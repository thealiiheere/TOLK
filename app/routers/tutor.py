from datetime import timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession, selectinload

from app import ratelimit
from app.auth import require_approved_tutor, require_tutor
from app.database import get_db
from app.i18n import ApiError
from app.models import Enrollment, Group, HomeworkSubmission, Lesson, LessonRating, LessonRecord, User, utcnow
from app.notify import notify
from app.schemas import LessonCompleteIn, LessonCreateIn, LessonUpdateIn, StrikeIn
from app.services import (
    MAX_STRIKES, add_tutor_documents, admin_recipients, aware, document_dict, enrolled_counts, group_card, group_recipients, iso, lesson_dict, lesson_end, review_dict,
    tutor_ratings,
)

router = APIRouter(prefix="/api/tutor", tags=["tutor"])

MAX_SCHEDULE_AHEAD = timedelta(days=180)
SCHEDULE_GRACE = timedelta(hours=1)  # allow logging a lesson that started a moment ago


def _own_group(db: DbSession, tutor: User, group_id: int) -> Group:
    group = db.get(Group, group_id)
    if group is None or group.tutor_id != tutor.id:
        raise ApiError("group_not_found", 404)
    return group


def _own_lesson(db: DbSession, tutor: User, lesson_id: int) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None or lesson.group.tutor_id != tutor.id:
        raise ApiError("lesson_not_found", 404)
    return lesson


def _check_start(starts_at):
    starts_at = aware(starts_at).astimezone(timezone.utc)
    now = utcnow()
    if starts_at < now - SCHEDULE_GRACE or starts_at > now + MAX_SCHEDULE_AHEAD:
        raise ApiError("lesson_time_invalid")
    return starts_at


def _check_new_link(db: DbSession, group_id: int, link: str, exclude_lesson_id: int | None = None) -> None:
    """Every lesson needs its own fresh meeting link: reject links already used in this class."""
    q = select(Lesson.id).where(Lesson.group_id == group_id, Lesson.meet_link == link, Lesson.status != "cancelled")
    if exclude_lesson_id:
        q = q.where(Lesson.id != exclude_lesson_id)
    if db.scalar(q) is not None:
        raise ApiError("meeting_link_reused")


@router.get("/dashboard")
def dashboard(tutor: User = Depends(require_tutor), db: DbSession = Depends(get_db)):
    rating = tutor_ratings(db, [tutor.id]).get(tutor.id)
    breakdown = dict(db.execute(
        select(LessonRating.stars, func.count()).where(LessonRating.tutor_id == tutor.id).group_by(LessonRating.stars)
    ).all())
    result = {
        "tutor_status": tutor.tutor_status,
        "tutor_review_note": tutor.tutor_review_note or "",
        "documents": [document_dict(d) for d in tutor.documents],
        "rating": rating[0] if rating else None,
        "ratings_count": rating[1] if rating else 0,
        "rating_breakdown": {s: int(breakdown.get(s, 0)) for s in range(5, 0, -1)},
        "groups": [],
        "reviews": [],
    }
    if tutor.tutor_status != "approved":
        return result

    groups = db.scalars(
        select(Group).where(Group.tutor_id == tutor.id).options(selectinload(Group.tutor)).order_by(Group.id)
    ).all()
    group_ids = [g.id for g in groups]
    counts = enrolled_counts(db, group_ids)
    now = utcnow()
    lessons = db.scalars(
        select(Lesson).where(Lesson.group_id.in_(group_ids), Lesson.status != "cancelled")
        .order_by(Lesson.starts_at.desc()).limit(500)
    ).all() if group_ids else []
    lesson_avgs = dict(db.execute(
        select(LessonRating.lesson_id, func.avg(LessonRating.stars))
        .where(LessonRating.lesson_id.in_([l.id for l in lessons])).group_by(LessonRating.lesson_id)
    ).all()) if lessons else {}

    for g in groups:
        card = group_card(g, counts.get(g.id, 0), rating)
        mine = [l for l in lessons if l.group_id == g.id]
        upcoming = sorted((l for l in mine if l.status == "scheduled" and lesson_end(l) > now), key=lambda l: l.starts_at)
        to_complete = sorted((l for l in mine if l.status == "scheduled" and lesson_end(l) <= now), key=lambda l: l.starts_at)
        completed = [l for l in mine if l.status == "completed"][:5]
        card["upcoming_lessons"] = [lesson_dict(l, True) for l in upcoming]
        card["to_complete"] = [lesson_dict(l, False) for l in to_complete]
        card["completed_lessons"] = [
            {**lesson_dict(l, False), "avg_rating": round(float(lesson_avgs[l.id]), 2) if l.id in lesson_avgs else None}
            for l in completed
        ]
        result["groups"].append(card)

    reviews = db.scalars(
        select(LessonRating).where(LessonRating.tutor_id == tutor.id)
        .options(selectinload(LessonRating.student), selectinload(LessonRating.lesson))
        .order_by(LessonRating.id.desc()).limit(10)
    ).all()
    titles = {g.id: g.title for g in groups}
    result["reviews"] = [review_dict(r, titles.get(r.lesson.group_id)) for r in reviews]
    return result


