import os
import json
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), "wallpapers.json")


def load_wallpapers():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/wallpapers")
def get_wallpapers():
    return jsonify(load_wallpapers())


if __name__ == "__main__":
    app.run(debug=True, port=5000)
