from fastapi import APIRouter, HTTPException, Depends
from datetime import date
from app.database import get_db
from app.auth import require_tutor
from app.models import MeetLinkUpdateRequest, LessonSaveRequest, StrikeActionRequest

router = APIRouter(prefix="/api/tutor", tags=["tutor"])

@router.get("/groups")
def get_tutor_groups(user: dict = Depends(require_tutor)):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT g.id, g.name, g.language, g.tariff, g.schedule, g.meet_link, g.max_students,
               COUNT(gs.student_id) as enrolled_count
        FROM groups g
        LEFT JOIN group_students gs ON g.id = gs.group_id
        WHERE g.tutor_id = ?
        GROUP BY g.id
        ORDER BY g.id
    """, (user["id"],))
    groups = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return {"groups": groups}

@router.get("/groups/{group_id}/students")
def get_group_students(group_id: int, user: dict = Depends(require_tutor)):
    conn = get_db()
    cursor = conn.cursor()

    # Check that this group belongs to the tutor
    cursor.execute("SELECT id, name, meet_link, schedule, tariff FROM groups WHERE id = ? AND tutor_id = ?", (group_id, user["id"]))
    group = cursor.fetchone()
    if not group:
        conn.close()
        raise HTTPException(status_code=404, detail="Группа не найдена или не принадлежит вам")

    cursor.execute("""
        SELECT u.id, u.full_name, u.phone, u.telegram_username, u.is_blocked,
               gs.strikes, gs.joined_at,
               (
                   SELECT link FROM homework_submissions hw 
                   WHERE hw.student_id = u.id AND hw.group_id = ? 
                   ORDER BY hw.id DESC LIMIT 1
               ) as latest_hw_link,
               (
                   SELECT submitted_at FROM homework_submissions hw 
                   WHERE hw.student_id = u.id AND hw.group_id = ? 
                   ORDER BY hw.id DESC LIMIT 1
               ) as latest_hw_date
        FROM group_students gs
        JOIN users u ON gs.student_id = u.id
        WHERE gs.group_id = ?
        ORDER BY u.full_name
    """, (group_id, group_id, group_id))
    students = [dict(r) for r in cursor.fetchall()]

    # Fetch recent lessons for this group
    cursor.execute("""
        SELECT id, lesson_date, topic, created_at
        FROM lessons
        WHERE group_id = ?
        ORDER BY id DESC
        LIMIT 5
    """, (group_id,))
    recent_lessons = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "group": dict(group),
        "students": students,
        "recent_lessons": recent_lessons
    }

@router.post("/update-meet-link")
def update_meet_link(req: MeetLinkUpdateRequest, user: dict = Depends(require_tutor)):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM groups WHERE id = ? AND tutor_id = ?", (req.group_id, user["id"]))
    group = cursor.fetchone()
    if not group:
        conn.close()
        raise HTTPException(status_code=404, detail="Группа не найдена или не принадлежит вам")

    cursor.execute("UPDATE groups SET meet_link = ? WHERE id = ?", (req.meet_link.strip(), req.group_id))
    conn.commit()
    conn.close()

    return {"status": "ok", "message": "Ссылка на Google Meet успешно сохранена"}

@router.post("/save-lesson")
def save_lesson(req: LessonSaveRequest, user: dict = Depends(require_tutor)):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM groups WHERE id = ? AND tutor_id = ?", (req.group_id, user["id"]))
    group = cursor.fetchone()
    if not group:
        conn.close()
        raise HTTPException(status_code=404, detail="Группа не найдена или не принадлежит вам")

    lesson_date = req.lesson_date or str(date.today())
    topic = req.topic.strip() if req.topic else f"Занятие от {lesson_date}"

    # Insert lesson
    cursor.execute("""
        INSERT INTO lessons (group_id, tutor_id, lesson_date, topic)
        VALUES (?, ?, ?, ?)
    """, (req.group_id, user["id"], lesson_date, topic))
    lesson_id = cursor.lastrowid

    # Record attendance and homework for each student
    for record in req.records:
        cursor.execute("""
            INSERT INTO lesson_records (lesson_id, student_id, attended, hw_status, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (lesson_id, record.student_id, 1 if record.attended else 0, record.hw_status, record.notes or ""))

        # If tutor marked strike for HW: increment strike in group_students
        if record.hw_status == "strike":
            cursor.execute("""
                UPDATE group_students 
                SET strikes = MIN(3, strikes + 1)
                WHERE group_id = ? AND student_id = ?
            """, (req.group_id, record.student_id))

    conn.commit()
    conn.close()

    return {"status": "ok", "lesson_id": lesson_id, "message": "Результаты урока успешно сохранены!"}

@router.post("/strike-action")
def strike_action(req: StrikeActionRequest, user: dict = Depends(require_tutor)):
    conn = get_db()
    cursor = conn.cursor()

    # Check group belongs to tutor
    cursor.execute("SELECT id FROM groups WHERE id = ? AND tutor_id = ?", (req.group_id, user["id"]))
    group = cursor.fetchone()
    if not group:
        conn.close()
        raise HTTPException(status_code=404, detail="Группа не найдена или не принадлежит вам")

    if req.action == "add_strike":
        cursor.execute("UPDATE group_students SET strikes = MIN(3, strikes + 1) WHERE group_id = ? AND student_id = ?", (req.group_id, req.student_id))
    elif req.action == "remove_strike":
        cursor.execute("UPDATE group_students SET strikes = MAX(0, strikes - 1) WHERE group_id = ? AND student_id = ?", (req.group_id, req.student_id))
    elif req.action == "reset":
        cursor.execute("UPDATE group_students SET strikes = 0 WHERE group_id = ? AND student_id = ?", (req.group_id, req.student_id))

    conn.commit()
    cursor.execute("SELECT strikes FROM group_students WHERE group_id = ? AND student_id = ?", (req.group_id, req.student_id))
    row = cursor.fetchone()
    conn.close()

    new_strikes = row[0] if row else 0
    return {"status": "ok", "strikes": new_strikes}