@router.get("/documents")
def my_documents(tutor: User = Depends(require_tutor)):
    return [document_dict(d) for d in tutor.documents]


@router.post("/documents")
async def upload_documents(
    background: BackgroundTasks,
    certificates: list[UploadFile] = File(default=[]),
    tutor: User = Depends(require_tutor),
    db: DbSession = Depends(get_db),
):
    """Add certificates. A rejected teacher who uploads new documents goes back to the review queue."""
    ratelimit.check("documents", tutor.id)
    docs = await add_tutor_documents(db, tutor, certificates)
    if tutor.tutor_status == "rejected":
        tutor.tutor_status = "pending"
    db.commit()
    if tutor.tutor_status == "pending":
        background.add_task(notify, admin_recipients(db), "n_admin_tutor_docs", name=tutor.full_name, n=len(docs))
    return {"tutor_status": tutor.tutor_status, "documents": [document_dict(d) for d in tutor.documents]}


@router.get("/groups/{group_id}/students")
def group_students(group_id: int, tutor: User = Depends(require_approved_tutor), db: DbSession = Depends(get_db)):
    group = _own_group(db, tutor, group_id)
    enrollments = db.scalars(
        select(Enrollment).where(Enrollment.group_id == group.id).options(selectinload(Enrollment.student))
    ).all()
    latest_hw = {}
    for hw in db.scalars(
        select(HomeworkSubmission).where(HomeworkSubmission.group_id == group.id).order_by(HomeworkSubmission.id)
    ):
        latest_hw[hw.student_id] = hw
    students = []
    for e in sorted(enrollments, key=lambda e: e.student.full_name.lower()):
        hw = latest_hw.get(e.student_id)
        students.append({
            "id": e.student.id,
            "full_name": e.student.full_name,
            "telegram_username": e.student.telegram_username,
            "photo_url": e.student.photo_url,
            "strikes": e.strikes,
            "access_revoked": e.strikes >= MAX_STRIKES,
            "latest_homework": {"link": hw.link, "comment": hw.comment, "submitted_at": iso(hw.submitted_at)} if hw else None,
        })
    return {"group_id": group.id, "title": group.title, "students": students}


@router.post("/lessons")
def create_lesson(
    body: LessonCreateIn,
    background: BackgroundTasks,
    tutor: User = Depends(require_approved_tutor),
    db: DbSession = Depends(get_db),
):
    group = _own_group(db, tutor, body.group_id)
    starts_at = _check_start(body.starts_at)
    _check_new_link(db, group.id, body.meet_link)
    lesson = Lesson(
        group_id=group.id, tutor_id=tutor.id, starts_at=starts_at, duration_min=body.duration_min,
        topic=body.topic.strip(), meet_link=body.meet_link,
    )
    db.add(lesson)
    db.commit()
    background.add_task(
        notify, group_recipients(db, group.id), "n_lesson_scheduled",
        group=group.title, when=starts_at, topic=lesson.topic,
    )
    return lesson_dict(lesson, True)


