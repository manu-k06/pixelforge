-- PixelForge Phase 2 schema upgrades
-- Run this once in the Supabase SQL Editor.

alter table public.wallpapers
  add column if not exists thumb_url text;

alter table public.wallpapers
  add column if not exists source_url text;

alter table public.pending
  add column if not exists thumb_url text;

alter table public.pending
  add column if not exists source_url text;

-- Optional indexes for gallery filters
create index if not exists wallpapers_orientation_idx on public.wallpapers (orientation);
create index if not exists wallpapers_category_idx on public.wallpapers (category);
create index if not exists wallpapers_added_at_idx on public.wallpapers (added_at desc);

-- Storage bucket is created automatically by backfill_images.py / approve
-- (bucket id: wallpapers, public). Or create it in Dashboard → Storage:
--   name: wallpapers
--   public: true
