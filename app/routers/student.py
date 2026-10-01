from fastapi import APIRouter, HTTPException, Depends
from app.database import get_db
from app.auth import require_student
from app.models import HomeworkSubmitRequest

router = APIRouter(prefix="/api/student", tags=["student"])

@router.get("/dashboard")
def get_student_dashboard(user: dict = Depends(require_student)):
    conn = get_db()
    cursor = conn.cursor()

    # Get student's group info
    cursor.execute("""
        SELECT 
            g.id as group_id,
            g.name as group_name,
            g.language,
            g.tariff,
            g.schedule,
            g.meet_link,
            t.full_name as tutor_name,
            t.phone as tutor_phone,
            t.telegram_username as tutor_telegram,
            gs.strikes,
            gs.joined_at,
            u.is_blocked
        FROM users u
        LEFT JOIN group_students gs ON u.id = gs.student_id
        LEFT JOIN groups g ON gs.group_id = g.id
        LEFT JOIN users t ON g.tutor_id = t.id
        WHERE u.id = ?
    """, (user["id"],))
    group_info = cursor.fetchone()

    # Get homework submissions history
    cursor.execute("""
        SELECT id, link, comment, status, submitted_at
        FROM homework_submissions
        WHERE student_id = ?
        ORDER BY id DESC
    """, (user["id"],))
    hw_rows = cursor.fetchall()
    submissions = [dict(r) for r in hw_rows]

    # Get payment records
    cursor.execute("""
        SELECT id, tariff, amount, receipt_filename, status, admin_comment, created_at, reviewed_at
        FROM payments
        WHERE student_id = ?
        ORDER BY id DESC
    """, (user["id"],))
    payments = [dict(r) for r in cursor.fetchall()]

    conn.close()

    result = {
        "user": user,
        "enrolled": False,
        "group": None,
        "submissions": submissions,
        "payments": payments
    }

    if group_info and group_info["group_id"]:
        group_data = dict(group_info)
        is_blocked = bool(group_data["is_blocked"] or group_data["strikes"] >= 3)
        group_data["is_access_revoked"] = is_blocked
        result["enrolled"] = True
        result["group"] = group_data

    return result

@router.post("/submit-hw")
def submit_homework(req: HomeworkSubmitRequest, user: dict = Depends(require_student)):
    link = req.link.strip()
    if not link:
        raise HTTPException(status_code=400, detail="Укажите ссылку на выполненное ДЗ")

    conn = get_db()
    cursor = conn.cursor()

    # Verify student is in group
    cursor.execute("""
        SELECT gs.strikes, u.is_blocked
        FROM group_students gs
        JOIN users u ON gs.student_id = u.id
        WHERE gs.student_id = ? AND gs.group_id = ?
    """, (user["id"], req.group_id))
    enrollment = cursor.fetchone()

    if not enrollment:
        conn.close()
        raise HTTPException(status_code=403, detail="Вы не состоите в указанной группе")

    if enrollment["is_blocked"] or enrollment["strikes"] >= 3:
        conn.close()
        raise HTTPException(status_code=403, detail="Доступ к группе аннулирован из-за 3 страйков")

    cursor.execute("""
        INSERT INTO homework_submissions (student_id, group_id, link, comment, status)
        VALUES (?, ?, ?, ?, 'submitted')
    """, (user["id"], req.group_id, link, req.comment))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return {"status": "ok", "submission_id": new_id, "message": "Домашнее задание успешно отправлено!"}
