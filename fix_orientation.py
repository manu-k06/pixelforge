import json
import os
import requests
from io import BytesIO
from PIL import Image

DATA_FILE = os.path.join(os.path.dirname(__file__), "wallpapers.json")

def load_json_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_json_file(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def fix_orientation():
    wallpapers = load_json_file(DATA_FILE)
    total = len(wallpapers)
    valid_wallpapers = []
    removed = 0
    
    print(f"Checking {total} wallpapers...")
    
    for i, wp in enumerate(wallpapers):
        print(f"[{i+1}/{total}] Checking {wp.get('title')}...")
        try:
            response = requests.get(
                wp["image_url"], 
                timeout=10, 
                headers={'User-Agent': 'PixelForge/1.0'}
            )
            response.raise_for_status()
            img = Image.open(BytesIO(response.content))
            width, height = img.size
            
            if height == 0:
                print(f"  -> Invalid dimensions")
                valid_wallpapers.append(wp)
                continue
                
            ratio = width / height
            if 0.7 <= ratio <= 1.6:
                print(f"  -> {width}x{height} -> Removed (ratio {ratio:.2f})")
                removed += 1
                continue
                
            max_dim = max(width, height)
            if max_dim <= 1920:
                wp["resolution"] = "1080p"
            elif max_dim <= 2560:
                wp["resolution"] = "1440p"
            else:
                wp["resolution"] = "4K"

            if height > width:
                wp["orientation"] = "mobile"
            else:
                wp["orientation"] = "desktop"
                
            print(f"  -> {width}x{height} -> {wp['orientation']}")
            valid_wallpapers.append(wp)
            
        except Exception as e:
            print(f"  -> Error fetching/parsing: {e}. Defaulting to desktop.")
            wp["orientation"] = "desktop"
            valid_wallpapers.append(wp)
            
    save_json_file(DATA_FILE, valid_wallpapers)
    print(f"Done! updated wallpapers.json. Removed {removed} square/non-standard wallpapers.")

if __name__ == "__main__":
    fix_orientation()
