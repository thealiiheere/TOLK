import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import APP_VERSION, settings
from app.database import SessionLocal
from app.i18n import MESSAGES, ApiError, lang_from_headers, t
from app.routers import admin, auth, catalog, student, tutor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tolk")

STATIC_DIR = Path(__file__).resolve().parent / "static"

for warning in settings.config_warnings():
    log.warning("CONFIG: %s", warning)

app = FastAPI(
    title="TOLK",
    version=APP_VERSION,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)

if settings.origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Lang"],
    )
app.add_middleware(GZipMiddleware, minimum_size=1024)

# The Mini App runs inside Telegram's iframe (web.telegram.org), so framing is allowed for Telegram only.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://telegram.org",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https://t.me https://*.telegram.org https://*.telesco.pe",
    "frame-src https://oauth.telegram.org",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org",
])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Content-Security-Policy", CSP)
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    path = request.url.path
    if path == "/" or path.startswith("/static/"):
        # Always revalidate (cheap 304s via ETag) so a deploy is picked up immediately, even by ES module imports.
        response.headers["Cache-Control"] = "no-cache"
    elif path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


# ---------- errors: always {"detail": <translated text>, "code": <key>} ----------

@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    lang = lang_from_headers(request.headers)
    return JSONResponse({"detail": t(exc.key, lang, **exc.params), "code": exc.key}, status_code=exc.status_code)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    lang = lang_from_headers(request.headers)
    key = "not_found" if exc.status_code == 404 else str(exc.detail)
    detail = t(key, lang) if key in MESSAGES else str(exc.detail)
    return JSONResponse({"detail": detail, "code": key}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    lang = lang_from_headers(request.headers)
    key = "validation_error"
    fields = []
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
        fields.append(".".join(loc))
        # Custom validators raise ValueError("<i18n key>"), e.g. invalid_meeting_link
        ctx_error = str((err.get("ctx") or {}).get("error", ""))
        if ctx_error in MESSAGES:
            key = ctx_error
    return JSONResponse({"detail": t(key, lang), "code": key, "fields": fields}, status_code=422)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    lang = lang_from_headers(request.headers)
    return JSONResponse({"detail": t("server_error", lang), "code": "server_error"}, status_code=500)


# ---------- routes ----------

for module in (auth, catalog, student, tutor, admin):
    app.include_router(module.router)


@app.get("/api/config")
def public_config():
    """Non-secret settings the frontend needs before sign-in."""
    return {
        "version": APP_VERSION,
        "bot_username": settings.telegram_bot_username,
        "demo_mode": settings.demo_mode,
        "payment_card_number": settings.payment_card_number,
        "payment_card_holder": settings.payment_card_holder,
        "support_contact": settings.support_contact,
        "max_upload_mb": settings.max_upload_mb,
        "meeting_hosts": settings.meeting_hosts,
    }


@app.get("/health")
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        log.exception("Health check: database unavailable")
        return JSONResponse({"status": "error", "database": "unavailable"}, status_code=503)
    return {"status": "ok", "version": APP_VERSION}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")
