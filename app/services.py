"""Shared queries and JSON serializers used by the routers.

Routers return plain dicts built here so the API shape lives in one place.
"""
import re
from datetime import datetime, timedelta, timezone

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.i18n import ApiError
from app.models import Enrollment, Group, Lesson, LessonRating, TutorDocument, User, utcnow
from app.uploads import CERTIFICATES, display_name, media_type, read_upload, write_upload

MAX_STRIKES = 3
MAX_DOCS_PER_UPLOAD = 5
MAX_DOCS_TOTAL = 10


# ---------- datetime helpers ----------

def aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; everything we store is UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def iso(dt: datetime | None) -> str | None:
    dt = aware(dt)
    return dt.isoformat() if dt else None


def lesson_end(lesson: Lesson) -> datetime:
    return aware(lesson.starts_at) + timedelta(minutes=lesson.duration_min or 60)


# ---------- aggregate queries ----------

def tutor_ratings(db: DbSession, tutor_ids=None) -> dict[int, tuple[float, int]]:
    """{tutor_id: (average_stars, ratings_count)}"""
    q = select(LessonRating.tutor_id, func.avg(LessonRating.stars), func.count(LessonRating.id)).group_by(
        LessonRating.tutor_id
    )
    if tutor_ids is not None:
        ids = [i for i in tutor_ids if i]
        if not ids:
            return {}
        q = q.where(LessonRating.tutor_id.in_(ids))
    return {tid: (round(float(avg), 2), int(cnt)) for tid, avg, cnt in db.execute(q)}


def enrolled_counts(db: DbSession, group_ids) -> dict[int, int]:
    ids = list(group_ids)
    if not ids:
        return {}
    q = (
        select(Enrollment.group_id, func.count())
        .where(Enrollment.group_id.in_(ids))
        .group_by(Enrollment.group_id)
    )
    return {gid: int(n) for gid, n in db.execute(q)}


def admin_recipients(db: DbSession) -> list[tuple[int | None, str]]:
    """Telegram chats to notify about admin events (new payments, teacher applications)."""
    rows = db.execute(select(User.telegram_id, User.lang).where(User.role == "admin", User.telegram_id.is_not(None)))
    found = {tid: lang for tid, lang in rows}
    for tid in settings.admin_ids:
        found.setdefault(tid, "uz")
    return list(found.items())


def group_recipients(db: DbSession, group_id: int) -> list[tuple[int | None, str]]:
    rows = db.execute(
        select(User.telegram_id, User.lang)
        .join(Enrollment, Enrollment.student_id == User.id)
        .where(Enrollment.group_id == group_id, Enrollment.strikes < MAX_STRIKES, User.is_blocked.is_(False))
    )
    return [(tid, lang) for tid, lang in rows if tid]


# ---------- course codes ----------

def course_code_prefix(category: str, subject: str) -> str:
    """'en' -> 'EN', 'Mathematics' -> 'MAT', non-latin subjects -> 'CRS'."""
    if category == "language":
        return subject.upper()[:3]
    letters = re.sub(r"[^A-Za-z]", "", subject).upper()
    return letters[:3] if len(letters) >= 2 else "CRS"


def generate_course_code(db: DbSession, category: str, subject: str) -> str:
    """First free code of the form PREFIX-101, PREFIX-102, ..."""
    prefix = course_code_prefix(category, subject)
    taken = set(db.scalars(select(Group.code).where(Group.code.like(f"{prefix}-%"))))
    n = 101
    while f"{prefix}-{n}" in taken:
        n += 1
    return f"{prefix}-{n}"


def ensure_course_code_free(db: DbSession, code: str, group_id: int | None = None) -> None:
    q = select(Group.id).where(Group.code == code)
    if group_id is not None:
        q = q.where(Group.id != group_id)
    if db.scalar(q) is not None:
        raise ApiError("course_code_taken", 409, code=code)


# ---------- teacher certificates ----------

