import os
import json
import requests
from http.server import BaseHTTPRequestHandler

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            headers = {
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            }
            
            # 1. Fetch all pending
            get_res = requests.get(f"{SUPABASE_URL}/rest/v1/pending?select=*", headers=headers)
            pending_items = get_res.json()
            
            if not pending_items:
                self.send_success({"success": True, "count": 0})
                return
                
            # 2. Insert into wallpapers
            insert_res = requests.post(f"{SUPABASE_URL}/rest/v1/wallpapers", headers=headers, json=pending_items)
            
            if str(insert_res.status_code).startswith('2'):
                # 3. Delete from pending
                # Workaround to delete all: id=not.is.null
                requests.delete(f"{SUPABASE_URL}/rest/v1/pending?id=not.is.null", headers=headers)
                
                self.send_success({"success": True, "count": len(pending_items)})
            else:
                self.send_error(insert_res.status_code, "Failed to insert batch")
        except Exception as e:
            self.send_error(500, str(e))

    def send_success(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
        
    def send_error(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))
