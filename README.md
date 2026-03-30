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
- Masonry grid layout with 3D card tilt effects
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
- Database: Supabase (PostgreSQL)
- AI: Google Gemini 2.5 Flash
- Deployment: Vercel
- Automation: GitHub Actions (runs every 6 hours)

## How It Works
1. GitHub Actions runs pipeline.py every 6 hours
2. Fetches top posts from wallpaper subreddits
3. Gemini AI judges each image for quality
4. Approved wallpapers saved to Supabase pending table
5. Admin reviews and approves via admin panel
6. Approved wallpapers go live on the site instantly

## Project Structure
PixelForge/
├── api/                  # Vercel serverless functions
│   ├── wallpapers.py     # GET live wallpapers
│   ├── pending.py        # GET pending wallpapers
│   ├── approve.py        # POST approve wallpaper
│   ├── reject.py         # POST reject wallpaper
│   ├── delete.py         # POST delete wallpaper
│   ├── update.py         # POST update wallpaper
│   ├── approve-all.py    # POST approve all pending
│   ├── reject-all.py     # POST reject all pending
│   └── auth.py           # POST admin authentication
├── .github/
│   └── workflows/
│       └── pipeline.yml  # GitHub Actions automation
├── index.html            # Main website
├── admin.html            # Admin panel
├── about.html            # About page
├── app.py                # Local Flask server
├── pipeline.py           # AI curation pipeline
├── migrate.py            # Supabase migration script
├── fix_orientation.py    # Image orientation fixer
├── vercel.json           # Vercel configuration
└── requirements.txt      # Python dependencies

## Setup
1. Clone the repo
2. Install dependencies: pip install -r requirements.txt
3. Add .env file with credentials:
   GEMINI_API_KEY=your_key
   SUPABASE_URL=your_url
   SUPABASE_KEY=your_anon_key
   SUPABASE_SERVICE_KEY=your_service_key
   ADMIN_USERNAME=your_username
   ADMIN_PASSWORD=your_password
   ADMIN_SECRET=your_secret
4. Run locally: python app.py
5. Run pipeline: python pipeline.py

## Built By
Manu K Rajan — [github.com/manu-k06](https://github.com/manu-k06)
