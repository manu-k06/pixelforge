import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def migrate():
    try:
        with open("wallpapers.json", "r", encoding="utf-8") as f:
            wallpapers = json.load(f)
    except FileNotFoundError:
        print("wallpapers.json not found!")
        return

    if not wallpapers:
        print("No wallpapers to migrate.")
        return

    print(f"Migrating {len(wallpapers)} wallpapers to Supabase...")
    
    # We can batch insert directly
    res = requests.post(f"{SUPABASE_URL}/rest/v1/wallpapers", headers=HEADERS, json=wallpapers)
    
    if str(res.status_code).startswith('2'):
        print(f"Successfully migrated {len(wallpapers)} wallpapers!")
    else:
        print(f"Failed to migrate: HTTP {res.status_code}")
        print(res.text)

if __name__ == "__main__":
    migrate()
