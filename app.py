import os
import urllib.parse

import requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

# Allow importing api.lib helpers when running locally
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from lib.image_storage import apply_rehost, delete_stored  # noqa: E402

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

READ_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

WRITE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

SELECT_FIELDS = "id,title,image_url,thumb_url,source_url,orientation,tags,category,resolution,added_at"
DEFAULT_LIMIT = 36
MAX_LIMIT = 100


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
    try:
        limit = min(max(int(request.args.get("limit", DEFAULT_LIMIT)), 1), MAX_LIMIT)
    except ValueError:
        limit = DEFAULT_LIMIT
    try:
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        offset = 0

    orientation = request.args.get("orientation")
    category = request.args.get("category")
    resolution = request.args.get("resolution")
    q = (request.args.get("q") or "").strip()

    filters = []
    if orientation in ("desktop", "mobile"):
        filters.append(f"orientation=eq.{urllib.parse.quote(orientation)}")
    if category and category != "All":
        filters.append(f"category=eq.{urllib.parse.quote(category)}")
    if resolution and resolution != "All":
        filters.append(f"resolution=eq.{urllib.parse.quote(resolution)}")
    if q:
        safe = q.replace(",", " ").replace(".", " ")
        filters.append(f"title=ilike.*{urllib.parse.quote(safe)}*")

    query = f"select={SELECT_FIELDS}&order=added_at.desc&limit={limit}&offset={offset}"
    if filters:
        query += "&" + "&".join(filters)

    headers = {**READ_HEADERS, "Prefer": "count=exact"}
    res = requests.get(f"{SUPABASE_URL}/rest/v1/wallpapers?{query}", headers=headers, timeout=30)
    if res.status_code not in (200, 206):
        return jsonify({"error": "Failed to fetch", "detail": res.text[:200]}), res.status_code

    items = res.json()
    if not isinstance(items, list):
        return jsonify({"error": "Unexpected response shape"}), 500
    total = len(items)
    cr = res.headers.get("Content-Range") or res.headers.get("content-range")
    if cr and "/" in cr:
        try:
            total = int(cr.split("/")[-1])
        except ValueError:
            pass

    resp = jsonify({
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    })
    resp.headers["Cache-Control"] = "public, s-maxage=60, stale-while-revalidate=600"
    return resp, 200


@app.route("/api/pending")
def get_pending():
    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/pending?select=*&order=added_at.desc",
        headers=READ_HEADERS,
        timeout=30,
    )
    return jsonify(res.json()), res.status_code


@app.route("/api/approve/<wp_id>", methods=["POST"])
def approve(wp_id):
    data = request.json or {}

    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}&select=*",
        headers=READ_HEADERS,
        timeout=30,
    )
    items = res.json()
    if not items or res.status_code != 200:
        return jsonify({"error": "Not found in pending"}), 404

    wallpaper = items[0]

    if "title" in data:
        wallpaper["title"] = data["title"]
    if "category" in data:
        wallpaper["category"] = data["category"]
    if "tags" in data:
        wallpaper["tags"] = data["tags"]

    wallpaper = apply_rehost(wallpaper)

    insert_res = requests.post(
        f"{SUPABASE_URL}/rest/v1/wallpapers",
        headers=WRITE_HEADERS,
        json=wallpaper,
        timeout=60,
    )
    if str(insert_res.status_code).startswith("2"):
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}",
            headers=WRITE_HEADERS,
            timeout=30,
        )
        return jsonify({"success": True, "thumb_url": wallpaper.get("thumb_url")})

    return jsonify({"error": "Failed to approve", "detail": insert_res.text[:200]}), insert_res.status_code


@app.route("/api/reject/<wp_id>", methods=["POST"])
def reject(wp_id):
    res = requests.delete(
        f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}",
        headers=WRITE_HEADERS,
        timeout=30,
    )
    if str(res.status_code).startswith("2"):
        return jsonify({"success": True})
    return jsonify({"error": "Failed to reject"}), res.status_code


@app.route("/api/approve-all", methods=["POST"])
def approve_all():
    res = requests.get(f"{SUPABASE_URL}/rest/v1/pending?select=*", headers=READ_HEADERS, timeout=30)
    pending = res.json() if res.status_code == 200 else []
    if not pending:
        return jsonify({"success": True, "count": 0})

    approved = 0
    errors = []
    for item in pending:
        wp_id = item.get("id")
        try:
            item = apply_rehost(item)
            insert_res = requests.post(
                f"{SUPABASE_URL}/rest/v1/wallpapers",
                headers=WRITE_HEADERS,
                json=item,
                timeout=60,
            )
            if str(insert_res.status_code).startswith("2"):
                requests.delete(
                    f"{SUPABASE_URL}/rest/v1/pending?id=eq.{wp_id}",
                    headers=WRITE_HEADERS,
                    timeout=30,
                )
                approved += 1
            else:
                errors.append({"id": wp_id, "error": insert_res.text[:120]})
        except Exception as e:
            errors.append({"id": wp_id, "error": str(e)})

    return jsonify({"success": True, "count": approved, "errors": errors})


@app.route("/api/reject-all", methods=["POST"])
def reject_all():
    res = requests.get(f"{SUPABASE_URL}/rest/v1/pending?select=*", headers=READ_HEADERS, timeout=30)
    count = len(res.json()) if res.status_code == 200 else 0

    del_res = requests.delete(
        f"{SUPABASE_URL}/rest/v1/pending?id=not.is.null",
        headers=WRITE_HEADERS,
        timeout=30,
    )
    if str(del_res.status_code).startswith("2"):
        return jsonify({"success": True, "count": count})
    return jsonify({"error": "Failed to reject all"}), del_res.status_code


@app.route("/api/update/<wp_id>", methods=["POST"])
def update(wp_id):
    data = request.json or {}
    if not data:
        return jsonify({"error": "No updates provided"}), 400

    res = requests.patch(
        f"{SUPABASE_URL}/rest/v1/wallpapers?id=eq.{wp_id}",
        headers=WRITE_HEADERS,
        json=data,
        timeout=30,
    )
    if str(res.status_code).startswith("2"):
        return jsonify({"success": True})
    return jsonify({"error": "Failed to update"}), res.status_code


@app.route("/api/delete/<wp_id>", methods=["POST"])
def delete_wp(wp_id):
    try:
        delete_stored(wp_id)
    except Exception:
        pass
    res = requests.delete(
        f"{SUPABASE_URL}/rest/v1/wallpapers?id=eq.{wp_id}",
        headers=WRITE_HEADERS,
        timeout=30,
    )
    if str(res.status_code).startswith("2"):
        return jsonify({"success": True})
    return jsonify({"error": "Failed to delete"}), res.status_code


@app.route("/api/test", methods=["POST"])
def test():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