async def add_tutor_documents(db: DbSession, tutor: User, files: list[UploadFile]) -> list[TutorDocument]:
    """Validate every file first, then store them all (so a bad file never leaves half an upload behind)."""
    files = [f for f in files if f is not None and f.filename]
    if not files:
        raise ApiError("certificates_required")
    if len(files) > MAX_DOCS_PER_UPLOAD or len(tutor.documents) + len(files) > MAX_DOCS_TOTAL:
        raise ApiError("too_many_documents", per_upload=MAX_DOCS_PER_UPLOAD, total=MAX_DOCS_TOTAL)
    validated = [(f, *await read_upload(f, "certificates_required")) for f in files]
    docs = []
    for f, data, ext in validated:
        doc = TutorDocument(filename=write_upload(CERTIFICATES, data, ext), original_name=display_name(f.filename))
        tutor.documents.append(doc)  # keeps the already-loaded collection in sync (sessions don't expire on commit)
        docs.append(doc)
    return docs


def document_dict(d: TutorDocument) -> dict:
    return {"id": d.id, "name": d.original_name, "content_type": media_type(d.filename), "created_at": iso(d.created_at)}


# ---------- serializers ----------

def user_me(u: User) -> dict:
    return {
        "id": u.id,
        "full_name": u.full_name,
        "role": u.role,
        "lang": u.lang,
        "onboarded": u.onboarded,
        "phone": u.phone or "",
        "telegram_username": u.telegram_username,
        "photo_url": u.photo_url,
        "bio": u.bio or "",
        "subjects": u.tutor_subjects or "",
        "tutor_status": u.tutor_status,
        "tutor_review_note": u.tutor_review_note or "",
        "is_demo": u.is_demo,
    }


def user_brief(u: User | None) -> dict | None:
    if u is None:
        return None
    return {"id": u.id, "full_name": u.full_name, "photo_url": u.photo_url, "telegram_username": u.telegram_username}


def tutor_card(u: User | None, rating: tuple[float, int] | None) -> dict | None:
    if u is None:
        return None
    avg, cnt = rating or (None, 0)
    return {
        "id": u.id,
        "full_name": u.full_name,
        "photo_url": u.photo_url,
        "telegram_username": u.telegram_username,
        "bio": u.bio or "",
        "subjects": u.tutor_subjects or "",
        "rating": avg,
        "ratings_count": cnt,
    }


def group_card(g: Group, enrolled: int, rating: tuple[float, int] | None) -> dict:
    return {
        "id": g.id,
        "code": g.code,
        "title": g.title,
        "category": g.category,
        "subject": g.subject,
        "level": g.level,
        "description": g.description,
        "price": g.price,
        "price_period": g.price_period,
        "schedule": g.schedule,
        "max_students": g.max_students,
        "enrolled": enrolled,
        "seats_left": max(0, g.max_students - enrolled),
        "is_published": g.is_published,
        "poster_url": f"/api/catalog/posters/{g.poster}" if g.poster else None,
        "tutor": tutor_card(g.tutor, rating),
    }


def lesson_dict(lesson: Lesson, include_link: bool) -> dict:
    now = utcnow()
    end = lesson_end(lesson)
    return {
        "id": lesson.id,
        "group_id": lesson.group_id,
        "starts_at": iso(lesson.starts_at),
        "ends_at": iso(end),
        "duration_min": lesson.duration_min,
        "topic": lesson.topic,
        "status": lesson.status,
        "is_live": lesson.status == "scheduled" and aware(lesson.starts_at) <= now < end,
        "meet_link": lesson.meet_link if include_link else None,
    }


def review_dict(r: LessonRating, group_title: str | None = None) -> dict:
    first_name = (r.student.full_name.split() or ["—"])[0] if r.student else "—"
    return {
        "id": r.id,
        "stars": r.stars,
        "comment": r.comment,
        "student_name": first_name,
        "group_title": group_title,
        "created_at": iso(r.created_at),
    }
