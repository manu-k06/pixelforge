import os
import json
import urllib.parse
import requests
from http.server import BaseHTTPRequestHandler

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
# Use SERVICE_KEY for write ops, fallback to KEY
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_KEY", ""))

def _get_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Parse query params
            query_components = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            wp_id = query_components.get("id", [None])[0]
            
            if not wp_id:
                self.send_error(400, "Missing ID")
                return

            # Read body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            updates = json.loads(post_data) if post_data else {}

            # Fetch existing pending item
            headers = _get_headers()
            fetch_url = f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}&select=*"
            res = requests.get(fetch_url, headers=headers)
            
            if res.status_code != 200 or not res.json():
                self.send_error(404, "Pending wallpaper not found")
                return
                
            item = res.json()[0]
            
            # Apply updates
            if "title" in updates:
                item["title"] = updates["title"]
            if "category" in updates:
                item["category"] = updates["category"]
            if "tags" in updates:
                item["tags"] = updates["tags"]
                
            # Insert into wallpapers
            insert_url = f"{SUPABASE_URL}/rest/v1/wallpapers"
            insert_res = requests.post(insert_url, headers=headers, json=item)
            
            if insert_res.status_code in (201, 204) or str(insert_res.status_code).startswith('2'):
                # Delete from pending
                delete_url = f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}"
                requests.delete(delete_url, headers=headers)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
            else:
                self.send_error(insert_res.status_code, "Failed to insert into library")
        except Exception as e:
            self.send_error(500, str(e))
            
    def send_error(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))
