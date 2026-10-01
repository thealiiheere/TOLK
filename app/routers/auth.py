from fastapi import APIRouter, HTTPException, Response, Request, Depends
from app.database import get_db
from app.models import PhoneLoginRequest, DemoLoginRequest, TelegramAuthRequest
from app.auth import create_session, delete_session, get_current_user, get_current_user_optional

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.get("/demo-users")
def get_demo_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.phone, u.full_name, u.role, u.telegram_username, u.is_blocked,
               gs.group_id, gs.strikes, g.name as group_name
        FROM users u
        LEFT JOIN group_students gs ON u.id = gs.student_id
        LEFT JOIN groups g ON gs.group_id = g.id
        ORDER BY 
            CASE u.role 
                WHEN 'admin' THEN 1 
                WHEN 'tutor' THEN 2 
                WHEN 'student' THEN 3 
            END, u.id
    """)
    rows = cursor.fetchall()
    conn.close()

    demo_accounts = []
    for r in rows:
        item = dict(r)
        demo_accounts.append(item)
    return {"demo_users": demo_accounts}

@router.post("/demo-login")
def demo_login(req: DemoLoginRequest, response: Response):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, phone, full_name, role, telegram_username, is_blocked FROM users WHERE id = ?", (req.user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    token = create_session(user["id"])
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=86400 * 30,
        samesite="lax"
    )
    return {
        "status": "ok",
        "token": token,
        "user": dict(user)
    }

@router.post("/login-phone")
def login_phone(req: PhoneLoginRequest, response: Response):
    phone = req.phone.strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Номер телефона обязателен")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, phone, full_name, role, telegram_username, is_blocked FROM users WHERE phone = ?", (phone,))
    user = cursor.fetchone()

    if not user:
        # Register new student
        full_name = req.full_name.strip() if req.full_name else f"Ученик {phone[-4:]}"
        tg = req.telegram_username.strip() if req.telegram_username else None
        cursor.execute("""
            INSERT INTO users (phone, full_name, role, telegram_username)
            VALUES (?, ?, 'student', ?)
        """, (phone, full_name, tg))
        conn.commit()
        user_id = cursor.lastrowid
        cursor.execute("SELECT id, phone, full_name, role, telegram_username, is_blocked FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

    conn.close()

    token = create_session(user["id"])
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=86400 * 30,
        samesite="lax"
    )

    return {
        "status": "ok",
        "token": token,
        "user": dict(user)
    }

@router.post("/telegram-webapp")
def telegram_webapp_auth(req: TelegramAuthRequest, response: Response):
    conn = get_db()
    cursor = conn.cursor()

    username = f"@{req.username.lstrip('@')}" if req.username else None
    phone_fallback = f"+tg_{req.id}"

    user = None
    # 1. Try matching by telegram_username if provided
    if username:
        cursor.execute("SELECT id, phone, full_name, role, telegram_username, is_blocked FROM users WHERE LOWER(telegram_username) = LOWER(?)", (username,))
        user = cursor.fetchone()

    # 2. Try matching by phone fallback
    if not user:
        cursor.execute("SELECT id, phone, full_name, role, telegram_username, is_blocked FROM users WHERE phone = ?", (phone_fallback,))
        user = cursor.fetchone()

    # 3. If not found, register new student
    if not user:
        full_name = f"{req.first_name} {req.last_name or ''}".strip() or f"Ученик {req.id}"
        cursor.execute("""
            INSERT INTO users (phone, full_name, role, telegram_username)
            VALUES (?, ?, 'student', ?)
        """, (phone_fallback, full_name, username))
        conn.commit()
        user_id = cursor.lastrowid
        cursor.execute("SELECT id, phone, full_name, role, telegram_username, is_blocked FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

    conn.close()

    token = create_session(user["id"])
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=86400 * 30,
        samesite="lax"
    )

    return {
        "status": "ok",
        "token": token,
        "user": dict(user)
    }

@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return {"user": user}

@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("session_token") or request.headers.get("X-Auth-Token")
    if token:
        delete_session(token)
    response.delete_cookie("session_token")
    return {"status": "ok"}
