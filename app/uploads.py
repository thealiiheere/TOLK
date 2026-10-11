"""Receipt file storage. Files are private: only admins can download them via /api/admin/payments/{id}/receipt."""
import secrets
from pathlib import Path

from fastapi import UploadFile

from app.config import settings
from app.i18n import ApiError

RECEIPTS_DIR_NAME = "receipts"

# Detect the real type from magic bytes instead of trusting the client's filename / content-type.
_SIGNATURES = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"%PDF-", ".pdf"),
)

MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".pdf": "application/pdf"}


def receipts_dir() -> Path:
    path = Path(settings.upload_dir) / RECEIPTS_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _detect_ext(head: bytes) -> str | None:
    for magic, ext in _SIGNATURES:
        if head.startswith(magic):
            return ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


async def save_receipt(file: UploadFile | None) -> str:
    """Validate and store an uploaded receipt. Returns the stored filename."""
    if file is None or not file.filename:
        raise ApiError("receipt_required")
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if not data:
        raise ApiError("receipt_required")
    if len(data) > limit:
        raise ApiError("receipt_too_large", mb=settings.max_upload_mb)
    ext = _detect_ext(data[:16])
    if ext is None:
        raise ApiError("receipt_bad_type")
    name = f"receipt_{secrets.token_hex(12)}{ext}"
    (receipts_dir() / name).write_bytes(data)
    return name


def receipt_path(filename: str) -> Path | None:
    path = receipts_dir() / Path(filename).name  # .name strips any path components
    return path if path.is_file() else None
