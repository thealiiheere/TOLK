from fastapi import APIRouter, HTTPException, Depends
from app.database import get_db
from app.auth import require_admin
from app.models import (
    GroupCreateRequest,
    StudentAssignRequest,
    PaymentReviewRequest,
    UserBlockRequest,
    StrikeActionRequest
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.get("/overview")
def get_admin_overview(user: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()

    # Stats
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'tutor'")
    total_tutors = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM groups")
    total_groups = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
    pending_payments_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM group_students WHERE strikes >= 3")
    striked_students_count = cursor.fetchone()[0]

    # Pending Payments with user details
    cursor.execute("""
        SELECT p.id, p.tariff, p.amount, p.receipt_filename, p.status, p.created_at,
               u.id as student_id, u.full_name as student_name, u.phone as student_phone, u.telegram_username
        FROM payments p
        JOIN users u ON p.student_id = u.id
        ORDER BY 
            CASE p.status WHEN 'pending' THEN 1 ELSE 2 END,
            p.id DESC
    """)
    payments = [dict(r) for r in cursor.fetchall()]

    # Groups list with student count and tutor info
    cursor.execute("""
        SELECT g.id, g.name, g.language, g.tariff, g.schedule, g.meet_link, g.max_students,
               t.id as tutor_id, t.full_name as tutor_name, t.phone as tutor_phone,
               COUNT(gs.student_id) as enrolled_count
        FROM groups g
        LEFT JOIN users t ON g.tutor_id = t.id
        LEFT JOIN group_students gs ON g.id = gs.group_id
        GROUP BY g.id
        ORDER BY g.id
    """)
    groups = [dict(r) for r in cursor.fetchall()]

    # For each group, get enrolled student details
    for g in groups:
        cursor.execute("""
            SELECT u.id, u.full_name, u.phone, u.telegram_username, u.is_blocked, gs.strikes
            FROM group_students gs
            JOIN users u ON gs.student_id = u.id
            WHERE gs.group_id = ?
            ORDER BY u.full_name
        """, (g["id"],))
        g["students"] = [dict(r) for r in cursor.fetchall()]

    # Violations Log: students with 3 strikes or is_blocked
    cursor.execute("""
        SELECT u.id as student_id, u.full_name as student_name, u.phone, u.telegram_username, u.is_blocked,
               gs.strikes, gs.group_id, g.name as group_name, t.full_name as tutor_name
        FROM group_students gs
        JOIN users u ON gs.student_id = u.id
        JOIN groups g ON gs.group_id = g.id
        LEFT JOIN users t ON g.tutor_id = t.id
        WHERE gs.strikes >= 3 OR u.is_blocked = 1
        ORDER BY gs.strikes DESC, u.id
    """)
    violations = [dict(r) for r in cursor.fetchall()]

    # Available tutors for new groups
    cursor.execute("SELECT id, full_name, phone FROM users WHERE role = 'tutor' ORDER BY full_name")
    tutors = [dict(r) for r in cursor.fetchall()]

    # Unassigned or available students (either paid or needing group)
    cursor.execute("""
        SELECT u.id, u.full_name, u.phone, u.telegram_username,
               (SELECT tariff FROM payments WHERE student_id = u.id AND status = 'approved' ORDER BY id DESC LIMIT 1) as paid_tariff
        FROM users u
        WHERE u.role = 'student'
          AND u.is_blocked = 0
          AND u.id NOT IN (SELECT student_id FROM group_students)
        ORDER BY u.id DESC
    """)
    unassigned_students = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "stats": {
            "total_students": total_students,
            "total_tutors": total_tutors,
            "total_groups": total_groups,
            "pending_payments": pending_payments_count,
            "striked_students": striked_students_count
        },
        "payments": payments,
        "groups": groups,
        "violations": violations,
        "tutors": tutors,
        "unassigned_students": unassigned_students
    }

@router.post("/review-payment/{payment_id}")
def review_payment(payment_id: int, req: PaymentReviewRequest, user: dict = Depends(require_admin)):
    if req.status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Неверный статус оплаты")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, student_id, tariff FROM payments WHERE id = ?", (payment_id,))
    payment = cursor.fetchone()
    if not payment:
        conn.close()
        raise HTTPException(status_code=404, detail="Заявка на оплату не найдена")

    cursor.execute("""
        UPDATE payments 
        SET status = ?, admin_comment = ?, reviewed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (req.status, req.admin_comment or "", payment_id))
    conn.commit()
    conn.close()

    status_str = "подтверждена" if req.status == "approved" else "отклонена"
    return {"status": "ok", "message": f"Оплата #{payment_id} успешно {status_str}"}

@router.post("/groups/create")
def create_group(req: GroupCreateRequest, user: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE id = ? AND role = 'tutor'", (req.tutor_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Выбранный тьютор не найден")

    cursor.execute("""
        INSERT INTO groups (name, language, tariff, schedule, tutor_id, meet_link, max_students)
        VALUES (?, ?, ?, ?, ?, ?, 5)
    """, (
        req.name.strip(),
        req.language.strip(),
        req.tariff.strip(),
        req.schedule.strip(),
        req.tutor_id,
        (req.meet_link or "").strip()
    ))
    conn.commit()
    group_id = cursor.lastrowid
    conn.close()

    return {"status": "ok", "group_id": group_id, "message": "Группа успешно создана"}

@router.post("/groups/assign-student")
def assign_student_to_group(req: StudentAssignRequest, user: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()

    # Verify group exists and has capacity
    cursor.execute("SELECT id, max_students FROM groups WHERE id = ?", (req.group_id,))
    group = cursor.fetchone()
    if not group:
        conn.close()
        raise HTTPException(status_code=404, detail="Группа не найдена")

    cursor.execute("SELECT COUNT(*) FROM group_students WHERE group_id = ?", (req.group_id,))
    current_count = cursor.fetchone()[0]

    # HARD CONSTRAINT: Max 5 students per micro-group
    if current_count >= group["max_students"]:
        conn.close()
        raise HTTPException(
            status_code=400, 
            detail=f"Группа заполнена! Максимум {group['max_students']} человек на микро-группу."
        )

    # Check if student already in any group
    cursor.execute("SELECT group_id FROM group_students WHERE student_id = ?", (req.student_id,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Ученик уже распределен в группу")

    cursor.execute("""
        INSERT INTO group_students (group_id, student_id, strikes)
        VALUES (?, ?, 0)
    """, (req.group_id, req.student_id))
    conn.commit()
    conn.close()

    return {"status": "ok", "message": "Ученик успешно зачислен в группу"}

@router.post("/groups/remove-student")
def remove_student_from_group(req: StudentAssignRequest, user: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM group_students WHERE group_id = ? AND student_id = ?", (req.group_id, req.student_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Ученик удален из группы"}

@router.post("/block-student")
def block_student(req: UserBlockRequest, user: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()

    # Update is_blocked
    cursor.execute("UPDATE users SET is_blocked = ? WHERE id = ?", (1 if req.is_blocked else 0, req.student_id))

    # If action is to exclude from group:
    if req.is_blocked and req.group_id:
        cursor.execute("DELETE FROM group_students WHERE group_id = ? AND student_id = ?", (req.group_id, req.student_id))

    conn.commit()
    conn.close()

    msg = "Доступ заблокирован и ученик исключен из группы" if req.is_blocked else "Доступ ученика восстановлен"
    return {"status": "ok", "message": msg}

@router.post("/reset-strikes")
def reset_student_strikes(req: StrikeActionRequest, user: dict = Depends(require_admin)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE group_students SET strikes = 0 WHERE group_id = ? AND student_id = ?", (req.group_id, req.student_id))
    cursor.execute("UPDATE users SET is_blocked = 0 WHERE id = ?", (req.student_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Страйки успешно сброшены"}
