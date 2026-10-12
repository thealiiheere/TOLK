"""Authentication: Telegram Mini App initData / Login Widget verification, sessions, role guards."""
import hashlib
import hmac
import json
import secrets
import time
from datetime import timedelta
from urllib.parse import parse_qsl

from fastapi import Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.database import get_db
from app.i18n import ApiError
from app.models import Session, User, utcnow


# ---------- Telegram signature checks ----------

def verify_webapp_init_data(init_data: str, bot_token: str, max_age_seconds: int) -> dict:
    """Validate Telegram Mini App initData (https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app).

    Returns the parsed Telegram user dict. Raises ApiError on any mismatch.
    """
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        raise ApiError("tg_auth_invalid", 401)
    received_hash = pairs.pop("hash", "")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not received_hash or not hmac.compare_digest(expected, received_hash):
        raise ApiError("tg_auth_invalid", 401)
    _check_auth_date(pairs.get("auth_date"), max_age_seconds)
    try:
        user = json.loads(pairs["user"])
        int(user["id"])
    except (KeyError, ValueError, TypeError):
        raise ApiError("tg_auth_invalid", 401)
    return user


def verify_login_widget(data: dict, bot_token: str, max_age_seconds: int) -> dict:
    """Validate Telegram Login Widget data (https://core.telegram.org/widgets/login#checking-authorization)."""
    fields = {k: v for k, v in data.items() if v is not None and k != "hash"}
    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hashlib.sha256(bot_token.encode()).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(data.get("hash", ""))):
        raise ApiError("tg_auth_invalid", 401)
    _check_auth_date(fields.get("auth_date"), max_age_seconds)
    return fields


def _check_auth_date(auth_date, max_age_seconds: int) -> None:
    try:
        age = time.time() - int(auth_date)
    except (TypeError, ValueError):
        raise ApiError("tg_auth_invalid", 401)
    if age > max_age_seconds:
        raise ApiError("tg_auth_expired", 401)


def upsert_telegram_user(db: DbSession, tg: dict) -> User:
    """Find or create the user for a verified Telegram identity."""
    tg_id = int(tg["id"])
    username = f"@{tg['username']}" if tg.get("username") else None
    user = db.scalar(select(User).where(User.telegram_id == tg_id))
    if user is None:
        name = " ".join(filter(None, [tg.get("first_name"), tg.get("last_name")])).strip() or f"User {tg_id}"
        lang = (tg.get("language_code") or "")[:2]
        user = User(
            telegram_id=tg_id,
            full_name=name[:120],
            lang=lang if lang in ("uz", "ru", "en") else "uz",
            role="student",
            onboarded=False,
        )
        db.add(user)
    user.telegram_username = username
    photo = tg.get("photo_url")
    if isinstance(photo, str) and photo.startswith("https://") and len(photo) <= 500:
        user.photo_url = photo
    if tg_id in settings.admin_ids:
        user.role = "admin"
        user.onboarded = True
        user.tutor_status = None
    db.commit()
    db.refresh(user)
    return user


# ---------- sessions ----------

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: DbSession, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(Session(
        token_hash=_hash_token(token),
        user_id=user.id,
        expires_at=utcnow() + timedelta(days=settings.session_ttl_days),
    ))
    # Opportunistic cleanup of this user's expired sessions
    db.execute(delete(Session).where(Session.user_id == user.id, Session.expires_at < utcnow()))
    db.commit()
    return token


def delete_session(db: DbSession, token: str) -> None:
    db.execute(delete(Session).where(Session.token_hash == _hash_token(token)))
    db.commit()


def bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


def get_current_user_optional(request: Request, db: DbSession = Depends(get_db)) -> User | None:
    token = bearer_token(request)
    if not token:
        return None
    session = db.get(Session, _hash_token(token))
    if session is None:
        return None
    expires = session.expires_at
    if expires.tzinfo is None:  # SQLite returns naive datetimes
        expires = expires.replace(tzinfo=utcnow().tzinfo)
    if expires < utcnow():
        db.delete(session)
        db.commit()
        return None
    user = session.user
    if user.telegram_id in settings.admin_ids and user.role != "admin":
        # ADMIN_TELEGRAM_IDS changed while this user was signed in: apply it now instead of at the next sign-in
        user.role, user.onboarded, user.tutor_status = "admin", True, None
        db.commit()
    return user


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    if user is None:
        raise ApiError("auth_required", 401)
    if user.is_blocked:
        raise ApiError("account_blocked", 403)
    return user


def require_onboarded(user: User = Depends(get_current_user)) -> User:
    if not user.onboarded:
        raise ApiError("onboarding_required", 403)
    return user


def require_admin(user: User = Depends(require_onboarded)) -> User:
    if user.role != "admin":
        raise ApiError("forbidden", 403)
    return user


def require_tutor(user: User = Depends(require_onboarded)) -> User:
    """Any tutor, including ones still waiting for approval."""
    if user.role != "tutor":
        raise ApiError("forbidden", 403)
    return user


def require_approved_tutor(user: User = Depends(require_tutor)) -> User:
    if user.tutor_status != "approved":
        raise ApiError("tutor_not_approved", 403)
    return user


def require_student(user: User = Depends(require_onboarded)) -> User:
    if user.role != "student":
        raise ApiError("forbidden", 403)
    return user
