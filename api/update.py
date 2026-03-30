import os
import json
import urllib.parse
import requests
import jwt
from http.server import BaseHTTPRequestHandler

ADMIN_SECRET = os.environ.get("ADMIN_SECRET")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            auth = self.headers.get('Authorization', '')
            token = auth.replace('Bearer ', '')
            try:
                jwt.decode(token, ADMIN_SECRET, algorithms=['HS256'])
            except Exception:
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Unauthorized'}).encode())
                return

            query_components = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            wp_id = query_components.get("id", [None])[0]
            
            if not wp_id:
                self.send_error(400, "Missing ID")
                return

            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            updates = json.loads(post_data) if post_data else {}
            
            if not updates:
                self.send_error(400, "No updates provided")
                return

            headers = {
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            
            update_url = f"{SUPABASE_URL}/rest/v1/wallpapers?id=eq.{wp_id}"
            res = requests.patch(update_url, headers=headers, json=updates)
            
            if str(res.status_code).startswith('2'):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
            else:
                self.send_error(res.status_code, "Failed to update")
        except Exception as e:
            self.send_error(500, str(e))

    def send_error(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))
