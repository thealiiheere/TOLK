from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session as DbSession, selectinload

from app.auth import require_admin
from app.database import get_db
from app.i18n import ApiError
from app.models import Enrollment, Group, Lesson, LessonRating, Payment, Session, TutorDocument, User, utcnow
from app.notify import notify
from app.routers.tutor import apply_strike
from app.schemas import AssignStudentIn, BlockIn, GroupIn, PaymentReviewIn, StrikeIn, TutorDecisionIn
from app.services import (
    MAX_STRIKES, document_dict, enrolled_counts, ensure_course_code_free, generate_course_code, group_card, iso,
    tutor_card, tutor_ratings, user_brief,
)
from app.uploads import CERTIFICATES, MEDIA_TYPES, media_type, receipt_path, stored_path

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _recipient(user: User | None) -> list[tuple[int | None, str]]:
    return [(user.telegram_id, user.lang)] if user and user.telegram_id else []


def _approved_tutor(db: DbSession, tutor_id: int | None) -> User | None:
    if tutor_id is None:
        return None
    tutor = db.get(User, tutor_id)
    if tutor is None or tutor.role != "tutor" or tutor.tutor_status != "approved":
        raise ApiError("tutor_not_found", 404)
    return tutor


def _enroll(db: DbSession, group: Group, student: User) -> None:
    if db.get(Enrollment, (group.id, student.id)) is not None:
        return
    if enrolled_counts(db, [group.id]).get(group.id, 0) >= group.max_students:
        raise ApiError("group_full", 409)
    db.add(Enrollment(group_id=group.id, student_id=student.id))


# ---------- overview ----------

