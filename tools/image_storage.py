"""
Image storage tool — saves user-uploaded images and maintains a JSON database.
"""

import os
import json
from datetime import datetime
from uuid import uuid4

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")
IMAGES_DIR = os.path.join(STORAGE_DIR, "images")
IMAGES_DB_PATH = os.path.join(STORAGE_DIR, "images_db.json")


def _ensure_dirs():
    """Ensure the images directory exists."""
    os.makedirs(IMAGES_DIR, exist_ok=True)


def _load_db() -> list:
    """Load the images database from JSON."""
    if os.path.exists(IMAGES_DB_PATH):
        try:
            with open(IMAGES_DB_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_db(data: list):
    """Persist the images database to JSON instantly."""
    with open(IMAGES_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def _mime_to_extension(mime_type: str) -> str:
    """Map a MIME type to a file extension."""
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/svg+xml": ".svg",
    }
    return mapping.get(mime_type, ".bin")


def save_image(image_bytes: bytes, mime_type: str, user_message: str = "") -> dict:
    """Save an image to storage and record it in the images database.

    Args:
        image_bytes: Raw bytes of the image.
        mime_type: MIME type string (e.g. 'image/png').
        user_message: The user's accompanying text message for context.

    Returns:
        A dict with save result info (filename, path, timestamp).
    """
    _ensure_dirs()

    ext = _mime_to_extension(mime_type)
    timestamp = datetime.now()
    unique_id = uuid4().hex[:8]
    filename = f"img_{timestamp.strftime('%Y%m%d_%H%M%S')}_{unique_id}{ext}"
    filepath = os.path.join(IMAGES_DIR, filename)

    # Write image file to disk
    with open(filepath, "wb") as f:
        f.write(image_bytes)

    # Build record
    record = {
        "id": unique_id,
        "filename": filename,
        "mime_type": mime_type,
        "size_bytes": len(image_bytes),
        "user_message": user_message,
        "saved_at": timestamp.isoformat(),
    }

    # Update JSON database instantly
    db = _load_db()
    db.append(record)
    _save_db(db)

    print(f"\n[SYSTEM] -> Image saved: {filename} ({len(image_bytes)} bytes)")
    print(f"[SYSTEM] -> Images database updated: {len(db)} total images")

    return record


def get_all_images() -> list:
    """Return all image records from the database.

    Returns:
        A list of dicts with image metadata.
    """
    return _load_db()


def get_image_count() -> int:
    """Return the total number of stored images."""
    return len(_load_db())
