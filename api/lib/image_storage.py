"""Download wallpapers, create WebP thumb + full, upload to Supabase Storage."""

from __future__ import annotations

import io
import os
from typing import Any
from urllib.parse import quote

import requests
from PIL import Image

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "wallpapers")

THUMB_MAX = 800
FULL_MAX = 3840
THUMB_QUALITY = 72
FULL_QUALITY = 85

_UA = {
    "User-Agent": "PixelForge/2.0 (wallpaper curator)",
    "Accept": "image/*,*/*",
}


def _service_headers(extra: dict | None = None) -> dict:
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    if extra:
        headers.update(extra)
    return headers


def public_url(path: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"


def ensure_bucket() -> None:
    """Create public wallpapers bucket if it does not exist."""
    list_res = requests.get(
        f"{SUPABASE_URL}/storage/v1/bucket/{BUCKET}",
        headers=_service_headers(),
        timeout=30,
    )
    if list_res.status_code == 200:
        return
    requests.post(
        f"{SUPABASE_URL}/storage/v1/bucket",
        headers=_service_headers({"Content-Type": "application/json"}),
        json={"id": BUCKET, "name": BUCKET, "public": True},
        timeout=30,
    )


def _download(url: str) -> bytes:
    res = requests.get(url, headers=_UA, timeout=60)
    res.raise_for_status()
    return res.content


def _to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGB", "L"):
        return img.convert("RGB")
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (0, 0, 0))
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


def _encode_webp(img: Image.Image, max_edge: int, quality: int) -> bytes:
    img = _to_rgb(img)
    img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=4)
    return buf.getvalue()


def _upload(path: str, data: bytes, content_type: str = "image/webp") -> None:
    # upsert via x-upsert
    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"
    res = requests.post(
        url,
        headers=_service_headers(
            {
                "Content-Type": content_type,
                "x-upsert": "true",
            }
        ),
        data=data,
        timeout=90,
    )
    if res.status_code not in (200, 201):
        # Some projects use PUT for upsert
        res = requests.put(
            url,
            headers=_service_headers(
                {
                    "Content-Type": content_type,
                    "x-upsert": "true",
                }
            ),
            data=data,
            timeout=90,
        )
    if res.status_code not in (200, 201):
        raise RuntimeError(f"Storage upload failed ({res.status_code}): {res.text[:300]}")


def delete_stored(wallpaper_id: str) -> None:
    """Best-effort delete of stored full/thumb objects."""
    paths = [f"full/{wallpaper_id}.webp", f"thumb/{wallpaper_id}.webp"]
    try:
        requests.delete(
            f"{SUPABASE_URL}/storage/v1/object/{BUCKET}",
            headers=_service_headers({"Content-Type": "application/json"}),
            json={"prefixes": paths},
            timeout=30,
        )
    except Exception:
        pass


def rehost_wallpaper(wallpaper_id: str, source_url: str) -> dict[str, str]:
    """
    Download source_url, upload WebP full + thumb, return URL fields.

    Returns keys: source_url, image_url, thumb_url
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    if not source_url:
        raise RuntimeError("Missing source_url")

    ensure_bucket()
    raw = _download(source_url)
    img = Image.open(io.BytesIO(raw))
    img.load()

    full_bytes = _encode_webp(img, FULL_MAX, FULL_QUALITY)
    thumb_bytes = _encode_webp(img, THUMB_MAX, THUMB_QUALITY)

    full_path = f"full/{wallpaper_id}.webp"
    thumb_path = f"thumb/{wallpaper_id}.webp"
    _upload(full_path, full_bytes)
    _upload(thumb_path, thumb_bytes)

    # cache-bust so browsers pick up replaced objects
    bust = quote(wallpaper_id)[:8]
    return {
        "source_url": source_url,
        "image_url": f"{public_url(full_path)}?v={bust}",
        "thumb_url": f"{public_url(thumb_path)}?v={bust}",
    }


def apply_rehost(item: dict[str, Any]) -> dict[str, Any]:
    """Mutate wallpaper dict with hosted URLs; keep original on failure."""
    wp_id = item.get("id")
    source = item.get("source_url") or item.get("image_url")
    if not wp_id or not source:
        return item
    # Already hosted in our bucket — skip unless thumb missing
    if item.get("thumb_url") and BUCKET in (item.get("image_url") or ""):
        return item
    try:
        urls = rehost_wallpaper(str(wp_id), source)
        item.update(urls)
    except Exception as e:
        print(f"[image_storage] rehost failed for {wp_id}: {e}", flush=True)
        item.setdefault("source_url", source)
    return item
