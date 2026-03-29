"""
PixelForge Pipeline — Fetch wallpapers from Reddit, judge with Gemini, save to wallpapers.json.
Run separately:  python pipeline.py
"""

import os
import json
import re
import time
import uuid
import base64
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

HEADERS = {"User-Agent": "PixelForge/1.0"}
DATA_FILE = os.path.join(os.path.dirname(__file__), "wallpapers.json")

SUBREDDITS = [
    "wallpapers",
    "Amoledbackgrounds",
    "animewallpaper",
    "ImaginaryLandscapes",
]

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
SKIP_EXTENSIONS = (".gif", ".gifv", ".mp4", ".webm")

PROMPT = (
    "Judge this wallpaper. Approve if: dark/moody, anime, "
    "sci-fi, cyberpunk, fantasy, abstract art, AI generated, "
    "beautiful landscapes, minimal art. "
    "Reject if: plain boring photo, meme, text overlays, "
    "low resolution, unappealing. "
    "Reply JSON only, no markdown:\n"
    "{\n"
    '  "approved": true or false,\n'
    '  "title": "short catchy 3-4 word title",\n'
    '  "tags": ["tag1","tag2","tag3"],\n'
    '  "category": "one of: Anime, Dark, Sci-Fi, Nature, '
    'Abstract, Cyberpunk, Minimal, Fantasy, AI Art"\n'
    "}"
)


def is_direct_image(url: str) -> bool:
    lower = url.lower().split("?")[0]
    if any(lower.endswith(ext) for ext in SKIP_EXTENSIONS):
        return False
    return any(lower.endswith(ext) for ext in IMAGE_EXTENSIONS)


def load_existing() -> list[dict]:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_data(data: list[dict]):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def judge_image(image_url: str) -> dict | None:
    try:
        img_data = requests.get(image_url, headers=HEADERS, timeout=20).content
    except Exception as e:
        print(f"  ✗ Failed to download image: {e}")
        return None

    # Determine mime type from URL
    lower = image_url.lower().split("?")[0]
    if lower.endswith(".png"):
        mime_type = "image/png"
    else:
        mime_type = "image/jpeg"

    # Build Gemini REST API request body
    img_b64 = base64.b64encode(img_data).decode("utf-8")
    payload = {
        "contents": [{
            "parts": [
                {"text": PROMPT},
                {"inline_data": {"mime_type": mime_type, "data": img_b64}},
            ]
        }]
    }

    for attempt in range(2):  # try once, retry once on 429
        try:
            resp = requests.post(GEMINI_URL, json=payload, timeout=30)
            if resp.status_code == 429 and attempt == 0:
                print(f"  ⏳ Rate limited, waiting 60s then retrying…")
                time.sleep(60)
                continue
            resp.raise_for_status()

            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            result = json.loads(text)
            return result if result.get("approved") else None
        except requests.exceptions.HTTPError as e:
            print(f"  ✗ HTTP Error: {e}")
            return None
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return None


def fetch_subreddit(subreddit: str) -> list[dict]:
    url = f"https://www.reddit.com/r/{subreddit}/top.json?limit=25&t=month"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        return resp.json()["data"]["children"]
    except Exception as e:
        print(f"  ✗ Failed to fetch r/{subreddit}: {e}")
        return []


def run_pipeline():
    existing = load_existing()
    existing_urls = {w["image_url"] for w in existing}
    new_wallpapers = []
    total_judged: int = 0
    total_approved: int = 0

    for sub in SUBREDDITS:
        if total_judged >= 15:
            break
        print(f"\n▸ Fetching r/{sub}...")
        posts = fetch_subreddit(sub)
        images = [p for p in posts if is_direct_image(p["data"].get("url", ""))]
        print(f"  Found {len(images)} direct images out of {len(posts)} posts")

        for i, post in enumerate(images):
            if total_judged >= 15:
                break
            data = post["data"]
            image_url = data["url"]

            if image_url in existing_urls:
                print(f"  ⊘ Skipping duplicate: {image_url[:60]}…")
                continue

            print(f"Processing {total_judged+1}/15: {image_url}")  # type: ignore
            total_judged += 1  # type: ignore

            try:
                judgement = judge_image(image_url)
            except Exception as e:
                print(f"  ✗ Unexpected error, skipping: {e}")
                continue

            time.sleep(12)  # rate-limit: respect free-tier quota

            if judgement is None:
                print(f"Result: rejected")
                continue

            total_approved += 1  # type: ignore
            entry = {
                "id": str(uuid.uuid4())[:8],  # type: ignore
                "title": judgement.get("title", data.get("title", "Untitled")),
                "image_url": image_url,
                "tags": judgement.get("tags", []),
                "category": judgement.get("category", "Abstract"),
                "subreddit": sub,
                "upvotes": data.get("ups", 0),
                "reddit_url": f"https://reddit.com{data.get('permalink', '')}",
                "added_at": datetime.now(timezone.utc).isoformat(),
            }
            new_wallpapers.append(entry)
            existing_urls.add(image_url)
            print(f"Result: approved")

    all_wallpapers = existing + new_wallpapers
    save_data(all_wallpapers)

    print(f"Done! Added {len(new_wallpapers)} new wallpapers to library")
    print(f"Total wallpapers in library: {len(all_wallpapers)}")


if __name__ == "__main__":
    run_pipeline()
