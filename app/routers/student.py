from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession, selectinload

from app.auth import require_student
from app.database import get_db
from app.i18n import ApiError
from app.models import Enrollment, Group, HomeworkSubmission, Lesson, LessonRating, LessonRecord, Payment, User, utcnow
from app.notify import notify
from app.schemas import HomeworkIn, RatingIn
from app.services import (
    MAX_STRIKES, admin_recipients, aware, enrolled_counts, group_card, iso, lesson_dict, lesson_end, tutor_ratings,
)
from app.uploads import save_receipt

router = APIRouter(prefix="/api/student", tags=["student"])

RATE_WINDOW_DAYS = 14  # students can rate a lesson for two weeks after it ends


def _ratable(db: DbSession, user: User, lesson: Lesson) -> str | None:
    """Return an error key if the student may not rate this lesson, otherwise None."""
    if lesson.status == "cancelled" or lesson_end(lesson) > utcnow():
        return "lesson_not_completed"
    record = db.scalar(select(LessonRecord).where(LessonRecord.lesson_id == lesson.id, LessonRecord.student_id == user.id))
    if record is not None and not record.attended:
        return "lesson_absent"
    if record is None and db.get(Enrollment, (lesson.group_id, user.id)) is None:
        return "not_enrolled"
    return None


@router.get("/dashboard")
def dashboard(user: User = Depends(require_student), db: DbSession = Depends(get_db)):
    enrollments = db.scalars(
        select(Enrollment)
        .where(Enrollment.student_id == user.id)
        .options(selectinload(Enrollment.group).selectinload(Group.tutor))
    ).all()
    group_ids = [e.group_id for e in enrollments]
    revoked = {e.group_id for e in enrollments if e.strikes >= MAX_STRIKES}
    counts = enrolled_counts(db, group_ids)
    ratings = tutor_ratings(db, {e.group.tutor_id for e in enrollments})

    now = utcnow()
    lessons = db.scalars(
        select(Lesson)
        .where(Lesson.group_id.in_(group_ids), Lesson.starts_at >= now - timedelta(days=RATE_WINDOW_DAYS + 1))
        .order_by(Lesson.starts_at)
    ).all() if group_ids else []
    my_ratings = dict(db.execute(
        select(LessonRating.lesson_id, LessonRating.stars).where(
            LessonRating.student_id == user.id, LessonRating.lesson_id.in_([l.id for l in lessons])
        )
    ).all()) if lessons else {}
    absent = set(db.scalars(
        select(LessonRecord.lesson_id).where(
            LessonRecord.student_id == user.id, LessonRecord.attended.is_(False),
            LessonRecord.lesson_id.in_([l.id for l in lessons]),
        )
    )) if lessons else set()

    titles = {e.group_id: e.group.title for e in enrollments}
    upcoming, to_rate, history = [], [], []
    for lesson in lessons:
        item = lesson_dict(lesson, include_link=lesson.group_id not in revoked)
        item["group_title"] = titles.get(lesson.group_id, "")
        item["my_rating"] = my_ratings.get(lesson.id)
        if lesson.status == "scheduled" and lesson_end(lesson) > now:
            upcoming.append(item)
        elif lesson.status != "cancelled":
            item["meet_link"] = None  # past links are not useful and should not be shared further
            if lesson.id in my_ratings or lesson.id in absent:
                history.append(item)
            elif lesson_end(lesson) >= now - timedelta(days=RATE_WINDOW_DAYS):
                to_rate.append(item)

    classes = []
    for e in enrollments:
        card = group_card(e.group, counts.get(e.group_id, 0), ratings.get(e.group.tutor_id))
        card["strikes"] = e.strikes
        card["access_revoked"] = e.group_id in revoked
        card["joined_at"] = iso(e.joined_at)
        classes.append(card)

    payments = db.scalars(
        select(Payment).where(Payment.student_id == user.id).options(selectinload(Payment.group)).order_by(Payment.id.desc())
    ).all()
    homework = db.scalars(
        select(HomeworkSubmission).where(HomeworkSubmission.student_id == user.id)
        .order_by(HomeworkSubmission.id.desc()).limit(30)
    ).all()

    return {
        "classes": classes,
        "upcoming_lessons": upcoming,
        "to_rate": list(reversed(to_rate)),
        "history": list(reversed(history))[:20],
        "payments": [
            {
                "id": p.id,
                "group_id": p.group_id,
                "group_title": p.group.title if p.group else None,
                "amount": p.amount,
                "status": p.status,
                "admin_comment": p.admin_comment,
                "created_at": iso(p.created_at),
            }
            for p in payments
        ],
        "homework": [
            {
                "id": h.id, "group_id": h.group_id, "group_title": titles.get(h.group_id), "link": h.link,
                "comment": h.comment, "status": h.status, "submitted_at": iso(h.submitted_at),
            }
            for h in homework
        ],
    }


