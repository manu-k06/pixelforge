import json
import os
from http.server import BaseHTTPRequestHandler

import jwt
import requests

from lib.image_storage import apply_rehost

ADMIN_SECRET = os.environ.get("ADMIN_SECRET")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")


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

            headers = {
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            }

            get_res = requests.get(
                f"{SUPABASE_URL}/rest/v1/pending?select=*",
                headers=headers,
                timeout=30,
            )
            pending_items = get_res.json() if get_res.status_code == 200 else []

            if not pending_items:
                self._json(200, {"success": True, "count": 0})
                return

            approved = 0
            errors = []
            for item in pending_items:
                wp_id = item.get("id")
                try:
                    item = apply_rehost(item)
                    insert_res = requests.post(
                        f"{SUPABASE_URL}/rest/v1/wallpapers",
                        headers=headers,
                        json=item,
                        timeout=60,
                    )
                    if str(insert_res.status_code).startswith("2"):
                        requests.delete(
                            f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}",
                            headers=headers,
                            timeout=30,
                        )
                        approved += 1
                    else:
                        errors.append({"id": wp_id, "error": insert_res.text[:120]})
                except Exception as e:
                    errors.append({"id": wp_id, "error": str(e)})

            self._json(200, {"success": True, "count": approved, "errors": errors})
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
