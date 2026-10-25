from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import case, select
from sqlalchemy.orm import Session as DbSession

from app.auth import (
    bearer_token, create_session, delete_session, get_current_user, upsert_telegram_user,
    verify_login_widget, verify_webapp_init_data,
)
from app import ratelimit
from app.config import settings
from app.database import get_db
from app.i18n import ApiError
from app.models import User
from app.notify import notify
from app.schemas import DemoLoginIn, OnboardingIn, ProfileUpdateIn, TelegramAuthIn, TelegramWidgetIn
from app.services import add_tutor_documents, admin_recipients, user_me

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _login_response(db: DbSession, user: User) -> dict:
    if user.is_blocked:
        raise ApiError("account_blocked", 403)
    return {"token": create_session(db, user), "user": user_me(user)}


def _require_bot_token() -> str:
    if not settings.telegram_bot_token:
        raise ApiError("tg_not_configured", 503)
    return settings.telegram_bot_token


@router.post("/telegram")
def telegram_webapp_login(body: TelegramAuthIn, request: Request, db: DbSession = Depends(get_db)):
    """Sign in from inside the Telegram Mini App using the signed initData string."""
    ratelimit.check("signin", ratelimit.client_ip(request))
    tg = verify_webapp_init_data(
        body.init_data, _require_bot_token(), settings.telegram_auth_max_age_hours * 3600
    )
    return _login_response(db, upsert_telegram_user(db, tg))


@router.post("/telegram-widget")
def telegram_widget_login(body: TelegramWidgetIn, request: Request, db: DbSession = Depends(get_db)):
    """Sign in from a regular browser via the Telegram Login Widget."""
    ratelimit.check("signin", ratelimit.client_ip(request))
    tg = verify_login_widget(
        body.model_dump(), _require_bot_token(), settings.telegram_auth_max_age_hours * 3600
    )
    return _login_response(db, upsert_telegram_user(db, tg))


@router.get("/demo-users")
def demo_users(db: DbSession = Depends(get_db)):
    if not settings.demo_mode:
        raise ApiError("demo_disabled", 404)
    order = case({"admin": 0, "tutor": 1, "student": 2}, value=User.role)
    users = db.scalars(select(User).where(User.is_demo.is_(True)).order_by(order, User.id))
    return [
        {"id": u.id, "full_name": u.full_name, "role": u.role, "tutor_status": u.tutor_status, "is_blocked": u.is_blocked}
        for u in users
    ]


@router.post("/demo-login")
def demo_login(body: DemoLoginIn, request: Request, db: DbSession = Depends(get_db)):
    if not settings.demo_mode:
        raise ApiError("demo_disabled", 404)
    ratelimit.check("signin", ratelimit.client_ip(request))
    user = db.get(User, body.user_id)
    if user is None or not user.is_demo:
        raise ApiError("user_not_found", 404)
    return _login_response(db, user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_me(user)


@router.post("/onboarding")
async def onboarding(
    background: BackgroundTasks,
    role: str = Form(...),
    full_name: str = Form(...),
    phone: str = Form(""),
    bio: str = Form(""),
    subjects: str = Form(""),
    certificates: list[UploadFile] = File(default=[]),
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """First-time sign-up (multipart form): the user picks Student or Teacher.

    Teachers must attach at least one certificate / diploma and then wait for admin approval.
    """
    ratelimit.check("onboarding", user.id)
    # (A Form() model can't be combined with File() params in FastAPI, so the model is built here.)
    try:
        body = OnboardingIn(role=role, full_name=full_name, phone=phone, bio=bio, subjects=subjects)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from None
    if user.onboarded:
        raise ApiError("already_onboarded", 409)
    if body.role == "tutor":
        if len(body.bio) < 20 or not body.subjects:
            raise ApiError("tutor_profile_incomplete")
        docs = await add_tutor_documents(db, user, certificates)  # validates before anything is saved
    user.full_name = body.full_name
    user.phone = body.phone or None
    user.role = body.role
    user.onboarded = True
    if body.role == "tutor":
        user.bio = body.bio
        user.tutor_subjects = body.subjects
        user.tutor_status = "pending"
    db.commit()
    if body.role == "tutor":
        background.add_task(notify, admin_recipients(db), "n_admin_tutor", name=user.full_name, n=len(docs))
    return user_me(user)


@router.patch("/me")
def update_profile(body: ProfileUpdateIn, user: User = Depends(get_current_user), db: DbSession = Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if data.get("full_name"):
        user.full_name = data["full_name"].strip()
    if "phone" in data and data["phone"] is not None:
        user.phone = data["phone"].strip() or None
    if data.get("lang"):
        user.lang = data["lang"]
    if user.role == "tutor":
        if data.get("bio") is not None:
            user.bio = data["bio"].strip()
        if data.get("subjects") is not None:
            user.tutor_subjects = data["subjects"].strip()
    db.commit()
    return user_me(user)


@router.post("/logout")
def logout(request: Request, db: DbSession = Depends(get_db)):
    token = bearer_token(request)
    if token:
        delete_session(db, token)
    return {"ok": True}
