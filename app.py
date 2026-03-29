import os
import json
import tempfile
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), "wallpapers.json")
PENDING_FILE = os.path.join(os.path.dirname(__file__), "pending.json")


def load_json_file(filepath: str) -> list[dict]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_json_file_atomic(filepath: str, data: list[dict]):
    # Write to a temporary file in the same directory, then replace atomically
    dir_name = os.path.dirname(filepath)
    fd, temp_path = tempfile.mkstemp(dir=dir_name, suffix=".json", prefix="tmp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp_path, filepath)
    except Exception as e:
        os.remove(temp_path)
        raise e


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/admin")
def admin():
    return send_from_directory(".", "admin.html")

@app.route("/about")
def about():
    return send_from_directory(".", "about.html")


@app.route("/api/wallpapers")
def get_wallpapers():
    wallpapers = load_json_file(DATA_FILE)
    for w in wallpapers:
        if "orientation" not in w:
            w["orientation"] = "desktop"
    return jsonify(wallpapers)


@app.route("/api/pending")
def get_pending():
    return jsonify(load_json_file(PENDING_FILE))


@app.route("/api/approve/<string:wp_id>", methods=["POST"])
def approve(wp_id):
    pending = load_json_file(PENDING_FILE)
    wallpapers = load_json_file(DATA_FILE)
    
    updates = request.json or {}
    item_to_move = None
    new_pending = []
    
    for item in pending:
        if item.get("id") == wp_id:
            item_to_move = item
        else:
            new_pending.append(item)
            
    if not item_to_move:
        return jsonify({"error": "Not found"}), 404
        
    # Apply updates
    if "title" in updates:
        item_to_move["title"] = updates["title"]
    if "category" in updates:
        item_to_move["category"] = updates["category"]
    if "tags" in updates:
        item_to_move["tags"] = updates["tags"]
        
    # Add to main collection (at top so it's fresh)
    wallpapers.insert(0, item_to_move)
    
    save_json_file_atomic(DATA_FILE, wallpapers)
    save_json_file_atomic(PENDING_FILE, new_pending)
    return jsonify({"success": True})


@app.route("/api/reject/<string:wp_id>", methods=["POST"])
def reject(wp_id):
    pending = load_json_file(PENDING_FILE)
    new_pending = [item for item in pending if item.get("id") != wp_id]
    
    if len(pending) == len(new_pending):
        return jsonify({"error": "Not found"}), 404
        
    save_json_file_atomic(PENDING_FILE, new_pending)
    return jsonify({"success": True})


@app.route("/api/approve-all", methods=["POST"])
def approve_all():
    pending = load_json_file(PENDING_FILE)
    if not pending:
        return jsonify({"success": True, "count": 0})
        
    wallpapers = load_json_file(DATA_FILE)
    # prepend the approved ones
    wallpapers = pending + wallpapers
    
    save_json_file_atomic(DATA_FILE, wallpapers)
    save_json_file_atomic(PENDING_FILE, [])
    return jsonify({"success": True, "count": len(pending)})


@app.route("/api/reject-all", methods=["POST"])
def reject_all():
    pending = load_json_file(PENDING_FILE)
    count = len(pending)
    save_json_file_atomic(PENDING_FILE, [])
    return jsonify({"success": True, "count": count})


@app.route("/api/update/<string:wp_id>", methods=["POST"])
def update(wp_id):
    wallpapers = load_json_file(DATA_FILE)
    updates = request.json or {}
    
    found = False
    for item in wallpapers:
        if item.get("id") == wp_id:
            if "title" in updates:
                item["title"] = updates["title"]
            if "category" in updates:
                item["category"] = updates["category"]
            if "tags" in updates:
                item["tags"] = updates["tags"]
            found = True
            break
            
    if not found:
        return jsonify({"error": "Not found"}), 404
        
    save_json_file_atomic(DATA_FILE, wallpapers)
    return jsonify({"success": True})


@app.route("/api/delete/<string:wp_id>", methods=["POST"])
def delete_wp(wp_id):
    wallpapers = load_json_file(DATA_FILE)
    new_wallpapers = [item for item in wallpapers if item.get("id") != wp_id]
    
    if len(wallpapers) == len(new_wallpapers):
        return jsonify({"error": "Not found"}), 404
        
    save_json_file_atomic(DATA_FILE, new_wallpapers)
    return jsonify({"success": True})

@app.route("/api/test", methods=["POST"])
def test():
    return jsonify({"status": "ok"})

print(app.url_map)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
