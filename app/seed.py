"""Demo data for presentations and local development.

    python -m app.seed            # add demo data if there is none yet
    python -m app.seed --reset    # DEV ONLY: drop every table, recreate, then seed

Demo users have is_demo=True and no Telegram account; they can only be used via the
one-click demo login, which exists only while DEMO_MODE=true.
"""
import argparse
import sys
from datetime import timedelta

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import (
    Enrollment, Group, HomeworkSubmission, Lesson, LessonRating, LessonRecord, Payment, TutorDocument, User, utcnow,
)
from app.services import generate_course_code
from app.uploads import CERTIFICATES, receipts_dir, upload_dir

TUTORS = [
    ("Alisher Karimov", "en,ru", "IELTS 8.0, 4 years of teaching speaking clubs. Business English and exam prep."),
    ("Dilnoza Rahimova", "ko", "TOPIK 6, studied at Seoul National University. Prepares students for TOPIK I-II."),
    ("Bobur Tursunov", "Mathematics, Programming", "Software engineer at a fintech startup. Teaches Python and SAT math."),
    ("Madina Saidova", "ru,de", "Philology graduate, Goethe-Zertifikat C1. Russian without barriers and German A1-B1."),
]
PENDING_TUTOR = ("Jamshid Nazarov", "Physics", "Physics olympiad winner, 2 years of tutoring school students.")
STUDENTS = ["Sardor Aliyev", "Malika Yusupova", "Jasur Umarov", "Nigora Ahmedova", "Temur Saidov", "Aziz Mirzayev", "Kamola Ergasheva"]

GROUPS = [
    # title, category, subject, level, price, period, schedule, tutor index, description
    ("English Speaking Club", "language", "en", "B1-B2", 300_000, "month", "Mon / Wed / Fri 19:00", 0,
     "Live conversation practice in a group of up to 5 people. Every student speaks at least 15 minutes per lesson."),
    ("IELTS Speaking Intensive", "language", "en", "B2+", 500_000, "month", "Tue / Thu 20:00", 0,
     "Mock speaking tests, band-score feedback and strategies for all three parts of the exam."),
    ("TOPIK I-II Preparation", "language", "ko", "A2-B1", 450_000, "month", "Tue / Thu / Sat 18:00", 1,
     "Grammar, listening and writing for the TOPIK exam with a TOPIK-6 tutor."),
    ("Russian Without Barriers", "language", "ru", "A2-B1", 200_000, "month", "Mon / Wed 18:30", 3,
     "Overcome the fear of speaking Russian: everyday situations, role plays and pronunciation."),
    ("German for Beginners", "language", "de", "A1", 350_000, "month", "Sat / Sun 11:00", 3,
     "Start German from zero: alphabet, basic grammar and simple conversations."),
    ("Python from Zero", "other", "Programming", "Beginner", 400_000, "month", "Sat 15:00", 2,
     "Variables to small projects. Homework is reviewed every week."),
    ("SAT Math", "other", "Mathematics", "Intermediate", 350_000, "month", "Mon / Thu 17:00", 2,
     "All SAT math topics with timed practice tests."),
    ("Trial lesson: English", "language", "en", "Any", 10_000, "lesson", "On request", 0,
     "One trial lesson to try the format before paying for a month."),
]


def _receipt(name: str, amount: int) -> str:
    """Draw a simple fake bank receipt so the admin payment review has something to show."""
    filename = f"demo_{name}.png"
    path = receipts_dir() / filename
    if not path.exists():
        img = Image.new("RGB", (420, 560), "white")
        d = ImageDraw.Draw(img)
        d.rectangle((0, 0, 420, 70), fill=(37, 99, 235))
        d.text((20, 25), "DEMO BANK  -  Transfer receipt", fill="white")
        lines = [
            "Status: SUCCESS", f"Amount: {amount:,} UZS".replace(",", " "), "To card: 8600 **** **** 0000",
            "Recipient: TOLK Education", f"Date: {utcnow():%d.%m.%Y %H:%M}", "", "This is demo data.",
        ]
        for i, line in enumerate(lines):
            d.text((20, 100 + i * 34), line, fill=(30, 30, 30))
        img.save(path)
    return filename


def _certificate(name: str, subject: str) -> str:
    """Draw a simple fake certificate for demo teachers (the admin review screen shows it)."""
    filename = f"demo_cert_{abs(hash((name, subject))) % 10**8}.png"
    path = upload_dir(CERTIFICATES) / filename
    if not path.exists():
        img = Image.new("RGB", (560, 400), (250, 247, 238))
        d = ImageDraw.Draw(img)
        d.rectangle((12, 12, 548, 388), outline=(180, 140, 60), width=4)
        for i, line in enumerate(["CERTIFICATE", "", f"awarded to {name}", f"for excellence in {subject}", "", "DEMO DATA"]):
            d.text((60, 70 + i * 40), line, fill=(60, 50, 30))
        img.save(path)
    return filename


