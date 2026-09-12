"""
Remove suggestive / bikini-style wallpapers from Supabase (and local JSON).

Usage:
  python cleanup.py              # keywords + Gemini vision on Anime category
  python cleanup.py --dry-run    # list what would be removed
  python cleanup.py --keywords-only
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from io import BytesIO

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}"
    f":generateContent?key={GEMINI_API_KEY}"
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

DATA_FILE = os.path.join(os.path.dirname(__file__), "wallpapers.json")

KEYWORDS = (
    "bikini", "swimsuit", "swimwear", "lingerie", "underwear",
    "nsfw", "nude", "naked", "sexy", "suggestive", "ecchi",
    "hentai", "fanservice", "lewd", "cleavage", "topless",
    "bottomless", "skimpy", "revealing", "seductive",
    "microbikini", "sling bikini", "bunny girl", "schoolgirl",
    "abs workout", "underboob", "sideboob",
)

VISION_PROMPT = (
    "Is this wallpaper NSFW or suggestive fanservice? "
    "Answer YES if it shows anime/game girls in bikini, swimsuit, "
    "lingerie, underwear, skimpy/revealing clothing, sexualized pose, "
    "heavy cleavage focus, ecchi, or similar. "
    "Answer NO for SFW characters in normal clothes, landscapes, "
    "abstract, sci-fi, etc. "
    'Reply JSON only: {"remove": true or false, "reason": "short"}'
)


def matches_keywords(wp: dict) -> bool:
    title = (wp.get("title") or "").lower()
    tags = " ".join(t.lower() for t in (wp.get("tags") or []))
    blob = f"{title} {tags}"
    return any(kw in blob for kw in KEYWORDS)


def fetch_all(table: str) -> list[dict]:
    rows = []
    offset = 0
    page = 200
    while True:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?select=*&order=added_at.desc&limit={page}&offset={offset}",
            headers={**HEADERS, "Prefer": "count=exact"},
            timeout=60,
        )
        if res.status_code not in (200, 206):
            raise RuntimeError(f"Fetch {table} failed {res.status_code}: {res.text[:200]}")
        batch = res.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += len(batch)
    return rows


def delete_storage(wp_id: str) -> None:
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))
        from lib.image_storage import delete_stored
        delete_stored(wp_id)
    except Exception:
        pass


def delete_row(table: str, wp_id: str) -> None:
    res = requests.delete(
        f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{wp_id}",
        headers=HEADERS,
        timeout=30,
    )
    if not str(res.status_code).startswith("2"):
        raise RuntimeError(f"Delete failed {res.status_code}: {res.text[:200]}")


def vision_should_remove(image_url: str) -> tuple[bool, str]:
    if not GEMINI_API_KEY:
        return False, "no GEMINI_API_KEY"
    try:
        img_bytes = requests.get(
            image_url,
            headers={"User-Agent": "PixelForge/2.0"},
            timeout=40,
        ).content
        img = Image.open(BytesIO(img_bytes))
        img.thumbnail((1024, 1024))
        buf = BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        payload = {
            "contents": [{
                "parts": [
                    {"text": VISION_PROMPT},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                ]
            }]
        }
        resp = requests.post(GEMINI_URL, json=payload, timeout=45)
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(text)
        return bool(data.get("remove")), str(data.get("reason") or "")
    except Exception as e:
        return False, f"vision error: {e}"


def cleanup_local_json(dry_run: bool) -> int:
    if not os.path.exists(DATA_FILE):
        return 0
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        wallpapers = json.load(f)
    cleaned = []
    removed = 0
    for wp in wallpapers:
        if matches_keywords(wp):
            print(f"  [json] {wp.get('title')}")
            removed += 1
            continue
        cleaned.append(wp)
    if not dry_run and removed:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)
    return removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keywords-only", action="store_true")
    parser.add_argument("--sleep", type=float, default=8.0, help="Delay between Gemini calls")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Missing SUPABASE_URL / SUPABASE_SERVICE_KEY in .env")
        sys.exit(1)

    to_remove: list[tuple[str, dict, str]] = []  # table, wp, reason

    for table in ("wallpapers", "pending"):
        print(f"Scanning {table}…")
        rows = fetch_all(table)
        print(f"  {len(rows)} rows")
        for wp in rows:
            if matches_keywords(wp):
                to_remove.append((table, wp, "keyword"))

    # Vision pass for Anime still in library (catches bikini without keyword titles)
    if not args.keywords_only:
        if not GEMINI_API_KEY:
            print("No GEMINI_API_KEY — skipping vision pass (keywords only).")
        else:
            already = {wp["id"] for _, wp, _ in to_remove}
            anime = [
                wp for wp in fetch_all("wallpapers")
                if wp.get("id") not in already
                and (wp.get("category") or "").lower() == "anime"
            ]
            print(f"Vision-checking {len(anime)} Anime wallpapers…")
            for i, wp in enumerate(anime, 1):
                url = wp.get("source_url") or wp.get("image_url") or wp.get("thumb_url")
                print(f"  [{i}/{len(anime)}] {wp.get('title')}")
                remove, reason = vision_should_remove(url)
                if remove:
                    print(f"    → remove ({reason})")
                    to_remove.append(("wallpapers", wp, f"vision:{reason}"))
                else:
                    print(f"    → keep ({reason or 'SFW'})")
                time.sleep(args.sleep)

    # Dedupe by id
    seen = set()
    unique = []
    for table, wp, reason in to_remove:
        key = (table, wp.get("id"))
        if key in seen:
            continue
        seen.add(key)
        unique.append((table, wp, reason))

    print(f"\nMarked for removal: {len(unique)}")
    for table, wp, reason in unique:
        print(f"  - [{table}] {wp.get('id')} | {wp.get('title')} ({reason})")

    if args.dry_run:
        print("Dry run — nothing deleted.")
        return

    deleted = 0
    for table, wp, reason in unique:
        wp_id = wp.get("id")
        try:
            if table == "wallpapers":
                delete_storage(wp_id)
            delete_row(table, wp_id)
            deleted += 1
            print(f"Deleted {wp_id}")
        except Exception as e:
            print(f"Failed {wp_id}: {e}")

    json_removed = cleanup_local_json(dry_run=False)
    print(f"\nDone. Deleted {deleted} from Supabase, {json_removed} from wallpapers.json")


if __name__ == "__main__":
    main()
