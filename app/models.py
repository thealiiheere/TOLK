from pydantic import BaseModel, Field
from typing import Optional, List

class PhoneLoginRequest(BaseModel):
    phone: str
    full_name: Optional[str] = None
    telegram_username: Optional[str] = None

class TelegramAuthRequest(BaseModel):
    id: int
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    username: Optional[str] = None

class DemoLoginRequest(BaseModel):
    user_id: int

class HomeworkSubmitRequest(BaseModel):
    group_id: int
    link: str
    comment: Optional[str] = ""

class MeetLinkUpdateRequest(BaseModel):
    group_id: int
    meet_link: str

class LessonStudentResult(BaseModel):
    student_id: int
    attended: bool = True
    hw_status: str = "done" # 'done', 'strike'
    notes: Optional[str] = ""

class LessonSaveRequest(BaseModel):
    group_id: int
    lesson_date: Optional[str] = None
    topic: Optional[str] = ""
    records: List[LessonStudentResult]

class GroupCreateRequest(BaseModel):
    name: str
    language: str
    tariff: str
    schedule: str
    tutor_id: int
    meet_link: Optional[str] = ""

class StudentAssignRequest(BaseModel):
    group_id: int
    student_id: int

class PaymentReviewRequest(BaseModel):
    status: str # 'approved' or 'rejected'
    admin_comment: Optional[str] = ""

class StrikeActionRequest(BaseModel):
    student_id: int
    group_id: int
    action: str # 'add_strike', 'remove_strike', 'reset'

class UserBlockRequest(BaseModel):
    student_id: int
    group_id: Optional[int] = None
    is_blocked: bool = True
