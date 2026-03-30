"""
PixelForge Pipeline — Fetch wallpapers from Reddit, judge with Gemini, save to wallpapers.json.
Run separately:  python pipeline.py
"""

import os
import sys
import json
import re
import time
import uuid
import base64
import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from io import BytesIO
from PIL import Image
from datetime import datetime, timezone
from dotenv import load_dotenv

print("Pipeline starting...")
sys.stdout.flush()

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
    'facebookexternalhit/1.1',
    'Twitterbot/1.0'
]

session = requests.Session()
retry = Retry(total=3, backoff_factor=1)
adapter = HTTPAdapter(max_retries=retry)
session.mount('https://', adapter)

def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

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
    "low resolution, unappealing, square format, "
    "non-standard aspect ratio, not suitable as a "
    "desktop or mobile wallpaper. "
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


def fetch_urls_from_supabase() -> set[str]:
    urls = set()
    try:
        res = requests.get(f"{SUPABASE_URL}/rest/v1/wallpapers?select=image_url", headers=get_supabase_headers(), timeout=30)
        if res.status_code == 200:
            urls.update(item["image_url"] for item in res.json())
        res = requests.get(f"{SUPABASE_URL}/rest/v1/pending?select=image_url", headers=get_supabase_headers(), timeout=30)
        if res.status_code == 200:
            urls.update(item["image_url"] for item in res.json())
    except Exception as e:
        print(f"  ✗ Failed to fetch existing urls from Supabase: {e}")
        sys.stdout.flush()
    return urls


def judge_image(image_url: str) -> dict | None:
    try:
        headers = {"User-Agent": random.choice(user_agents)}
        img_data = session.get(image_url, headers=headers, timeout=20).content
    except Exception as e:
        print(f"  ✗ Failed to download image: {e}")
        sys.stdout.flush()
        return None
        
    try:
        img = Image.open(BytesIO(img_data))
        width, height = img.size
        
        if height == 0:
            return None
            
        ratio = width / height
        if 0.7 <= ratio <= 1.6:
            print(f"  ⊘ Skipping square/non-standard: {ratio:.2f}")
            sys.stdout.flush()
            return None
            
        orientation = "mobile" if height > width else "desktop"
        
        max_dim = max(width, height)
        if max_dim <= 1920:
            resolution = "1080p"
        elif max_dim <= 2560:
            resolution = "1440p"
        else:
            resolution = "4K"
    except Exception as e:
        print(f"  ✗ Failed to process image with PIL: {e}")
        sys.stdout.flush()
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
                sys.stdout.flush()
                time.sleep(60)
                continue
            resp.raise_for_status()

            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            result = json.loads(text)
            if result.get("approved"):
                result["orientation"] = orientation
                result["resolution"] = resolution
                return result
            return None
        except requests.exceptions.HTTPError as e:
            print(f"  ✗ HTTP Error: {e}")
            sys.stdout.flush()
            return None
        except Exception as e:
            print(f"  ✗ Error: {e}")
            sys.stdout.flush()
            return None


def parse_rss_posts(xml_text: str) -> list[dict]:
    """Parse Reddit RSS XML into the same format as JSON API children."""
    import xml.etree.ElementTree as ET
    posts = []
    try:
        root = ET.fromstring(xml_text)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        for entry in root.findall('atom:entry', ns):
            content_el = entry.find('atom:content', ns)
            if content_el is None or content_el.text is None:
                continue
            content_html = content_el.text
            title_el = entry.find('atom:title', ns)
            link_el = entry.find('atom:link', ns)
            # Extract image URLs from the HTML content
            img_urls = re.findall(r'href="(https://i\.redd\.it/[^"]+)"', content_html)
            if not img_urls:
                img_urls = re.findall(r'src="(https://[^"]+\.(?:jpg|jpeg|png))"', content_html)
            if img_urls:
                posts.append({"data": {
                    "url": img_urls[0],
                    "title": title_el.text if title_el is not None else "Untitled",
                    "permalink": link_el.get('href', '') if link_el is not None else '',
                    "ups": 0,
                }})
    except ET.ParseError:
        pass
    return posts


