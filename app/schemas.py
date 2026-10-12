"""Pydantic request bodies. Responses are plain dicts built in app/services.py."""
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings

Lang = Literal["uz", "ru", "en"]


def _clean(v: str | None) -> str:
    return (v or "").strip()


def validate_http_url(v: str) -> str:
    v = _clean(v)
    parts = urlsplit(v)
    if parts.scheme not in ("http", "https") or not parts.netloc or len(v) > 500:
        raise ValueError("invalid_url")
    return v


def validate_meeting_link(v: str) -> str:
    """Meeting links must be HTTPS and point to an allowed video platform (Zoom, Google Meet...)."""
    v = _clean(v)
    parts = urlsplit(v)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or len(v) > 500:
        raise ValueError("invalid_meeting_link")
    if not any(host == h or host.endswith("." + h) for h in settings.meeting_hosts):
        raise ValueError("invalid_meeting_link")
    return v


# ---------- auth / profile ----------

class TelegramAuthIn(BaseModel):
    init_data: str = Field(min_length=10, max_length=4096)


class TelegramWidgetIn(BaseModel):
    id: int
    first_name: str = ""
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class DemoLoginIn(BaseModel):
    user_id: int


class OnboardingIn(BaseModel):
    role: Literal["student", "tutor"]
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(default="", max_length=32)
    bio: str = Field(default="", max_length=1500)
    subjects: str = Field(default="", max_length=255)

    @field_validator("full_name", "phone", "bio", "subjects")
    @classmethod
    def strip(cls, v: str) -> str:
        return _clean(v)


class ProfileUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    lang: Lang | None = None
    bio: str | None = Field(default=None, max_length=1500)
    subjects: str | None = Field(default=None, max_length=255)


# ---------- admin ----------

class GroupIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    category: Literal["language", "other"]
    subject: str = Field(min_length=1, max_length=80)
    level: str = Field(default="", max_length=40)
    description: str = Field(default="", max_length=4000)
    price: int = Field(ge=0, le=100_000_000)
    price_period: Literal["month", "course", "lesson"] = "month"
    schedule: str = Field(default="", max_length=160)
    max_students: int = Field(default=5, ge=1, le=100)
    tutor_id: int | None = None
    is_published: bool = True

    @field_validator("title", "subject", "level", "description", "schedule")
    @classmethod
    def strip(cls, v: str) -> str:
        return _clean(v)

    @model_validator(mode="after")
    def language_code(self):
        # Language classes store an ISO code ("en", "ru", "ko"...) so the catalog can group and translate them.
        if self.category == "language":
            self.subject = self.subject.lower()
            if not (2 <= len(self.subject) <= 3 and self.subject.isalpha()):
                raise ValueError("invalid_language_code")
        return self


class AssignStudentIn(BaseModel):
    student_id: int


class PaymentReviewIn(BaseModel):
    status: Literal["approved", "rejected"]
    comment: str = Field(default="", max_length=500)


class TutorDecisionIn(BaseModel):
    status: Literal["approved", "rejected"]
    comment: str = Field(default="", max_length=500)  # reason shown to the teacher (mainly for rejections)


class BlockIn(BaseModel):
    is_blocked: bool


class StrikeIn(BaseModel):
    group_id: int
    student_id: int
    action: Literal["add", "remove", "reset"]


# ---------- tutor ----------

class LessonCreateIn(BaseModel):
    group_id: int
    starts_at: datetime
    duration_min: int = Field(default=60, ge=15, le=240)
    topic: str = Field(default="", max_length=200)
    meet_link: str

    @field_validator("meet_link")
    @classmethod
    def link(cls, v: str) -> str:
        return validate_meeting_link(v)


class LessonUpdateIn(BaseModel):
    starts_at: datetime | None = None
    duration_min: int | None = Field(default=None, ge=15, le=240)
    topic: str | None = Field(default=None, max_length=200)
    meet_link: str | None = None

    @field_validator("meet_link")
    @classmethod
    def link(cls, v: str | None) -> str | None:
        return None if v is None else validate_meeting_link(v)


class LessonRecordIn(BaseModel):
    student_id: int
    attended: bool = True
    hw_status: Literal["done", "strike", "none"] = "none"
    notes: str = Field(default="", max_length=500)


class LessonCompleteIn(BaseModel):
    records: list[LessonRecordIn] = []


# ---------- student ----------

class RatingIn(BaseModel):
    stars: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=500)


class HomeworkIn(BaseModel):
    group_id: int
    link: str
    comment: str = Field(default="", max_length=500)

    @field_validator("link")
    @classmethod
    def valid_link(cls, v: str) -> str:
        return validate_http_url(v)
