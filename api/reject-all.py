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
            
            # Fetch count first just to return it
            get_res = requests.get(f"{SUPABASE_URL}/rest/v1/pending?select=*", headers=headers)
            count = len(get_res.json()) if get_res.status_code == 200 else 0
            
            # Delete all
            del_res = requests.delete(f"{SUPABASE_URL}/rest/v1/pending?id=not.is.null", headers=headers)
            
            if str(del_res.status_code).startswith('2'):
                self.send_success({"success": True, "count": count})
            else:
                self.send_error(del_res.status_code, "Failed to reject all")
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
