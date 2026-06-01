"""缩略图生成与管理。"""

from pathlib import Path

from PIL import Image


THUMBNAIL_DIR = Path(__file__).parent.parent / "data" / "thumbnails"
IMAGE_DIR = Path(__file__).parent.parent / "data" / "images"


def get_thumbnail_path(pattern_id: str) -> Path:
    return THUMBNAIL_DIR / f"{pattern_id}.png"


def get_image_path(pattern_id: str) -> Path:
    return IMAGE_DIR / f"{pattern_id}.png"


def generate_thumbnail(source_image: Path, pattern_id: str, size: int = 100) -> Path:
    """从原始图片生成缩略图并保存。"""
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    thumb_path = get_thumbnail_path(pattern_id)

    img = Image.open(source_image).convert("RGB")
    img.thumbnail((size, size))
    img.save(thumb_path, "PNG")
    return thumb_path


def thumbnail_exists(pattern_id: str) -> bool:
    return get_thumbnail_path(pattern_id).exists()
