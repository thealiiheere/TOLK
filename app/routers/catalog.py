"""Public class catalog: browsing, filters, class and teacher pages. No sign-in required."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DbSession, selectinload

from app import cache
from app.auth import get_current_user_optional
from app.database import get_db
from app.i18n import ApiError
from app.models import Enrollment, Group, LessonRating, Payment, User
from app.services import enrolled_counts, group_card, review_dict, tutor_card, tutor_ratings
from app.uploads import poster_path

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


def _public_groups():
    """Groups that are visible in the catalog: published and taught by an approved, active teacher."""
    return (
        select(Group)
        .join(User, Group.tutor_id == User.id)
        .where(Group.is_published.is_(True), User.tutor_status == "approved", User.is_blocked.is_(False))
    )


@router.get("/filters")
def filters(db: DbSession = Depends(get_db)):
    """Options for the filter panel, built from what is actually in the catalog."""
    return cache.cached(cache.catalog_key("filters"), cache.CATALOG_TTL, lambda: _filters(db))


def _filters(db: DbSession) -> dict:
    groups = db.scalars(_public_groups()).all()
    languages: dict[str, int] = {}
    others: dict[str, tuple[str, int]] = {}
    for g in groups:
        if g.category == "language":
            languages[g.subject] = languages.get(g.subject, 0) + 1
        else:
            key = g.subject.strip().lower()
            label, n = others.get(key, (g.subject.strip(), 0))
            others[key] = (label, n + 1)
    prices = [g.price for g in groups]
    return {
        "languages": [{"code": c, "count": n} for c, n in sorted(languages.items(), key=lambda x: -x[1])],
        "other_subjects": [{"name": label, "count": n} for label, n in sorted(others.values(), key=lambda x: -x[1])],
        "price_min": min(prices) if prices else 0,
        "price_max": max(prices) if prices else 0,
        "total": len(groups),
    }


@router.get("/groups")
def list_groups(
    db: DbSession = Depends(get_db),
    category: Literal["language", "other"] | None = None,
    subjects: str = Query("", max_length=500, description="Comma-separated subjects / language codes"),
    price_min: int | None = Query(None, ge=0),
    price_max: int | None = Query(None, ge=0),
    min_rating: float | None = Query(None, ge=0, le=5),
    q: str = Query("", max_length=100),
    has_seats: bool = False,
    sort: Literal["rating", "price_asc", "price_desc", "newest"] = "rating",
):
    wanted = sorted({s.strip().lower() for s in subjects.split(",") if s.strip()})
    q = q.strip()
    key = cache.catalog_key("groups", category, ",".join(wanted), price_min, price_max, min_rating, q.lower(), has_seats, sort)
    return cache.cached(key, cache.CATALOG_TTL, lambda: _list_groups(
        db, category, wanted, price_min, price_max, min_rating, q, has_seats, sort,
    ))


def _list_groups(db, category, wanted, price_min, price_max, min_rating, q, has_seats, sort) -> list[dict]:
    rating_sq = (
        select(
            LessonRating.tutor_id.label("tid"),
            func.avg(LessonRating.stars).label("avg"),
            func.count(LessonRating.id).label("cnt"),
        )
        .group_by(LessonRating.tutor_id)
        .subquery()
    )
    count_sq = (
        select(Enrollment.group_id.label("gid"), func.count().label("n")).group_by(Enrollment.group_id).subquery()
    )
    avg = func.coalesce(rating_sq.c.avg, 0)
    stmt = (
        _public_groups()
        .outerjoin(rating_sq, rating_sq.c.tid == Group.tutor_id)
        .outerjoin(count_sq, count_sq.c.gid == Group.id)
        .options(selectinload(Group.tutor))
    )
    if category:
        stmt = stmt.where(Group.category == category)
    if wanted:
        stmt = stmt.where(func.lower(Group.subject).in_(wanted))
    if price_min is not None:
        stmt = stmt.where(Group.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(Group.price <= price_max)
    if min_rating:
        stmt = stmt.where(avg >= min_rating)
    if has_seats:
        stmt = stmt.where(func.coalesce(count_sq.c.n, 0) < Group.max_students)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(
            func.lower(Group.code).like(like),
            func.lower(Group.title).like(like),
            func.lower(Group.subject).like(like),
            func.lower(Group.description).like(like),
            func.lower(User.full_name).like(like),
        ))
    order = {
        "rating": (avg.desc(), func.coalesce(rating_sq.c.cnt, 0).desc(), Group.id.desc()),
        "price_asc": (Group.price.asc(), Group.id.desc()),
        "price_desc": (Group.price.desc(), Group.id.desc()),
        "newest": (Group.id.desc(),),
    }[sort]
    groups = db.scalars(stmt.order_by(*order).limit(200)).unique().all()
    counts = enrolled_counts(db, [g.id for g in groups])
    ratings = tutor_ratings(db, {g.tutor_id for g in groups})
    return [group_card(g, counts.get(g.id, 0), ratings.get(g.tutor_id)) for g in groups]


def _reviews_for_tutor(db: DbSession, tutor_id: int, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        select(LessonRating)
        .where(LessonRating.tutor_id == tutor_id)
        .options(selectinload(LessonRating.student), selectinload(LessonRating.lesson))
        .order_by(LessonRating.id.desc())
        .limit(limit)
    ).all()
    titles = dict(db.execute(select(Group.id, Group.title).where(Group.id.in_({r.lesson.group_id for r in rows}))).all())
    return [review_dict(r, titles.get(r.lesson.group_id)) for r in rows]


def _rating_breakdown(db: DbSession, tutor_id: int) -> dict[int, int]:
    rows = db.execute(
        select(LessonRating.stars, func.count()).where(LessonRating.tutor_id == tutor_id).group_by(LessonRating.stars)
    )
    found = {int(s): int(n) for s, n in rows}
    return {s: found.get(s, 0) for s in range(5, 0, -1)}


@router.get("/groups/{group_id}")
def group_detail(
    group_id: int,
    db: DbSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    # The public part is cached; "my" (enrolled / payment pending) is per visitor and always read fresh.
    data = cache.cached(cache.catalog_key("group", group_id), cache.CATALOG_TTL, lambda: _group_page(db, group_id))
    if data is None and user is not None and user.role == "admin":
        group = db.get(Group, group_id)  # admins may preview unpublished classes (not cached)
        data = _group_page(db, group_id, group) if group is not None else None
    if data is None:
        raise ApiError("group_not_found", 404)

    my = {"enrolled": False, "pending_payment": False, "can_enroll": False}
    if user is not None and user.role == "student" and user.onboarded:
        my["enrolled"] = db.get(Enrollment, (group_id, user.id)) is not None
        my["pending_payment"] = db.scalar(
            select(Payment.id).where(
                Payment.student_id == user.id, Payment.group_id == group_id, Payment.status == "pending"
            )
        ) is not None
        my["can_enroll"] = not my["enrolled"] and not my["pending_payment"] and data["seats_left"] > 0
    return {**data, "my": my}


def _group_page(db: DbSession, group_id: int, group: Group | None = None) -> dict | None:
    """Public class page data, or None when the class isn't in the catalog."""
    if group is None:
        group = db.scalar(_public_groups().where(Group.id == group_id).options(selectinload(Group.tutor)))
    if group is None:
        return None
    enrolled = enrolled_counts(db, [group.id]).get(group.id, 0)
    rating = tutor_ratings(db, [group.tutor_id]).get(group.tutor_id)
    data = group_card(group, enrolled, rating)
    data["reviews"] = _reviews_for_tutor(db, group.tutor_id, 10) if group.tutor_id else []
    data["rating_breakdown"] = _rating_breakdown(db, group.tutor_id) if group.tutor_id else {}
    return data


