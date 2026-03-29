import os
import json

DATA_FILE = os.path.join(os.path.dirname(__file__), "wallpapers.json")

def cleanup():
    if not os.path.exists(DATA_FILE):
        print("No wallpapers.json found.")
        return

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        wallpapers = json.load(f)

    keywords = ["bikini", "sweaty", "nsfw", "nude", "naked", "sexy", "suggestive"]

    initial_count = len(wallpapers)
    cleaned = []

    for wp in wallpapers:
        title = wp.get("title", "").lower()
        tags = [t.lower() for t in wp.get("tags", [])]
        
        # Check title
        if any(kw in title for kw in keywords):
            print(f"Removing: {wp.get('title')}")
            continue
            
        # Check tags
        if any(kw in tag for tag in tags for kw in keywords):
            print(f"Removing: {wp.get('title')}")
            continue
            
        cleaned.append(wp)

    removed = initial_count - len(cleaned)
    
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    print(f"Cleanup complete. Removed {removed} wallpapers.")

if __name__ == "__main__":
    cleanup()