@router.patch("/lessons/{lesson_id}")
def update_lesson(
    lesson_id: int,
    body: LessonUpdateIn,
    background: BackgroundTasks,
    tutor: User = Depends(require_approved_tutor),
    db: DbSession = Depends(get_db),
):
    lesson = _own_lesson(db, tutor, lesson_id)
    if lesson.status != "scheduled":
        raise ApiError("lesson_not_scheduled")
    if body.starts_at is not None:
        lesson.starts_at = _check_start(body.starts_at)
    if body.duration_min is not None:
        lesson.duration_min = body.duration_min
    if body.topic is not None:
        lesson.topic = body.topic.strip()
    if body.meet_link is not None and body.meet_link != lesson.meet_link:
        _check_new_link(db, lesson.group_id, body.meet_link, exclude_lesson_id=lesson.id)
        lesson.meet_link = body.meet_link
    db.commit()
    background.add_task(
        notify, group_recipients(db, lesson.group_id), "n_lesson_updated",
        group=lesson.group.title, when=aware(lesson.starts_at),
    )
    return lesson_dict(lesson, True)


@router.post("/lessons/{lesson_id}/cancel")
def cancel_lesson(
    lesson_id: int,
    background: BackgroundTasks,
    tutor: User = Depends(require_approved_tutor),
    db: DbSession = Depends(get_db),
):
    lesson = _own_lesson(db, tutor, lesson_id)
    if lesson.status != "scheduled":
        raise ApiError("lesson_not_scheduled")
    lesson.status = "cancelled"
    db.commit()
    background.add_task(
        notify, group_recipients(db, lesson.group_id), "n_lesson_cancelled",
        group=lesson.group.title, when=aware(lesson.starts_at),
    )
    return {"ok": True}


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(
    lesson_id: int,
    body: LessonCompleteIn,
    background: BackgroundTasks,
    tutor: User = Depends(require_approved_tutor),
    db: DbSession = Depends(get_db),
):
    """Close a lesson: save attendance + homework (strikes) and ask attendees to rate it."""
    lesson = _own_lesson(db, tutor, lesson_id)
    if lesson.status != "scheduled":
        raise ApiError("lesson_not_scheduled")
    if aware(lesson.starts_at) > utcnow():
        raise ApiError("lesson_not_started")
    enrollments = {
        e.student_id: e for e in db.scalars(select(Enrollment).where(Enrollment.group_id == lesson.group_id))
    }
    attendees = []
    for rec in body.records:
        enrollment = enrollments.get(rec.student_id)
        if enrollment is None:
            continue
        record = db.scalar(select(LessonRecord).where(
            LessonRecord.lesson_id == lesson.id, LessonRecord.student_id == rec.student_id
        ))
        if record is None:
            record = LessonRecord(lesson_id=lesson.id, student_id=rec.student_id)
            db.add(record)
        record.attended = rec.attended
        record.hw_status = rec.hw_status
        record.notes = rec.notes.strip()
        if rec.hw_status == "strike":
            enrollment.strikes = min(MAX_STRIKES, enrollment.strikes + 1)
        if rec.attended:
            attendees.append(rec.student_id)
    lesson.status = "completed"
    lesson.completed_at = utcnow()
    db.commit()
    if attendees:
        recipients = [
            (tid, lang) for tid, lang in db.execute(
                select(User.telegram_id, User.lang).where(User.id.in_(attendees), User.telegram_id.is_not(None))
            )
        ]
        background.add_task(notify, recipients, "n_rate_lesson", group=lesson.group.title)
    return {"ok": True}


@router.post("/strikes")
def strike_action(body: StrikeIn, tutor: User = Depends(require_approved_tutor), db: DbSession = Depends(get_db)):
    _own_group(db, tutor, body.group_id)
    enrollment = db.get(Enrollment, (body.group_id, body.student_id))
    if enrollment is None:
        raise ApiError("student_not_found", 404)
    apply_strike(enrollment, body.action)
    db.commit()
    return {"strikes": enrollment.strikes}


def apply_strike(enrollment: Enrollment, action: str) -> None:
    if action == "add":
        enrollment.strikes = min(MAX_STRIKES, enrollment.strikes + 1)
    elif action == "remove":
        enrollment.strikes = max(0, enrollment.strikes - 1)
    else:
        enrollment.strikes = 0
