from http.server import BaseHTTPRequestHandler
import json, os, jwt, datetime

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET")

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length))
        if body.get('username') == ADMIN_USERNAME and \
           body.get('password') == ADMIN_PASSWORD:
            token = jwt.encode({
                'user': ADMIN_USERNAME,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }, ADMIN_SECRET, algorithm='HS256')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'token': token}).encode())
        else:
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Invalid credentials'}).encode())