@router.post("/enroll")
async def enroll(
    background: BackgroundTasks,
    group_id: int = Form(...),
    receipt: UploadFile | None = File(None),
    user: User = Depends(require_student),
    db: DbSession = Depends(get_db),
):
    """Student pays by card transfer and uploads the receipt; the admin approves it and enrolls them."""
    group = db.get(Group, group_id)
    if group is None or not group.is_published:
        raise ApiError("group_not_found", 404)
    tutor = group.tutor
    if tutor is None or tutor.tutor_status != "approved":
        raise ApiError("group_unavailable")
    if db.get(Enrollment, (group.id, user.id)) is not None:
        raise ApiError("already_enrolled", 409)
    pending = db.scalar(select(Payment.id).where(
        Payment.student_id == user.id, Payment.group_id == group.id, Payment.status == "pending"
    ))
    if pending is not None:
        raise ApiError("payment_pending_exists", 409)
    if enrolled_counts(db, [group.id]).get(group.id, 0) >= group.max_students:
        raise ApiError("group_full", 409)

    filename = await save_receipt(receipt)
    payment = Payment(student_id=user.id, group_id=group.id, amount=group.price, receipt_filename=filename)
    db.add(payment)
    db.commit()
    background.add_task(
        notify, admin_recipients(db), "n_admin_payment",
        student=user.full_name, group=group.title, amount=f"{group.price:,}".replace(",", " "),
    )
    return {"id": payment.id, "status": payment.status}


@router.post("/lessons/{lesson_id}/rate")
def rate_lesson(lesson_id: int, body: RatingIn, user: User = Depends(require_student), db: DbSession = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise ApiError("lesson_not_found", 404)
    error = _ratable(db, user, lesson)
    if error:
        raise ApiError(error, 403 if error == "not_enrolled" else 400)
    if db.scalar(select(LessonRating.id).where(LessonRating.lesson_id == lesson.id, LessonRating.student_id == user.id)):
        raise ApiError("already_rated", 409)
    tutor_id = lesson.tutor_id or lesson.group.tutor_id
    if tutor_id is None:
        raise ApiError("group_has_no_tutor")
    db.add(LessonRating(
        lesson_id=lesson.id, student_id=user.id, tutor_id=tutor_id, stars=body.stars, comment=body.comment.strip()
    ))
    db.commit()
    return {"ok": True}


@router.post("/homework")
def submit_homework(body: HomeworkIn, user: User = Depends(require_student), db: DbSession = Depends(get_db)):
    enrollment = db.get(Enrollment, (body.group_id, user.id))
    if enrollment is None:
        raise ApiError("not_enrolled", 403)
    if enrollment.strikes >= MAX_STRIKES:
        raise ApiError("access_revoked", 403)
    hw = HomeworkSubmission(student_id=user.id, group_id=body.group_id, link=body.link, comment=body.comment.strip())
    db.add(hw)
    db.commit()
    return {"id": hw.id, "submitted_at": iso(aware(hw.submitted_at))}
