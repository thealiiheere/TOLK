"""SQLAlchemy ORM models. Schema changes need an Alembic migration (see CLAUDE.md)."""
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

ROLES = ("student", "tutor", "admin")
LANGS = ("uz", "ru", "en")
CATEGORIES = ("language", "other")
PRICE_PERIODS = ("month", "course", "lesson")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64))
    photo_url: Mapped[str | None] = mapped_column(String(500))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(16), default="student")
    lang: Mapped[str] = mapped_column(String(2), default="uz")
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    # Tutor profile (only meaningful when role == "tutor")
    bio: Mapped[str] = mapped_column(Text, default="")
    tutor_subjects: Mapped[str] = mapped_column(String(255), default="")
    tutor_status: Mapped[str | None] = mapped_column(String(16))  # pending / approved / rejected
    tutor_review_note: Mapped[str] = mapped_column(String(500), default="", server_default="")  # admin's reason
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (CheckConstraint("role IN ('student','tutor','admin')", name="ck_users_role"),)

    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="student", cascade="all, delete-orphan")
    documents: Mapped[list["TutorDocument"]] = relationship(
        back_populates="tutor", cascade="all, delete-orphan", order_by="TutorDocument.id"
    )


class TutorDocument(Base):
    """A certificate / diploma a teacher uploads to prove their qualification. Private: admins only."""
    __tablename__ = "tutor_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    tutor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(64))  # stored name on disk (random)
    original_name: Mapped[str] = mapped_column(String(160), default="")  # sanitized, for display only
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    tutor: Mapped[User] = relationship(back_populates="documents")


class Session(Base):
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class Group(Base):
    """A class/course that students enroll into. Created by the admin, taught by one tutor."""
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Short public course code (e.g. "ENG-101"), unique, stored uppercase. Auto-generated when the admin leaves it empty.
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(16), default="language")  # language / other
    # For category "language": ISO code (en, ru, ko...). For "other": free-text subject (Math, IT...).
    subject: Mapped[str] = mapped_column(String(80), index=True)
    level: Mapped[str] = mapped_column(String(40), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer, default=0)  # UZS
    price_period: Mapped[str] = mapped_column(String(16), default="month")
    schedule: Mapped[str] = mapped_column(String(160), default="")
    max_students: Mapped[int] = mapped_column(Integer, default=5)
    tutor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    # Poster image (re-encoded WEBP in upload_dir/posters, public). None = colored cover.
    poster: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("category IN ('language','other')", name="ck_groups_category"),
        CheckConstraint("price >= 0", name="ck_groups_price"),
    )

    tutor: Mapped[User | None] = relationship()
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="group", cascade="all, delete-orphan")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class Enrollment(Base):
    __tablename__ = "group_students"

    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    strikes: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group: Mapped[Group] = relationship(back_populates="enrollments")
    student: Mapped[User] = relationship(back_populates="enrollments")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id", ondelete="SET NULL"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    receipt_filename: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending/approved/rejected
    admin_comment: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped[User] = relationship()
    group: Mapped[Group | None] = relationship()


class Lesson(Base):
    """One scheduled lesson. Each lesson carries its own meeting link (Zoom / Google Meet)."""
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    tutor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_min: Mapped[int] = mapped_column(Integer, default=60)
    topic: Mapped[str] = mapped_column(String(200), default="")
    meet_link: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), default="scheduled")  # scheduled/completed/cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    group: Mapped[Group] = relationship(back_populates="lessons")
    tutor: Mapped[User | None] = relationship()
    records: Mapped[list["LessonRecord"]] = relationship(back_populates="lesson", cascade="all, delete-orphan")
    ratings: Mapped[list["LessonRating"]] = relationship(back_populates="lesson", cascade="all, delete-orphan")


class LessonRecord(Base):
    """Attendance + homework result for one student in one lesson (filled by the tutor)."""
    __tablename__ = "lesson_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    attended: Mapped[bool] = mapped_column(Boolean, default=True)
    hw_status: Mapped[str] = mapped_column(String(16), default="none")  # done / strike / none
    notes: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (UniqueConstraint("lesson_id", "student_id", name="uq_lesson_records_lesson_student"),)

    lesson: Mapped[Lesson] = relationship(back_populates="records")


class LessonRating(Base):
    """1-5 star rating a student gives after a completed lesson. Drives the tutor's public rating."""
    __tablename__ = "lesson_ratings"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tutor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    stars: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("lesson_id", "student_id", name="uq_lesson_ratings_lesson_student"),
        CheckConstraint("stars BETWEEN 1 AND 5", name="ck_lesson_ratings_stars"),
    )

    lesson: Mapped[Lesson] = relationship(back_populates="ratings")
    student: Mapped[User] = relationship(foreign_keys=[student_id])


class HomeworkSubmission(Base):
    __tablename__ = "homework_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    link: Mapped[str] = mapped_column(String(500))
    comment: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(16), default="submitted")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
