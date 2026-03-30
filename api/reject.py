import os
import json
import urllib.parse
import requests
from http.server import BaseHTTPRequestHandler

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            query_components = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            wp_id = query_components.get("id", [None])[0]
            
            if not wp_id:
                self.send_error(400, "Missing ID")
                return

            headers = {
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            }
            
            delete_url = f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}"
            res = requests.delete(delete_url, headers=headers)
            
            if str(res.status_code).startswith('2'):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
            else:
                self.send_error(res.status_code, "Failed to delete")
        except Exception as e:
            self.send_error(500, str(e))

    def send_error(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))
