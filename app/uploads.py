"""File storage: payment receipts and teacher certificates (private) and course posters (public).

Private files never go through a public URL: admins download them through authenticated endpoints
(/api/admin/payments/{id}/receipt, /api/admin/tutors/{id}/documents/{doc_id}).
Posters are public (/api/catalog/posters/{name}) and are always re-encoded, never served as uploaded.
"""
import io
import re
import secrets
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps

from app.config import settings
from app.i18n import ApiError

RECEIPTS = "receipts"
CERTIFICATES = "certificates"
POSTERS = "posters"

POSTER_MAX_SIZE = (1280, 800)
POSTER_NAME_RE = re.compile(r"^poster_[0-9a-f]{24}\.webp$")
Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse decompression bombs early

# Detect the real type from magic bytes instead of trusting the client's filename / content-type.
_SIGNATURES = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"%PDF-", ".pdf"),
)

MEDIA_TYPES = {".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".pdf": "application/pdf"}


def upload_dir(kind: str) -> Path:
    path = Path(settings.upload_dir) / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def receipts_dir() -> Path:
    return upload_dir(RECEIPTS)


def _detect_ext(head: bytes) -> str | None:
    for magic, ext in _SIGNATURES:
        if head.startswith(magic):
            return ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


def media_type(filename: str) -> str:
    return MEDIA_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")


def display_name(filename: str | None) -> str:
    """A safe, short label for a client-supplied filename (only ever shown as escaped text)."""
    name = Path(filename or "").name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:160] or "file"


async def read_upload(file: UploadFile | None, missing_key: str) -> tuple[bytes, str]:
    """Read and validate one upload. Returns (data, extension). Nothing is written to disk."""
    if file is None or not file.filename:
        raise ApiError(missing_key)
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if not data:
        raise ApiError(missing_key)
    if len(data) > limit:
        raise ApiError("receipt_too_large", mb=settings.max_upload_mb)
    ext = _detect_ext(data[:16])
    if ext is None:
        raise ApiError("receipt_bad_type")
    return data, ext


def write_upload(kind: str, data: bytes, ext: str) -> str:
    name = f"{kind[:-1]}_{secrets.token_hex(12)}{ext}"
    (upload_dir(kind) / name).write_bytes(data)
    return name


async def save_receipt(file: UploadFile | None) -> str:
    """Validate and store an uploaded receipt. Returns the stored filename."""
    data, ext = await read_upload(file, "receipt_required")
    return write_upload(RECEIPTS, data, ext)


async def save_poster(file: UploadFile | None) -> str:
    """Validate an image and store a re-encoded copy: resized to fit POSTER_MAX_SIZE, EXIF (incl. GPS) stripped,
    saved as WEBP. Re-encoding also guarantees we never serve the uploaded bytes themselves."""
    data, ext = await read_upload(file, "poster_required")
    if ext == ".pdf":
        raise ApiError("poster_bad_type")
    try:
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
            img.thumbnail(POSTER_MAX_SIZE, Image.Resampling.LANCZOS)
            out = io.BytesIO()
            img.save(out, "WEBP", quality=82, method=4)
    except (OSError, ValueError, Image.DecompressionBombError):
        raise ApiError("poster_bad_type") from None
    return write_upload(POSTERS, out.getvalue(), ".webp")


def poster_path(name: str) -> Path | None:
    if not POSTER_NAME_RE.match(name):
        return None
    return stored_path(POSTERS, name)


def stored_path(kind: str, filename: str) -> Path | None:
    path = upload_dir(kind) / Path(filename).name  # .name strips any path components
    return path if path.is_file() else None


def receipt_path(filename: str) -> Path | None:
    return stored_path(RECEIPTS, filename)


def delete_stored(kind: str, filename: str) -> None:
    path = stored_path(kind, filename)
    if path:
        path.unlink(missing_ok=True)