@router.get("/posters/{name}")
def poster(name: str):
    """Course poster image. Names are random per upload, so the file can be cached forever."""
    path = poster_path(name)
    if path is None:
        raise ApiError("not_found", 404)
    return FileResponse(path, media_type="image/webp", headers={"Cache-Control": "public, max-age=31536000, immutable"})


@router.get("/tutors/{tutor_id}")
def tutor_profile(tutor_id: int, db: DbSession = Depends(get_db)):
    data = cache.cached(cache.catalog_key("tutor", tutor_id), cache.CATALOG_TTL, lambda: _tutor_page(db, tutor_id))
    if data is None:
        raise ApiError("tutor_not_found", 404)
    return data


def _tutor_page(db: DbSession, tutor_id: int) -> dict | None:
    tutor = db.get(User, tutor_id)
    if tutor is None or tutor.role != "tutor" or tutor.tutor_status != "approved" or tutor.is_blocked:
        return None
    rating = tutor_ratings(db, [tutor.id]).get(tutor.id)
    groups = db.scalars(_public_groups().where(Group.tutor_id == tutor.id).options(selectinload(Group.tutor))).all()
    counts = enrolled_counts(db, [g.id for g in groups])
    data = tutor_card(tutor, rating)
    data["groups"] = [group_card(g, counts.get(g.id, 0), rating) for g in groups]
    data["reviews"] = _reviews_for_tutor(db, tutor.id)
    data["rating_breakdown"] = _rating_breakdown(db, tutor.id)
    return data
