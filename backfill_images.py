"""
Backfill existing wallpapers into Supabase Storage (full WebP + thumb).

Prereqs:
  1. Run schema.sql in the Supabase SQL editor (adds thumb_url, source_url).
  2. Ensure .env has SUPABASE_URL + SUPABASE_SERVICE_KEY.
  3. pip install -r requirements.txt

Usage:
  python backfill_images.py           # process all missing thumbs
  python backfill_images.py --limit 20
  python backfill_images.py --force   # re-encode even if thumb_url exists
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))
from lib.image_storage import apply_rehost, ensure_bucket  # noqa: E402

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def fetch_batch(offset: int, limit: int, force: bool) -> list[dict]:
    params = f"select=*&order=added_at.desc&limit={limit}&offset={offset}"
    if not force:
        params += "&thumb_url=is.null"
    res = requests.get(f"{SUPABASE_URL}/rest/v1/wallpapers?{params}", headers=HEADERS, timeout=60)
    if res.status_code != 200:
        raise RuntimeError(f"Fetch failed {res.status_code}: {res.text[:300]}")
    return res.json()


def update_row(wp_id: str, fields: dict) -> None:
    res = requests.patch(
        f"{SUPABASE_URL}/rest/v1/wallpapers?id=eq.{wp_id}",
        headers=HEADERS,
        json=fields,
        timeout=60,
    )
    if not str(res.status_code).startswith("2"):
        raise RuntimeError(f"Update failed {res.status_code}: {res.text[:300]}")


def main():
    parser = argparse.ArgumentParser(description="Rehost wallpapers to Supabase Storage")
    parser.add_argument("--limit", type=int, default=0, help="Max items to process (0 = all)")
    parser.add_argument("--batch", type=int, default=50, help="Fetch page size")
    parser.add_argument("--force", action="store_true", help="Reprocess rows that already have thumb_url")
    parser.add_argument("--sleep", type=float, default=0.3, help="Pause between items (seconds)")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Missing SUPABASE_URL / SUPABASE_SERVICE_KEY in .env")
        sys.exit(1)

    print("Ensuring storage bucket…")
    ensure_bucket()

    processed = 0
    failed = 0
    offset = 0

    while True:
        if args.limit and processed + failed >= args.limit:
            break

        page_limit = args.batch
        if args.limit:
            page_limit = min(page_limit, args.limit - (processed + failed))

        rows = fetch_batch(offset, page_limit, force=args.force)
        if not rows:
            break

        for item in rows:
            wp_id = item.get("id")
            print(f"→ {wp_id} {item.get('title', '')[:50]}")
            try:
                if args.force:
                    item["thumb_url"] = None
                # Prefer original source when re-encoding
                if item.get("source_url"):
                    item["image_url"] = item["source_url"]
                updated = apply_rehost(item)
                if not updated.get("thumb_url"):
                    raise RuntimeError("rehost did not set thumb_url")
                update_row(
                    wp_id,
                    {
                        "source_url": updated.get("source_url"),
                        "image_url": updated.get("image_url"),
                        "thumb_url": updated.get("thumb_url"),
                    },
                )
                processed += 1
                print("  ✓ ok")
            except Exception as e:
                failed += 1
                print(f"  ✗ {e}")
            time.sleep(args.sleep)

        if args.force:
            offset += len(rows)
        # when not forcing, rows without thumbs shrink so keep offset at 0
        if len(rows) < page_limit:
            break

    print(f"\nDone. processed={processed} failed={failed}")


if __name__ == "__main__":
    main()
