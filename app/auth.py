import uuid
from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from app.database import get_db

def create_session(user_id: int) -> str:
    token = str(uuid.uuid4())
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    conn.commit()
    conn.close()
    return token

def delete_session(token: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def get_current_user_optional(request: Request) -> Optional[dict]:
    token = None
    # Check Header Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    
    # Check X-Auth-Token header
    if not token:
        token = request.headers.get("X-Auth-Token")
        
    # Check Cookie
    if not token:
        token = request.cookies.get("session_token")
        
    if not token:
        return None

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.phone, u.full_name, u.role, u.telegram_username, u.is_blocked
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return None
    return dict(user)

def get_current_user(request: Request) -> dict:
    user = get_current_user_optional(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необходима авторизация"
        )
    return user

def require_role(allowed_roles: list[str]):
    def role_checker(user: dict = Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет доступа к этому разделу"
            )
        return user
    return role_checker

require_admin = require_role(["admin"])
require_tutor = require_role(["tutor"])
require_student = require_role(["student"])