@router.get("/stats")
def stats(_: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    def count(stmt):
        return int(db.scalar(stmt) or 0)  # SUM() is Decimal on PostgreSQL

    now = utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    avg = db.scalar(select(func.avg(LessonRating.stars)))
    return {
        "students": count(select(func.count()).select_from(User).where(User.role == "student", User.onboarded.is_(True))),
        "tutors": count(select(func.count()).select_from(User).where(User.role == "tutor", User.tutor_status == "approved")),
        "pending_tutors": count(select(func.count()).select_from(User).where(User.role == "tutor", User.tutor_status == "pending")),
        "groups": count(select(func.count()).select_from(Group)),
        "enrollments": count(select(func.count()).select_from(Enrollment)),
        "pending_payments": count(select(func.count()).select_from(Payment).where(Payment.status == "pending")),
        "violations": count(select(func.count()).select_from(Enrollment).where(Enrollment.strikes >= MAX_STRIKES)),
        "upcoming_lessons": count(select(func.count()).select_from(Lesson).where(Lesson.status == "scheduled", Lesson.starts_at >= now)),
        "revenue_month": count(select(func.sum(Payment.amount)).where(Payment.status == "approved", Payment.reviewed_at >= month_start)),
        "revenue_total": count(select(func.sum(Payment.amount)).where(Payment.status == "approved")),
        "avg_rating": round(float(avg), 2) if avg is not None else None,
    }


# ---------- payments ----------

@router.get("/payments")
def list_payments(
    status: Literal["pending", "approved", "rejected", "all"] = "pending",
    _: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    stmt = select(Payment).options(selectinload(Payment.student), selectinload(Payment.group)).order_by(Payment.id.desc())
    if status != "all":
        stmt = stmt.where(Payment.status == status)
    payments = db.scalars(stmt.limit(300)).all()
    counts = enrolled_counts(db, {p.group_id for p in payments if p.group_id})
    return [
        {
            "id": p.id,
            "amount": p.amount,
            "status": p.status,
            "admin_comment": p.admin_comment,
            "created_at": iso(p.created_at),
            "reviewed_at": iso(p.reviewed_at),
            "receipt_type": MEDIA_TYPES.get("." + p.receipt_filename.rsplit(".", 1)[-1], "application/octet-stream"),
            "student": {**user_brief(p.student), "phone": p.student.phone or ""},
            "group": {
                "id": p.group.id, "code": p.group.code, "title": p.group.title, "price": p.group.price,
                "seats_left": max(0, p.group.max_students - counts.get(p.group.id, 0)),
            } if p.group else None,
        }
        for p in payments
    ]


@router.get("/payments/{payment_id}/receipt")
def payment_receipt(payment_id: int, _: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    payment = db.get(Payment, payment_id)
    path = receipt_path(payment.receipt_filename) if payment else None
    if path is None:
        raise ApiError("payment_not_found", 404)
    return FileResponse(
        path, media_type=MEDIA_TYPES.get(path.suffix, "application/octet-stream"),
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/payments/{payment_id}/review")
def review_payment(
    payment_id: int,
    body: PaymentReviewIn,
    background: BackgroundTasks,
    _: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise ApiError("payment_not_found", 404)
    if payment.status != "pending":
        raise ApiError("payment_already_reviewed", 409)
    group = payment.group
    if body.status == "approved":
        if group is None:
            raise ApiError("group_not_found", 404)
        _enroll(db, group, payment.student)
    payment.status = body.status
    payment.admin_comment = body.comment.strip()
    payment.reviewed_at = utcnow()
    db.commit()
    title = group.title if group else "—"
    if body.status == "approved":
        background.add_task(notify, _recipient(payment.student), "n_payment_approved", group=title)
    else:
        background.add_task(notify, _recipient(payment.student), "n_payment_rejected", group=title, comment=payment.admin_comment)
    return {"ok": True}


# ---------- groups (classes) ----------

def _group_admin_dict(db: DbSession, g: Group, count: int, rating) -> dict:
    card = group_card(g, count, rating)
    card["students"] = [
        {**user_brief(e.student), "strikes": e.strikes, "joined_at": iso(e.joined_at)}
        for e in sorted(g.enrollments, key=lambda e: e.student.full_name.lower())
    ]
    next_lesson = db.scalar(
        select(Lesson).where(Lesson.group_id == g.id, Lesson.status == "scheduled", Lesson.starts_at >= utcnow())
        .order_by(Lesson.starts_at)
    )
    card["next_lesson_at"] = iso(next_lesson.starts_at) if next_lesson else None
    return card


@router.get("/groups")
def list_groups(_: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    groups = db.scalars(
        select(Group).options(
            selectinload(Group.tutor), selectinload(Group.enrollments).selectinload(Enrollment.student)
        ).order_by(Group.id.desc())
    ).all()
    ratings = tutor_ratings(db, {g.tutor_id for g in groups})
    return [_group_admin_dict(db, g, len(g.enrollments), ratings.get(g.tutor_id)) for g in groups]


@router.post("/groups")
def create_group(
    body: GroupIn, background: BackgroundTasks, _: User = Depends(require_admin), db: DbSession = Depends(get_db),
):
    tutor = _approved_tutor(db, body.tutor_id)
    data = body.model_dump()
    if data["code"]:
        ensure_course_code_free(db, data["code"])
    else:
        data["code"] = generate_course_code(db, body.category, body.subject)
    group = Group(**data)
    db.add(group)
    db.commit()
    if tutor:
        background.add_task(notify, _recipient(tutor), "n_group_assigned", group=group.title)
    return {"id": group.id, "code": group.code}


@router.put("/groups/{group_id}")
def update_group(
    group_id: int, body: GroupIn, background: BackgroundTasks,
    _: User = Depends(require_admin), db: DbSession = Depends(get_db),
):
    group = db.get(Group, group_id)
    if group is None:
        raise ApiError("group_not_found", 404)
    tutor = _approved_tutor(db, body.tutor_id) if body.tutor_id != group.tutor_id else None
    if body.max_students < len(group.enrollments):
        raise ApiError("max_below_enrolled", n=len(group.enrollments))
    data = body.model_dump()
    if not data["code"]:
        data["code"] = group.code  # empty field on edit = keep the current code
    elif data["code"] != group.code:
        ensure_course_code_free(db, data["code"], group.id)
    for key, value in data.items():
        setattr(group, key, value)
    db.commit()
    if tutor:
        background.add_task(notify, _recipient(tutor), "n_group_assigned", group=group.title)
    return {"id": group.id, "code": group.code}


@router.delete("/groups/{group_id}")
def delete_group(group_id: int, _: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    group = db.get(Group, group_id)
    if group is None:
        raise ApiError("group_not_found", 404)
    db.delete(group)
    db.commit()
    return {"ok": True}


@router.post("/groups/{group_id}/students")
def add_student(group_id: int, body: AssignStudentIn, _: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    group = db.get(Group, group_id)
    if group is None:
        raise ApiError("group_not_found", 404)
    student = db.get(User, body.student_id)
    if student is None or student.role != "student":
        raise ApiError("student_not_found", 404)
    if db.get(Enrollment, (group.id, student.id)) is not None:
        raise ApiError("already_enrolled_admin", 409)
    _enroll(db, group, student)
    db.commit()
    return {"ok": True}


@router.delete("/groups/{group_id}/students/{student_id}")
def remove_student(group_id: int, student_id: int, _: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    db.execute(delete(Enrollment).where(Enrollment.group_id == group_id, Enrollment.student_id == student_id))
    db.commit()
    return {"ok": True}


# ---------- teachers ----------

@router.get("/tutors")
def list_tutors(_: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    tutors = db.scalars(
        select(User).where(User.role == "tutor").options(selectinload(User.documents)).order_by(User.id.desc())
    ).all()
    ratings = tutor_ratings(db, [t.id for t in tutors])
    group_counts = dict(db.execute(
        select(Group.tutor_id, func.count()).where(Group.tutor_id.is_not(None)).group_by(Group.tutor_id)
    ).all())
    order = {"pending": 0, "approved": 1, "rejected": 2}
    tutors = sorted(tutors, key=lambda t: order.get(t.tutor_status or "", 3))
    return [
        {
            **tutor_card(t, ratings.get(t.id)),
            "tutor_status": t.tutor_status,
            "phone": t.phone or "",
            "is_blocked": t.is_blocked,
            "groups_count": group_counts.get(t.id, 0),
            "created_at": iso(t.created_at),
            "review_note": t.tutor_review_note or "",
            "documents": [document_dict(d) for d in t.documents],
        }
        for t in tutors
    ]


@router.get("/tutors/{tutor_id}/documents/{doc_id}")
def tutor_document(tutor_id: int, doc_id: int, _: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    doc = db.get(TutorDocument, doc_id)
    path = stored_path(CERTIFICATES, doc.filename) if doc is not None and doc.tutor_id == tutor_id else None
    if path is None:
        raise ApiError("document_not_found", 404)
    return FileResponse(path, media_type=media_type(path.name), headers={"Cache-Control": "private, no-store"})


@router.post("/tutors/{tutor_id}/decision")
def tutor_decision(
    tutor_id: int, body: TutorDecisionIn, background: BackgroundTasks,
    _: User = Depends(require_admin), db: DbSession = Depends(get_db),
):
    tutor = db.get(User, tutor_id)
    if tutor is None or tutor.role != "tutor":
        raise ApiError("tutor_not_found", 404)
    if body.status == "approved" and not tutor.documents:
        raise ApiError("tutor_no_documents")
    tutor.tutor_status = body.status
    tutor.tutor_review_note = body.comment.strip()
    db.commit()
    if body.status == "approved":
        background.add_task(notify, _recipient(tutor), "n_tutor_approved")
    else:
        background.add_task(notify, _recipient(tutor), "n_tutor_rejected", reason=tutor.tutor_review_note)
    return {"ok": True}


# ---------- users & discipline ----------

@router.get("/users")
def list_users(
    role: Literal["student", "tutor", "admin", "all"] = "all",
    q: str = Query("", max_length=100),
    _: User = Depends(require_admin),
    db: DbSession = Depends(get_db),
):
    stmt = select(User).where(User.onboarded.is_(True)).options(selectinload(User.enrollments)).order_by(User.id.desc())
    if role != "all":
        stmt = stmt.where(User.role == role)
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(
            func.lower(User.full_name).like(like),
            func.lower(func.coalesce(User.telegram_username, "")).like(like),
            func.coalesce(User.phone, "").like(like),
        ))
    return [
        {
            **user_brief(u),
            "role": u.role,
            "phone": u.phone or "",
            "is_blocked": u.is_blocked,
            "tutor_status": u.tutor_status,
            "group_ids": [e.group_id for e in u.enrollments],
            "created_at": iso(u.created_at),
        }
        for u in db.scalars(stmt.limit(300))
    ]


@router.post("/users/{user_id}/block")
def block_user(user_id: int, body: BlockIn, admin: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise ApiError("user_not_found", 404)
    if user.role == "admin" or user.id == admin.id:
        raise ApiError("cannot_block_admin")
    user.is_blocked = body.is_blocked
    if body.is_blocked:
        db.execute(delete(Session).where(Session.user_id == user.id))
    db.commit()
    return {"ok": True}


@router.get("/violations")
def violations(_: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    rows = db.scalars(
        select(Enrollment).where(Enrollment.strikes >= MAX_STRIKES - 1)
        .options(selectinload(Enrollment.student), selectinload(Enrollment.group).selectinload(Group.tutor))
        .order_by(Enrollment.strikes.desc())
    ).all()
    return [
        {
            "student": user_brief(e.student),
            "group": {"id": e.group.id, "title": e.group.title},
            "tutor": user_brief(e.group.tutor),
            "strikes": e.strikes,
            "access_revoked": e.strikes >= MAX_STRIKES,
        }
        for e in rows
    ]


@router.post("/strikes")
def strike_action(body: StrikeIn, _: User = Depends(require_admin), db: DbSession = Depends(get_db)):
    enrollment = db.get(Enrollment, (body.group_id, body.student_id))
    if enrollment is None:
        raise ApiError("student_not_found", 404)
    apply_strike(enrollment, body.action)
    db.commit()
    return {"strikes": enrollment.strikes}
