import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import jwt
import requests

# Ensure api/ is on path so `lib.image_storage` resolves on Vercel
_API_DIR = str(Path(__file__).resolve().parent)
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

ADMIN_SECRET = os.environ.get("ADMIN_SECRET")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")


def _get_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _rehost(item: dict) -> dict:
    """Rehost when possible; never block approve if storage/Pillow fails."""
    try:
        from lib.image_storage import apply_rehost
        return apply_rehost(item)
    except Exception as e:
        print(f"[approve] rehost skipped: {e}", flush=True)
        item.setdefault("source_url", item.get("image_url"))
        return item


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self):
        try:
            auth = self.headers.get("Authorization", "")
            token = auth.replace("Bearer ", "")
            try:
                jwt.decode(token, ADMIN_SECRET, algorithms=["HS256"])
            except Exception:
                self._json(401, {"error": "Unauthorized"})
                return

            query_components = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            wp_id = query_components.get("id", [None])[0]

            if not wp_id:
                self._json(400, {"error": "Missing ID"})
                return

            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            updates = json.loads(post_data) if post_data else {}

            headers = _get_headers()
            fetch_url = f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}&select=*"
            res = requests.get(fetch_url, headers=headers, timeout=30)

            if res.status_code != 200 or not res.json():
                self._json(404, {"error": "Pending wallpaper not found"})
                return

            item = res.json()[0]

            if "title" in updates:
                item["title"] = updates["title"]
            if "category" in updates:
                item["category"] = updates["category"]
            if "tags" in updates:
                item["tags"] = updates["tags"]

            item = _rehost(item)

            insert_url = f"{SUPABASE_URL}/rest/v1/wallpapers"
            insert_res = requests.post(insert_url, headers=headers, json=item, timeout=60)

            if str(insert_res.status_code).startswith("2"):
                delete_url = f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}"
                requests.delete(delete_url, headers=headers, timeout=30)

                self._json(200, {"success": True, "thumb_url": item.get("thumb_url")})
            else:
                self._json(
                    insert_res.status_code,
                    {"error": "Failed to insert into library", "detail": insert_res.text[:200]},
                )
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        return
