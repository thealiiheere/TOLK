import uuid
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from app.database import get_db, UPLOAD_DIR
from app.auth import get_current_user_optional

router = APIRouter(prefix="/api/public", tags=["public"])

TARIFFS = [
    {
        "id": "sinov",
        "name": "Sinov davri",
        "badge": "Пробный",
        "price": 10000,
        "price_display": "10,000 UZS / 1 занятие",
        "description": "Идеально для знакомства с платформой и пробного разговорного занятия в мини-группе.",
        "features": [
            "1 практический урок в микро-группе",
            "До 5 человек в группе",
            "Опытный студент-тьютор",
            "Обратная связь по уровню языка"
        ]
    },
    {
        "id": "bez_baryera",
        "name": "Bez baryera (Русский)",
        "badge": "Популярный",
        "price": 200000,
        "price_display": "200,000 UZS / месяц",
        "description": "Снятие языкового барьера, преодоление страха говорить, живая русская речь.",
        "features": [
            "3 занятия в неделю по расписанию",
            "Микро-группа строго до 5 человек",
            "Тьютор-носитель языка",
            "Домашние задания с проверкой",
            "Правило 3-х страйков для мотивации"
        ]
    },
    {
        "id": "speaking_club",
        "name": "Speaking Club",
        "badge": "Интенсив",
        "price": 300000,
        "price_display": "300,000 UZS / месяц",
        "description": "Разговорный клуб для уверенной спонтанной речи и дебатов на актуальные темы.",
        "features": [
            "Живые дискуссии и игры в мини-группе",
            "Разбор лексики и сленга",
            "Гибкое расписание",
            "Мини-группа до 5 человек"
        ]
    },
    {
        "id": "topik",
        "name": "TOPIK I-II (Корейский)",
        "badge": "Спецкурс",
        "price": 450000,
        "price_display": "400,000–500,000 UZS / месяц",
        "description": "Подготовка к сдаче экзамена TOPIK I-II со студентами корейских вузов.",
        "features": [
            "Разговорная практика + разбор структуры TOPIK",
            "Аудирование и письмо",
            "Тьюторы со знанием корейского на уровне TOPIK 5-6",
            "До 5 человек в группе"
        ]
    }
]

@router.get("/tariffs")
def get_tariffs():
    return {"tariffs": TARIFFS}

@router.post("/submit-payment")
async def submit_payment(
    tariff_name: str = Form(...),
    amount: int = Form(...),
    phone: str = Form(...),
    full_name: str = Form(...),
    telegram_username: str = Form(""),
    receipt_file: UploadFile = File(None)
):
    phone_clean = phone.strip()
    if not phone_clean:
        raise HTTPException(status_code=400, detail="Укажите номер телефона")

    # Save uploaded receipt image or use placeholder
    filename = "default_receipt.png"
    if receipt_file and receipt_file.filename:
        ext = Path(receipt_file.filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp", ".pdf"]:
            ext = ".jpg"
        filename = f"receipt_{uuid.uuid4().hex[:12]}{ext}"
        destination = UPLOAD_DIR / filename
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(receipt_file.file, buffer)
    else:
        # Use one of the pre-generated sample receipts
        filename = "receipt_sample_1.png"

    conn = get_db()
    cursor = conn.cursor()

    # Find or create user
    cursor.execute("SELECT id FROM users WHERE phone = ?", (phone_clean,))
    user = cursor.fetchone()

    if user:
        student_id = user["id"]
    else:
        cursor.execute("""
            INSERT INTO users (phone, full_name, role, telegram_username)
            VALUES (?, ?, 'student', ?)
        """, (phone_clean, full_name.strip() or f"Ученик {phone_clean[-4:]}", telegram_username.strip()))
        student_id = cursor.lastrowid

    # Create payment record
    cursor.execute("""
        INSERT INTO payments (student_id, tariff, amount, receipt_filename, status, admin_comment)
        VALUES (?, ?, ?, ?, 'pending', '')
    """, (student_id, tariff_name, amount, filename))
    payment_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "payment_id": payment_id,
        "message": "Заявка и чек успешно отправлены! Администратор подтвердит оплату в течение 15 минут."
    }
