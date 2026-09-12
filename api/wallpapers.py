import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

SELECT_FIELDS = "id,title,image_url,thumb_url,source_url,orientation,tags,category,resolution,added_at"
DEFAULT_LIMIT = 36
MAX_LIMIT = 100


def _parse_qs(path: str) -> dict:
    return urllib.parse.parse_qs(urllib.parse.urlparse(path).query)


def _first(qs: dict, key: str, default: str | None = None) -> str | None:
    vals = qs.get(key)
    return vals[0] if vals else default


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        qs = _parse_qs(self.path)
        try:
            limit = min(max(int(_first(qs, "limit", str(DEFAULT_LIMIT))), 1), MAX_LIMIT)
        except ValueError:
            limit = DEFAULT_LIMIT
        try:
            offset = max(int(_first(qs, "offset", "0")), 0)
        except ValueError:
            offset = 0

        orientation = _first(qs, "orientation")
        category = _first(qs, "category")
        resolution = _first(qs, "resolution")
        q = (_first(qs, "q") or "").strip()

        filters = []
        if orientation in ("desktop", "mobile"):
            filters.append(f"orientation=eq.{urllib.parse.quote(orientation)}")
        if category and category != "All":
            filters.append(f"category=eq.{urllib.parse.quote(category)}")
        if resolution and resolution != "All":
            filters.append(f"resolution=eq.{urllib.parse.quote(resolution)}")
        if q:
            # title search (case-insensitive)
            safe = q.replace(",", " ").replace(".", " ")
            filters.append(f"title=ilike.*{urllib.parse.quote(safe)}*")

        query = (
            f"select={SELECT_FIELDS}"
            f"&order=added_at.desc"
            f"&limit={limit}"
            f"&offset={offset}"
        )
        if filters:
            query += "&" + "&".join(filters)

        url = f"{SUPABASE_URL}/rest/v1/wallpapers?{query}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "count=exact",
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code not in (200, 206):
                self._json(response.status_code, {"error": "Failed to fetch", "detail": response.text[:200]})
                return

            items = response.json()
            if not isinstance(items, list):
                self._json(500, {"error": "Unexpected response shape"})
                return
            total = len(items)
            # Content-Range: 0-35/715
            cr = response.headers.get("Content-Range") or response.headers.get("content-range")
            if cr and "/" in cr:
                try:
                    total = int(cr.split("/")[-1])
                except ValueError:
                    pass

            body = {
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(items) < total,
            }
            self._json(
                200,
                body,
                cache="public, s-maxage=60, stale-while-revalidate=600",
            )
        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, status: int, data: dict, cache: str | None = None):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        if cache and status == 200:
            self.send_header("Cache-Control", cache)
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        return
