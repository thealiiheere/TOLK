import sqlite3
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tolk.db"
UPLOAD_DIR = BASE_DIR / "uploads" / "receipts"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'tutor', 'student')),
        telegram_username TEXT,
        is_blocked INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        language TEXT NOT NULL,
        tariff TEXT NOT NULL,
        schedule TEXT NOT NULL,
        tutor_id INTEGER NOT NULL,
        meet_link TEXT DEFAULT '',
        max_students INTEGER DEFAULT 5,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(tutor_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS group_students (
        group_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        strikes INTEGER DEFAULT 0,
        joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (group_id, student_id),
        FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        tariff TEXT NOT NULL,
        amount INTEGER NOT NULL,
        receipt_filename TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
        admin_comment TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TEXT,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        tutor_id INTEGER NOT NULL,
        lesson_date TEXT NOT NULL,
        topic TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE,
        FOREIGN KEY(tutor_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS lesson_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        attended INTEGER DEFAULT 1,
        hw_status TEXT DEFAULT 'done' CHECK(hw_status IN ('done', 'strike', 'pending')),
        notes TEXT DEFAULT '',
        FOREIGN KEY(lesson_id) REFERENCES lessons(id) ON DELETE CASCADE,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS homework_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        link TEXT NOT NULL,
        comment TEXT DEFAULT '',
        status TEXT DEFAULT 'submitted' CHECK(status IN ('submitted', 'approved', 'rejected')),
        submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()

def seed_demo_data():
    conn = get_db()
    cursor = conn.cursor()

    # Check if admin already exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    # Seed Admin
    cursor.execute("""
    INSERT INTO users (phone, full_name, role, telegram_username)
    VALUES ('+998901110001', 'Администратор TOLK', 'admin', '@tolk_admin')
    """)

    # Seed Tutors
    cursor.execute("""
    INSERT INTO users (phone, full_name, role, telegram_username)
    VALUES 
    ('+998902220001', 'Алишер Каримов', 'tutor', '@alisher_tutor'),
    ('+998902220002', 'Дильноза Рахимова', 'tutor', '@dilnoza_tutor')
    """)
    tutor1_id = 2
    tutor2_id = 3

    # Seed 5 Students for the Test Group
    students = [
        ('+998903330001', 'Сардор Алиев', '@sardor_a', 0),
        ('+998903330002', 'Малика Юсупова', '@malika_y', 1),
        ('+998903330003', 'Джасур Умаров', '@jasur_u', 2),
        ('+998903330004', 'Нигора Ахмедова', '@nigora_a', 3), # 3 strikes test case
        ('+998903330005', 'Темур Саидов', '@temur_s', 0)
    ]

    student_ids = []
    for phone, name, tg, _ in students:
        cursor.execute("""
        INSERT INTO users (phone, full_name, role, telegram_username)
        VALUES (?, ?, 'student', ?)
        """, (phone, name, tg))
        student_ids.append(cursor.lastrowid)

    # Seed additional students with pending payments for Admin demo
    pending_students = [
        ('+998903330006', 'Азиз Мирзаев', '@aziz_m', 'Speaking Club', 300000),
        ('+998903330007', 'Зарина Ибрагимова', '@zarina_i', 'TOPIK I-II (Корейский)', 450000),
        ('+998903330008', 'Бобур Шарипов', '@bobur_sh', 'Sinov davri', 10000)
    ]
    pending_student_ids = []
    for phone, name, tg, tariff, amount in pending_students:
        cursor.execute("""
        INSERT INTO users (phone, full_name, role, telegram_username)
        VALUES (?, ?, 'student', ?)
        """, (phone, name, tg))
        p_id = cursor.lastrowid
        pending_student_ids.append((p_id, tariff, amount))

    # Create Groups
    # Group 1: Max 5 students, fully filled with 5 test students
    cursor.execute("""
    INSERT INTO groups (name, language, tariff, schedule, tutor_id, meet_link, max_students)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        'Группа #1 — Русский язык "Bez baryera"',
        'Русский язык',
        'Bez baryera (Русский)',
        'Вт / Чт / Сб в 19:00',
        tutor1_id,
        'https://meet.google.com/tolk-bez-baryera',
        5
    ))
    group1_id = cursor.lastrowid

    # Group 2: Korean with Tutor 2, has 2 slots free
    cursor.execute("""
    INSERT INTO groups (name, language, tariff, schedule, tutor_id, meet_link, max_students)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        'Группа #2 — Корейский язык TOPIK I-II',
        'Корейский язык',
        'TOPIK I-II (Корейский)',
        'Пн / Ср / Пт в 18:30',
        tutor2_id,
        'https://meet.google.com/tolk-topik-korean',
        5
    ))
    group2_id = cursor.lastrowid

    # Group 3: Speaking Club with Tutor 1
    cursor.execute("""
    INSERT INTO groups (name, language, tariff, schedule, tutor_id, meet_link, max_students)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        'Группа #3 — English Speaking Club',
        'Английский язык',
        'Speaking Club',
        'Сб / Вс в 11:00',
        tutor1_id,
        'https://meet.google.com/tolk-english-club',
        5
    ))
    group3_id = cursor.lastrowid

    # Enroll 5 students into Group 1 with their pre-assigned strikes
    for i, s_id in enumerate(student_ids):
        strikes = students[i][3]
        cursor.execute("""
        INSERT INTO group_students (group_id, student_id, strikes)
        VALUES (?, ?, ?)
        """, (group1_id, s_id, strikes))

    # Add sample homework submission for Sardor Aliev
    cursor.execute("""
    INSERT INTO homework_submissions (student_id, group_id, link, comment, status)
    VALUES (?, ?, ?, ?, ?)
    """, (
        student_ids[0],
        group1_id,
        'https://drive.google.com/file/d/tolk_hw_audio_recording_sardor/view',
        'Аудио-запись рассказа о себе на 2 минуты (тема Урока 1)',
        'approved'
    ))

    # Add sample homework submission for Malika Yusupova
    cursor.execute("""
    INSERT INTO homework_submissions (student_id, group_id, link, comment, status)
    VALUES (?, ?, ?, ?, ?)
    """, (
        student_ids[1],
        group1_id,
        'https://t.me/c/tolk_hw_malika/45',
        'Ссылка на видео-презентацию',
        'submitted'
    ))

    # Generate sample receipt files so admin can preview them
    _create_sample_receipts()

    # Create pending payments for the pending students
    cursor.execute("""
    INSERT INTO payments (student_id, tariff, amount, receipt_filename, status, admin_comment)
    VALUES 
    (?, ?, ?, 'receipt_sample_1.png', 'pending', ''),
    (?, ?, ?, 'receipt_sample_2.png', 'pending', ''),
    (?, ?, ?, 'receipt_sample_3.png', 'pending', '')
    """, (
        pending_student_ids[0][0], pending_student_ids[0][1], pending_student_ids[0][2],
        pending_student_ids[1][0], pending_student_ids[1][1], pending_student_ids[1][2],
        pending_student_ids[2][0], pending_student_ids[2][1], pending_student_ids[2][2],
    ))

    # Also add an approved payment record for Sardor Aliev
    cursor.execute("""
    INSERT INTO payments (student_id, tariff, amount, receipt_filename, status, admin_comment, reviewed_at)
    VALUES (?, 'Bez baryera (Русский)', 200000, 'receipt_sample_1.png', 'approved', 'Оплата подтверждена через Payme чек', CURRENT_TIMESTAMP)
    """, (student_ids[0],))

    # Add sample past lesson with attendance record
    cursor.execute("""
    INSERT INTO lessons (group_id, tutor_id, lesson_date, topic)
    VALUES (?, ?, '2026-09-28', 'Вводный урок: Знакомство и снятие языкового барьера')
    """, (group1_id, tutor1_id))
    lesson1_id = cursor.lastrowid

    for s_id in student_ids:
        cursor.execute("""
        INSERT INTO lesson_records (lesson_id, student_id, attended, hw_status, notes)
        VALUES (?, ?, 1, 'done', 'Активное участие')
        """, (lesson1_id, s_id))

    conn.commit()
    conn.close()

def _create_sample_receipts():
    """Generates simple receipt images using Pillow for realistic admin verification demo"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        receipts = [
            ("receipt_sample_1.png", "CHECK: 300,000 UZS", "Speaking Club", "Card: *8821"),
            ("receipt_sample_2.png", "CHECK: 450,000 UZS", "TOPIK I-II (Korean)", "Card: *4019"),
            ("receipt_sample_3.png", "CHECK: 10,000 UZS", "Sinov Davri (Trial)", "Card: *5531")
        ]
        for fname, title, desc, card in receipts:
            filepath = UPLOAD_DIR / fname
            if not filepath.exists():
                img = Image.new('RGB', (450, 600), color=(250, 250, 252))
                d = ImageDraw.Draw(img)
                # Border
                d.rectangle([(15, 15), (435, 585)], outline=(220, 224, 230), width=2)
                # Header
                d.rectangle([(15, 15), (435, 90)], fill=(255, 107, 0))
                d.text((140, 40), "TOLK PAYMENT", fill=(255, 255, 255))
                # Details
                d.text((50, 130), "Квитанция о переводе", fill=(30, 30, 30))
                d.text((50, 180), f"Сумма: {title}", fill=(20, 130, 40))
                d.text((50, 230), f"Тариф: {desc}", fill=(50, 50, 50))
                d.text((50, 280), f"Отправитель: {card}", fill=(80, 80, 80))
                d.text((50, 330), "Дата: 01.10.2026 14:22", fill=(100, 100, 100))
                d.text((50, 380), "Статус: Успешно проведен", fill=(20, 130, 40))
                d.text((50, 440), "ID транзакции: #TLK-92847194", fill=(130, 130, 130))
                # Footer note
                d.text((50, 520), "Manual verification document for TOLK MVP", fill=(160, 160, 160))
                img.save(filepath)
    except Exception as e:
        print(f"Warning generating receipt images: {e}")