def seed(db) -> bool:
    if db.scalar(select(User.id).where(User.is_demo.is_(True)).limit(1)):
        return False
    now = utcnow()

    admin = User(full_name="TOLK Admin", role="admin", onboarded=True, is_demo=True, lang="en")
    tutors = [
        User(full_name=n, role="tutor", onboarded=True, is_demo=True, tutor_subjects=s, bio=b, tutor_status="approved",
             telegram_username=f"@demo_tutor{i + 1}", lang="en")
        for i, (n, s, b) in enumerate(TUTORS)
    ]
    pending = User(full_name=PENDING_TUTOR[0], role="tutor", onboarded=True, is_demo=True,
                   tutor_subjects=PENDING_TUTOR[1], bio=PENDING_TUTOR[2], tutor_status="pending", lang="en")
    students = [
        User(full_name=n, role="student", onboarded=True, is_demo=True, phone=f"+99890333000{i + 1}",
             telegram_username=f"@demo_student{i + 1}", lang="en")
        for i, n in enumerate(STUDENTS)
    ]
    for t in [*tutors, pending]:
        t.documents.append(TutorDocument(filename=_certificate(t.full_name, t.tutor_subjects), original_name="certificate.png"))
    db.add_all([admin, *tutors, pending, *students])
    db.flush()

    groups = []
    for title, cat, subj, level, price, period, sched, t_idx, desc in GROUPS:
        g = Group(code=generate_course_code(db, cat, subj), title=title, category=cat, subject=subj, level=level,
                  price=price, price_period=period, schedule=sched, tutor_id=tutors[t_idx].id, description=desc,
                  max_students=5)
        db.add(g)
        db.flush()  # so the next generated code sees this one
        groups.append(g)
    db.add_all(groups)
    db.flush()

    # Main demo class: English Speaking Club with five students showing 0..3 strikes
    club = groups[0]
    for student, strikes in zip(students[:5], [0, 1, 2, 3, 0]):
        db.add(Enrollment(group_id=club.id, student_id=student.id, strikes=strikes))
    db.add(Enrollment(group_id=groups[2].id, student_id=students[0].id))
    db.add(Enrollment(group_id=groups[5].id, student_id=students[1].id))
    db.add(Enrollment(group_id=groups[5].id, student_id=students[4].id))

    # Past lessons with ratings so the catalog shows real teacher ratings
    stars_by_group = {0: [5, 5, 4, 5], 2: [5, 4], 5: [4, 5], 3: [], 6: []}
    rated_students = {0: students[:5], 2: [students[0]], 5: [students[1], students[4]]}
    for g_idx, stars in stars_by_group.items():
        group = groups[g_idx]
        for week in range(1, 4):
            lesson = Lesson(group_id=group.id, tutor_id=group.tutor_id, starts_at=now - timedelta(days=7 * week),
                            topic=f"Week {4 - week} topic", meet_link=f"https://meet.google.com/demo-old-{group.id}{week}",
                            status="completed", completed_at=now - timedelta(days=7 * week) + timedelta(hours=1))
            db.add(lesson)
            db.flush()
            for i, student in enumerate(rated_students.get(g_idx, [])):
                db.add(LessonRecord(lesson_id=lesson.id, student_id=student.id, attended=True, hw_status="done"))
                if stars and week <= 2:
                    db.add(LessonRating(lesson_id=lesson.id, student_id=student.id, tutor_id=group.tutor_id,
                                        stars=stars[(i + week) % len(stars)],
                                        comment=["Great lesson!", "Very useful, thank you", "", "Loved the discussion"][(i + week) % 4]))

    # A lesson that just finished (students can rate it) and upcoming lessons with fresh links
    db.add(Lesson(group_id=club.id, tutor_id=club.tutor_id, starts_at=now - timedelta(hours=3), topic="Travel stories",
                  meet_link="https://meet.google.com/abc-defg-hij"))
    db.add(Lesson(group_id=club.id, tutor_id=club.tutor_id, starts_at=now + timedelta(days=1, hours=2),
                  topic="Talking about movies", meet_link="https://meet.google.com/xyz-uvwq-rst"))
    db.add(Lesson(group_id=groups[2].id, tutor_id=groups[2].tutor_id, starts_at=now + timedelta(days=2),
                  topic="TOPIK listening practice", meet_link="https://us05web.zoom.us/j/81234567890"))
    db.add(Lesson(group_id=groups[5].id, tutor_id=groups[5].tutor_id, starts_at=now + timedelta(days=3),
                  topic="Loops and functions", meet_link="https://meet.google.com/pyt-hone-zro"))

    db.add(HomeworkSubmission(student_id=students[0].id, group_id=club.id,
                              link="https://drive.google.com/file/d/demo-homework-1", comment="Essay about my city"))
    db.add(HomeworkSubmission(student_id=students[1].id, group_id=club.id,
                              link="https://drive.google.com/file/d/demo-homework-2", comment="Voice recording"))

    # Payments waiting for the admin
    db.add(Payment(student_id=students[5].id, group_id=club.id, amount=club.price,
                   receipt_filename=_receipt("1", club.price)))
    db.add(Payment(student_id=students[6].id, group_id=groups[2].id, amount=groups[2].price,
                   receipt_filename=_receipt("2", groups[2].price)))
    db.add(Payment(student_id=students[0].id, group_id=groups[0].id, amount=club.price, status="approved",
                   receipt_filename=_receipt("3", club.price), reviewed_at=now - timedelta(days=25)))
    db.commit()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables first (dev only)")
    args = parser.parse_args()
    if args.reset:
        if settings.is_production:
            sys.exit("Refusing to --reset in production.")
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        print("Database reset.")
    with SessionLocal() as db:
        print("Demo data added." if seed(db) else "Demo data already present, nothing to do.")


if __name__ == "__main__":
    main()