def fetch_subreddit(subreddit: str) -> list[dict]:
    # Source 1: Reddit RSS feed
    try:
        rss_url = f"https://www.reddit.com/r/{subreddit}/top/.rss?t=week&limit=25"
        headers = {"User-Agent": "PixelForge/1.0"}
        resp = session.get(rss_url, headers=headers, timeout=15)
        resp.raise_for_status()
        posts = parse_rss_posts(resp.text)
        if posts:
            print(f"  ✓ Source: Reddit RSS ({len(posts)} posts)")
            sys.stdout.flush()
            return posts
    except Exception as e:
        print(f"  ⚠ RSS failed: {e}")
        sys.stdout.flush()

    time.sleep(random.uniform(1, 2))

    # Source 2: Teddit mirror
    try:
        teddit_url = f"https://teddit.net/r/{subreddit}/top?t=week&api"
        headers = {"User-Agent": random.choice(user_agents)}
        resp = session.get(teddit_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        posts = []
        for item in data if isinstance(data, list) else data.get("links", data.get("children", [])):
            post_data = item.get("data", item) if isinstance(item, dict) else item
            if isinstance(post_data, dict) and post_data.get("url"):
                posts.append({"data": post_data})
        if posts:
            print(f"  ✓ Source: Teddit ({len(posts)} posts)")
            sys.stdout.flush()
            return posts
    except Exception as e:
        print(f"  ⚠ Teddit failed: {e}")
        sys.stdout.flush()

    time.sleep(random.uniform(1, 2))

    # Source 3: Libreddit mirror
    try:
        libreddit_url = f"https://libreddit.spike.codes/r/{subreddit}/top.json?t=week"
        headers = {"User-Agent": random.choice(user_agents)}
        resp = session.get(libreddit_url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "data" in data and "children" in data["data"]:
            posts = data["data"]["children"]
            print(f"  ✓ Source: Libreddit ({len(posts)} posts)")
            sys.stdout.flush()
            return posts
    except Exception as e:
        print(f"  ⚠ Libreddit failed: {e}")
        sys.stdout.flush()

    time.sleep(random.uniform(1, 2))

    # Source 4: Fallback to direct Reddit JSON with rotating UA
    try:
        json_url = f"https://www.reddit.com/r/{subreddit}/top.json?limit=25&t=week"
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = session.get(json_url, headers=headers, timeout=15)
        resp.raise_for_status()
        posts = resp.json()["data"]["children"]
        print(f"  ✓ Source: Reddit JSON fallback ({len(posts)} posts)")
        sys.stdout.flush()
        return posts
    except Exception as e:
        print(f"  ⚠ Reddit JSON fallback failed: {e}")
        sys.stdout.flush()

    print(f"  ✗ All sources failed for r/{subreddit}")
    sys.stdout.flush()
    return []


def run_pipeline():
    print("Fetching existing URLs from Supabase...")
    sys.stdout.flush()
    existing_urls = fetch_urls_from_supabase()

    new_wallpapers = []
    total_judged: int = 0
    total_approved: int = 0

    for sub in SUBREDDITS:
        if total_judged >= 15:
            break
        print(f"\n▸ Fetching r/{sub}...")
        sys.stdout.flush()
        time.sleep(random.uniform(2, 5))
        posts = fetch_subreddit(sub)
        images = [p for p in posts if is_direct_image(p["data"].get("url", ""))]
        print(f"  Found {len(images)} direct images out of {len(posts)} posts")
        sys.stdout.flush()

        for i, post in enumerate(images):
            if total_judged >= 15:
                break
            data = post["data"]
            image_url = data["url"]

            if image_url in existing_urls:
                print(f"  ⊘ Skipping duplicate: {image_url[:60]}…")
                sys.stdout.flush()
                continue

            print(f"Processing {total_judged+1}/15: {image_url}")  # type: ignore
            sys.stdout.flush()
            total_judged += 1  # type: ignore

            try:
                judgement = judge_image(image_url)
            except Exception as e:
                print(f"  ✗ Unexpected error, skipping: {e}")
                sys.stdout.flush()
                continue

            time.sleep(12)  # rate-limit: respect free-tier quota

            if judgement is None:
                print(f"Result: rejected")
                sys.stdout.flush()
                continue

            total_approved += 1  # type: ignore
            entry = {
                "id": str(uuid.uuid4())[:8],  # type: ignore
                "title": judgement.get("title", data.get("title", "Untitled")),
                "image_url": image_url,
                "orientation": judgement.get("orientation", "desktop"),
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
            sys.stdout.flush()

    if new_wallpapers:
        res = requests.post(f"{SUPABASE_URL}/rest/v1/pending", headers=get_supabase_headers(), json=new_wallpapers, timeout=30)
        if str(res.status_code).startswith('2'):
            print(f"Done! Saved {len(new_wallpapers)} wallpapers to Supabase pending table for review")
            sys.stdout.flush()
        else:
            print(f"Failed to save to Supabase: {res.status_code} {res.text}")
            sys.stdout.flush()
    else:
        print("Done! No new wallpapers to save.")
        sys.stdout.flush()


if __name__ == "__main__":
    run_pipeline()
