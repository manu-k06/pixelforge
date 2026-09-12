# PixelForge v2

![PixelForge](https://pixelforge-io.vercel.app)

> AI-curated wallpaper platform. Stunning wallpapers  
> discovered automatically and filtered by AI.

## Live Site
🌐 [pixelforge-io.vercel.app](https://pixelforge-io.vercel.app)

## What is PixelForge?
PixelForge is an automated wallpaper discovery platform  
that uses AI to curate high-quality wallpapers from  
across the internet. Every wallpaper in the library has  
been individually judged by Gemini AI for quality,  
composition, and visual appeal.

## Features
- AI-powered wallpaper curation using Google Gemini
- Paginated masonry grid with infinite scroll
- WebP thumbnails for fast browsing; full-res for download
- Images hosted on Supabase Storage (not hotlinked for the grid)
- Categories: Anime, Dark, Sci-Fi, Nature, Abstract,  
  Cyberpunk, Minimal, Fantasy, AI Art
- Desktop and Mobile wallpaper separation
- Resolution filtering: 1080p, 1440p, 4K
- Wallpaper of the Day
- Fullscreen lightbox preview
- One-click download
- NSFW content filtering
- Admin panel for manual review
- Fully automated pipeline via GitHub Actions

## Tech Stack
- Frontend: HTML, CSS, Vanilla JS
- Backend: Python Flask (local) / Vercel Serverless Functions
- Database: Supabase (PostgreSQL + Storage)
- AI: Google Gemini 2.5 Flash
- Deployment: Vercel
- Automation: GitHub Actions (runs every 6 hours)

## How It Works
1. GitHub Actions runs `pipeline.py` every 6 hours
2. Fetches top posts from wallpaper sources
3. Gemini AI judges each image for quality
4. Candidates land in Supabase `pending`
5. Admin approves → image is rehosted (full + thumb WebP) to Storage
6. Gallery loads paginated thumbs; lightbox/download use full files

## Project Structure
```
PixelForge/
├── api/                  # Vercel serverless functions
│   ├── lib/              # Shared image storage helpers
│   ├── wallpapers.py     # GET paginated wallpapers
│   ├── pending.py
│   ├── approve.py        # Approves + rehosts image
│   └── …
├── schema.sql            # DB columns for thumb_url / source_url
├── backfill_images.py    # Rehost existing library
├── index.html
├── admin.html
├── app.py
├── pipeline.py
└── requirements.txt
```

## Setup
1. Clone the repo  
2. `pip install -r requirements.txt`  
3. Add `.env`:
   ```
   GEMINI_API_KEY=…
   SUPABASE_URL=…
   SUPABASE_KEY=…              # anon
   SUPABASE_SERVICE_KEY=…      # service role (writes + storage)
   ADMIN_USERNAME=…
   ADMIN_PASSWORD=…
   ADMIN_SECRET=…
   ```
4. In Supabase SQL Editor, run `schema.sql`  
5. (Optional) create a **public** Storage bucket named `wallpapers`  
   — or let `backfill_images.py` / approve create it  
6. Local: `python app.py`  
7. Backfill existing rows: `python backfill_images.py`  
8. Pipeline: `python pipeline.py`

### Gallery API
`GET /api/wallpapers?limit=36&offset=0&orientation=desktop&category=Anime&resolution=4K&q=space`

Returns:
```json
{ "items": [...], "total": 715, "limit": 36, "offset": 0, "has_more": true }
```

Cached at the edge (~60s) with stale-while-revalidate.

## Built By
Manu K Rajan — [github.com/manu-k06](https://github.com/manu-k06)
