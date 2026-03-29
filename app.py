import os
import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

READ_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

WRITE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# --- STATIC ROUTES ---
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/admin")
def admin():
    return send_from_directory(".", "admin.html")

@app.route("/about")
def about():
    return send_from_directory(".", "about.html")

# --- API ROUTES ---
@app.route('/api/wallpapers')
def get_wallpapers():
    # Adding order=added_at.desc to mirror standard library viewing
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/wallpapers?select=*&order=added_at.desc",
        headers=READ_HEADERS
    )
    return jsonify(res.json()), res.status_code

@app.route('/api/pending')
def get_pending():
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/pending?select=*&order=added_at.desc",
        headers=READ_HEADERS
    )
    return jsonify(res.json()), res.status_code

@app.route('/api/approve/<wp_id>', methods=['POST'])
def approve(wp_id):
    data = request.json or {}
    
    # Get from pending
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}&select=*",
        headers=READ_HEADERS
    )
    items = res.json()
    if not items or res.status_code != 200:
        return jsonify({"error": "Not found in pending"}), 404
        
    wallpaper = items[0]
    
    # Apply updates
    if "title" in data:
        wallpaper["title"] = data["title"]
    if "category" in data:
        wallpaper["category"] = data["category"]
    if "tags" in data:
        wallpaper["tags"] = data["tags"]
        
    # Insert into wallpapers
    insert_res = requests.post(f"{SUPABASE_URL}/rest/v1/wallpapers", headers=WRITE_HEADERS, json=wallpaper)
    if str(insert_res.status_code).startswith('2'):
        requests.delete(f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}", headers=WRITE_HEADERS)
        return jsonify({"success": True})
        
    return jsonify({"error": "Failed to approve"}), insert_res.status_code

@app.route('/api/reject/<wp_id>', methods=['POST'])
def reject(wp_id):
    res = requests.delete(f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}", headers=WRITE_HEADERS)
    if str(res.status_code).startswith('2'):
        return jsonify({"success": True})
    return jsonify({"error": "Failed to reject"}), res.status_code

@app.route('/api/approve-all', methods=['POST'])
def approve_all():
    # 1. Fetch pending
    res = requests.get(f"{SUPABASE_URL}/rest/v1/pending?select=*", headers=READ_HEADERS)
    pending = res.json()
    if not pending or res.status_code != 200:
        return jsonify({"success": True, "count": 0})
        
    # 2. Insert into wallpapers
    insert_res = requests.post(f"{SUPABASE_URL}/rest/v1/wallpapers", headers=WRITE_HEADERS, json=pending)
    
    if str(insert_res.status_code).startswith('2'):
        # 3. Delete from pending
        requests.delete(f"{SUPABASE_URL}/rest/v1/pending?id=not.is.null", headers=WRITE_HEADERS)
        return jsonify({"success": True, "count": len(pending)})
        
    return jsonify({"error": "Failed to approve all"}), insert_res.status_code

@app.route('/api/reject-all', methods=['POST'])
def reject_all():
    # Count first
    res = requests.get(f"{SUPABASE_URL}/rest/v1/pending?select=*", headers=READ_HEADERS)
    count = len(res.json()) if res.status_code == 200 else 0
    
    del_res = requests.delete(f"{SUPABASE_URL}/rest/v1/pending?id=not.is.null", headers=WRITE_HEADERS)
    if str(del_res.status_code).startswith('2'):
        return jsonify({"success": True, "count": count})
    return jsonify({"error": "Failed to reject all"}), del_res.status_code

@app.route('/api/update/<wp_id>', methods=['POST'])
def update(wp_id):
    data = request.json or {}
    if not data:
        return jsonify({"error": "No updates provided"}), 400
        
    res = requests.patch(f"{SUPABASE_URL}/rest/v1/wallpapers?id=eq.{wp_id}", headers=WRITE_HEADERS, json=data)
    if str(res.status_code).startswith('2'):
        return jsonify({"success": True})
    return jsonify({"error": "Failed to update"}), res.status_code

@app.route('/api/delete/<wp_id>', methods=['POST'])
def delete_wp(wp_id):
    res = requests.delete(f"{SUPABASE_URL}/rest/v1/wallpapers?id=eq.{wp_id}", headers=WRITE_HEADERS)
    if str(res.status_code).startswith('2'):
        return jsonify({"success": True})
    return jsonify({"error": "Failed to delete"}), res.status_code

@app.route('/api/test', methods=['POST'])
def test():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
