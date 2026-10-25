import io
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import update

from app.database import SessionLocal
from app.models import Lesson, utcnow
from tests.conftest import ADMIN_TG_ID, PNG, Api, receipt

SOON = lambda **kw: (utcnow() + timedelta(**kw)).isoformat()  # noqa: E731


def make_admin(client):
    return Api(client, ADMIN_TG_ID, "Admin")


def make_tutor(client, admin, tg_id=2000, name="Teacher One"):
    tutor = Api(client, tg_id, name)
    res = tutor.post("/api/auth/onboarding", data={
        "role": "tutor", "full_name": name, "subjects": "English", "bio": "I have taught English for five years.",
    }, files=certificates())
    assert res.status_code == 200 and res.json()["tutor_status"] == "pending"
    assert admin.post(f"/api/admin/tutors/{tutor.user['id']}/decision", json={"status": "approved"}).status_code == 200
    return tutor


def certificates(*names):
    """Multipart file list for the onboarding / documents endpoints."""
    return [("certificates", (n, io.BytesIO(PNG), "image/png")) for n in (names or ("ielts.png",))]


def make_student(client, tg_id=3000, name="Student One"):
    student = Api(client, tg_id, name)
    assert student.post("/api/auth/onboarding", data={"role": "student", "full_name": name}).status_code == 200
    return student


def make_group(admin, tutor_id, **overrides):
    body = {
        "title": "English Club", "category": "language", "subject": "EN", "level": "B1", "price": 300000,
        "price_period": "month", "schedule": "Mon 19:00", "max_students": 5, "tutor_id": tutor_id, **overrides,
    }
    res = admin.post("/api/admin/groups", json=body)
    assert res.status_code == 200, res.text
    return res.json()["id"]


def enroll_and_approve(admin, student, group_id):
    res = student.post("/api/student/enroll", data={"group_id": group_id}, files=receipt())
    assert res.status_code == 200, res.text
    pay_id = res.json()["id"]
    assert admin.post(f"/api/admin/payments/{pay_id}/review", json={"status": "approved"}).status_code == 200
    return pay_id


def move_lesson_to_past(lesson_id, hours=3):
    with SessionLocal() as db:
        db.execute(update(Lesson).where(Lesson.id == lesson_id).values(starts_at=utcnow() - timedelta(hours=hours)))
        db.commit()


# ---------- auth ----------

def test_health_and_config(client):
    assert client.get("/health").json()["status"] == "ok"
    cfg = client.get("/api/config").json()
    assert cfg["demo_mode"] is True and "meet.google.com" in cfg["meeting_hosts"]


def test_telegram_login_rejects_tampered_data(client):
    from tests.conftest import init_data

    data = init_data(42).replace("Test", "Evil")
    res = client.post("/api/auth/telegram", json={"init_data": data})
    assert res.status_code == 401 and res.json()["code"] == "tg_auth_invalid"


def test_admin_from_env_and_new_user_needs_onboarding(client):
    admin = make_admin(client)
    assert admin.user["role"] == "admin" and admin.user["onboarded"]
    newbie = Api(client, 5555)
    assert newbie.user["onboarded"] is False
    assert newbie.get("/api/student/dashboard").json()["code"] == "onboarding_required"


def test_role_guards(client):
    admin = make_admin(client)
    student = make_student(client)
    assert client.get("/api/admin/stats").status_code == 401
    assert student.get("/api/admin/stats").status_code == 403
    assert student.get("/api/tutor/dashboard").status_code == 403
    assert admin.get("/api/admin/stats").status_code == 200


def test_tutor_must_be_approved_and_profile_complete(client):
    admin = make_admin(client)
    t = Api(client, 2100, "Short")
    res = t.post("/api/auth/onboarding", data={"role": "tutor", "full_name": "Short", "subjects": "", "bio": "hi"},
                 files=certificates())
    assert res.json()["code"] == "tutor_profile_incomplete"
    t.post("/api/auth/onboarding", data={
        "role": "tutor", "full_name": "Short", "subjects": "Math", "bio": "Twenty characters of bio text",
    }, files=certificates())
    assert t.get("/api/tutor/dashboard").json()["tutor_status"] == "pending"
    assert t.post("/api/tutor/lessons", json={}).status_code == 403
    # Pending teachers can't be assigned to a class
    res = admin.post("/api/admin/groups", json={
        "title": "Physics", "category": "other", "subject": "Math", "price": 1, "tutor_id": t.user["id"],
    })
    assert res.status_code == 404


def test_demo_login_only_for_demo_users(client):
    from app.seed import seed

    with SessionLocal() as db:
        seed(db)
    users = client.get("/api/auth/demo-users").json()
    assert {u["role"] for u in users} == {"admin", "tutor", "student"}
    assert client.post("/api/auth/demo-login", json={"user_id": users[0]["id"]}).status_code == 200
    real = Api(client, 7777)
    assert client.post("/api/auth/demo-login", json={"user_id": real.user["id"]}).status_code == 404


def test_language_preference_and_translated_errors(client):
    student = make_student(client)
    assert student.patch("/api/auth/me", json={"lang": "ru"}).json()["lang"] == "ru"
    res = student.get("/api/admin/stats", headers={"X-Lang": "ru"})
    assert res.json()["detail"] == "У вас нет доступа к этому разделу"
    res = student.get("/api/admin/stats", headers={"X-Lang": "uz"})
    assert res.json()["detail"].startswith("Bu bo'limga")


# ---------- catalog & filters ----------

def test_catalog_filters(client):
    admin = make_admin(client)
    t1 = make_tutor(client, admin, 2001, "Anna English")
    t2 = make_tutor(client, admin, 2002, "Bob Math")
    en = make_group(admin, t1.user["id"], title="English Club", subject="en", price=300000)
    ko = make_group(admin, t1.user["id"], title="Korean", subject="ko", price=450000)
    math = make_group(admin, t2.user["id"], title="SAT Math", category="other", subject="Mathematics", price=200000)
    make_group(admin, t2.user["id"], title="Hidden", subject="de", price=1, is_published=False)
    make_group(admin, None, title="No teacher", subject="fr", price=1)

    def ids(**params):
        return [g["id"] for g in client.get("/api/catalog/groups", params=params).json()]

    assert set(ids()) == {en, ko, math}
    assert set(ids(category="language")) == {en, ko}
    assert ids(category="other") == [math]
    assert ids(subjects="mathematics") == [math]
    assert set(ids(subjects="en,ko")) == {en, ko}
    assert set(ids(price_min=250000, price_max=400000)) == {en}
    assert ids(sort="price_asc") == [math, en, ko]
    assert ids(q="anna") and set(ids(q="anna")) == {en, ko}

    f = client.get("/api/catalog/filters").json()
    assert {x["code"] for x in f["languages"]} == {"en", "ko"}
    assert f["other_subjects"] == [{"name": "Mathematics", "count": 1}]
    assert (f["price_min"], f["price_max"]) == (200000, 450000)
    assert client.get("/api/catalog/groups/999").status_code == 404


# ---------- full enrollment → lesson → rating flow ----------

def test_full_flow(client, fresh_db):
    sent = fresh_db
    admin = make_admin(client)
    tutor = make_tutor(client, admin)
    group_id = make_group(admin, tutor.user["id"])
    student = make_student(client)

    # Enroll with receipt → admin sees it → approve → enrolled
    res = student.post("/api/student/enroll", data={"group_id": group_id}, files=receipt())
    assert res.status_code == 200
    again = student.post("/api/student/enroll", data={"group_id": group_id}, files=receipt())
    assert again.json()["code"] == "payment_pending_exists"
    detail = student.get(f"/api/catalog/groups/{group_id}").json()
    assert detail["my"]["pending_payment"] and not detail["my"]["can_enroll"]
    pending = admin.get("/api/admin/payments").json()
    assert len(pending) == 1 and pending[0]["student"]["full_name"] == "Student One"
    rec = admin.get(f"/api/admin/payments/{pending[0]['id']}/receipt")
    assert rec.status_code == 200 and rec.headers["content-type"] == "image/png"
    assert student.get(f"/api/admin/payments/{pending[0]['id']}/receipt").status_code == 403
    assert admin.post(f"/api/admin/payments/{pending[0]['id']}/review", json={"status": "approved"}).status_code == 200
    assert [c["id"] for c in student.get("/api/student/dashboard").json()["classes"]] == [group_id]
    assert any(chat == 1000 for chat, _ in sent)  # admin was told about the new payment

    # Teacher must give a real meeting link, and a new one for each lesson
    bad = tutor.post("/api/tutor/lessons", json={"group_id": group_id, "starts_at": SOON(days=1), "meet_link": "https://evil.com/x"})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_meeting_link"
    link = "https://meet.google.com/abc-defg-hij"
    lesson = tutor.post("/api/tutor/lessons", json={
        "group_id": group_id, "starts_at": SOON(days=1), "topic": "Intro", "meet_link": link,
    })
    assert lesson.status_code == 200, lesson.text
    lesson_id = lesson.json()["id"]
    reused = tutor.post("/api/tutor/lessons", json={"group_id": group_id, "starts_at": SOON(days=2), "meet_link": link})
    assert reused.json()["code"] == "meeting_link_reused"
    zoom = tutor.post("/api/tutor/lessons", json={
        "group_id": group_id, "starts_at": SOON(days=2), "meet_link": "https://us05web.zoom.us/j/123",
    })
    assert zoom.status_code == 200

    dash = student.get("/api/student/dashboard").json()
    assert [l["meet_link"] for l in dash["upcoming_lessons"]] == [link, "https://us05web.zoom.us/j/123"]

    # Can't rate before the lesson; can't complete a future lesson
    assert student.post(f"/api/student/lessons/{lesson_id}/rate", json={"stars": 5}).json()["code"] == "lesson_not_completed"
    assert tutor.post(f"/api/tutor/lessons/{lesson_id}/complete", json={"records": []}).json()["code"] == "lesson_not_started"

    # Lesson happens → teacher completes it → student rates it
    move_lesson_to_past(lesson_id)
    tdash = tutor.get("/api/tutor/dashboard").json()
    assert [l["id"] for l in tdash["groups"][0]["to_complete"]] == [lesson_id]
    res = tutor.post(f"/api/tutor/lessons/{lesson_id}/complete", json={
        "records": [{"student_id": student.user["id"], "attended": True, "hw_status": "done"}],
    })
    assert res.status_code == 200
    dash = student.get("/api/student/dashboard").json()
    assert [l["id"] for l in dash["to_rate"]] == [lesson_id]
    assert student.post(f"/api/student/lessons/{lesson_id}/rate", json={"stars": 4, "comment": "Nice"}).status_code == 200
    assert student.post(f"/api/student/lessons/{lesson_id}/rate", json={"stars": 5}).json()["code"] == "already_rated"
    assert student.post(f"/api/student/lessons/{lesson_id}/rate", json={"stars": 6}).status_code == 422

    # The rating is now visible in the catalog and drives the rating filter
    card = client.get("/api/catalog/groups").json()[0]
    assert card["tutor"]["rating"] == 4.0 and card["tutor"]["ratings_count"] == 1
    assert len(client.get("/api/catalog/groups", params={"min_rating": 4}).json()) == 1
    assert client.get("/api/catalog/groups", params={"min_rating": 4.5}).json() == []
    profile = client.get(f"/api/catalog/tutors/{tutor.user['id']}").json()
    assert profile["reviews"][0]["comment"] == "Nice" and profile["rating_breakdown"]["4"] == 1


def test_absent_student_cannot_rate_and_outsiders_cannot_rate(client):
    admin = make_admin(client)
    tutor = make_tutor(client, admin)
    group_id = make_group(admin, tutor.user["id"])
    s1, s2, outsider = make_student(client, 3001, "Aziz"), make_student(client, 3002, "Bekzod"), make_student(client, 3003, "Charos")
    enroll_and_approve(admin, s1, group_id)
    enroll_and_approve(admin, s2, group_id)
    lesson_id = tutor.post("/api/tutor/lessons", json={
        "group_id": group_id, "starts_at": SOON(days=1), "meet_link": "https://meet.google.com/aaa-bbbb-ccc",
    }).json()["id"]
    move_lesson_to_past(lesson_id)
    tutor.post(f"/api/tutor/lessons/{lesson_id}/complete", json={"records": [
        {"student_id": s1.user["id"], "attended": True},
        {"student_id": s2.user["id"], "attended": False},
    ]})
    assert s2.post(f"/api/student/lessons/{lesson_id}/rate", json={"stars": 1}).json()["code"] == "lesson_absent"
    assert outsider.post(f"/api/student/lessons/{lesson_id}/rate", json={"stars": 1}).status_code == 403
    assert s1.post(f"/api/student/lessons/{lesson_id}/rate", json={"stars": 5}).status_code == 200


def test_three_strikes_hide_lesson_link(client):
    admin = make_admin(client)
    tutor = make_tutor(client, admin)
    group_id = make_group(admin, tutor.user["id"])
    student = make_student(client)
    enroll_and_approve(admin, student, group_id)
    tutor.post("/api/tutor/lessons", json={
        "group_id": group_id, "starts_at": SOON(days=1), "meet_link": "https://meet.google.com/aaa-bbbb-ccc",
    })
    for _ in range(4):
        tutor.post("/api/tutor/strikes", json={"group_id": group_id, "student_id": student.user["id"], "action": "add"})
    dash = student.get("/api/student/dashboard").json()
    assert dash["classes"][0]["strikes"] == 3 and dash["classes"][0]["access_revoked"]
    assert dash["upcoming_lessons"][0]["meet_link"] is None
    hw = student.post("/api/student/homework", json={"group_id": group_id, "link": "https://drive.google.com/x"})
    assert hw.json()["code"] == "access_revoked"
    assert len(admin.get("/api/admin/violations").json()) == 1
    admin.post("/api/admin/strikes", json={"group_id": group_id, "student_id": student.user["id"], "action": "reset"})
    assert student.get("/api/student/dashboard").json()["upcoming_lessons"][0]["meet_link"]


def test_group_capacity_and_admin_management(client):
    admin = make_admin(client)
    tutor = make_tutor(client, admin)
    group_id = make_group(admin, tutor.user["id"], max_students=1)
    s1, s2 = make_student(client, 3001, "Aziz"), make_student(client, 3002, "Bekzod")
    assert admin.post(f"/api/admin/groups/{group_id}/students", json={"student_id": s1.user["id"]}).status_code == 200
    assert s2.post("/api/student/enroll", data={"group_id": group_id}, files=receipt()).json()["code"] == "group_full"
    assert admin.post(f"/api/admin/groups/{group_id}/students", json={"student_id": s2.user["id"]}).json()["code"] == "group_full"
    body = {"title": "Renamed", "category": "language", "subject": "en", "price": 1, "max_students": 0}
    assert admin.put(f"/api/admin/groups/{group_id}", json=body).status_code == 422
    body["max_students"] = 3
    assert admin.put(f"/api/admin/groups/{group_id}", json={**body, "tutor_id": tutor.user["id"]}).status_code == 200
    groups = admin.get("/api/admin/groups").json()
    assert groups[0]["title"] == "Renamed" and groups[0]["students"][0]["full_name"] == "Aziz"
    assert admin.delete(f"/api/admin/groups/{group_id}/students/{s1.user['id']}").status_code == 200
    assert admin.delete(f"/api/admin/groups/{group_id}").status_code == 200
    assert admin.get("/api/admin/groups").json() == []


def test_blocked_user_is_signed_out(client):
    admin = make_admin(client)
    student = make_student(client)
    assert admin.post(f"/api/admin/users/{student.user['id']}/block", json={"is_blocked": True}).status_code == 200
    assert student.get("/api/auth/me").status_code == 401  # session revoked
    from tests.conftest import init_data

    res = client.post("/api/auth/telegram", json={"init_data": init_data(3000)})
    assert res.json()["code"] == "account_blocked"
    assert admin.post(f"/api/admin/users/{admin.user['id']}/block", json={"is_blocked": True}).json()["code"] == "cannot_block_admin"


def test_receipt_upload_validation(client):
    import io

    admin = make_admin(client)
    tutor = make_tutor(client, admin)
    group_id = make_group(admin, tutor.user["id"])
    student = make_student(client)
    fake = {"receipt": ("evil.png", io.BytesIO(b"<script>alert(1)</script>"), "image/png")}
    assert student.post("/api/student/enroll", data={"group_id": group_id}, files=fake).json()["code"] == "receipt_bad_type"
    assert student.post("/api/student/enroll", data={"group_id": group_id}).json()["code"] == "receipt_required"


# ---------- teacher certificates ----------

def tutor_application(client, tg_id=2500, files=None):
    t = Api(client, tg_id, "Applicant")
    body = {"role": "tutor", "full_name": "Applicant", "subjects": "IELTS", "bio": "IELTS 8.0, three years of teaching."}
    return t, t.post("/api/auth/onboarding", data=body, files=files if files is not None else certificates())


def test_teacher_sign_up_requires_certificate(client):
    t, res = tutor_application(client, files=[])
    assert res.json()["code"] == "certificates_required"
    assert t.get("/api/auth/me").json()["onboarded"] is False  # nothing was saved
    fake = [("certificates", ("cert.png", io.BytesIO(b"<html>not an image</html>"), "image/png"))]
    t, res = tutor_application(client, tg_id=2501, files=fake)
    assert res.json()["code"] == "receipt_bad_type"
    t, res = tutor_application(client, tg_id=2502, files=certificates(*[f"c{i}.png" for i in range(6)]))
    assert res.json()["code"] == "too_many_documents"
    t, res = tutor_application(client, tg_id=2503, files=certificates("diploma.png", "../../etc/ielts.png"))
    assert res.status_code == 200 and res.json()["tutor_status"] == "pending"
    assert [d["name"] for d in t.get("/api/tutor/documents").json()] == ["diploma.png", "ielts.png"]


def test_admin_reviews_documents_and_rejects_with_reason(client, fresh_db):
    sent = fresh_db
    admin = make_admin(client)
    t, _ = tutor_application(client)
    applicant = next(x for x in admin.get("/api/admin/tutors").json() if x["id"] == t.user["id"])
    doc = applicant["documents"][0]
    assert doc["content_type"] == "image/png"
    url = f"/api/admin/tutors/{t.user['id']}/documents/{doc['id']}"
    file = admin.get(url)
    assert file.status_code == 200 and file.content == PNG and file.headers["cache-control"] == "private, no-store"
    assert t.get(url).status_code == 403  # documents are admin-only
    assert admin.get(f"/api/admin/tutors/{t.user['id'] + 1}/documents/{doc['id']}").status_code == 404

    res = admin.post(f"/api/admin/tutors/{t.user['id']}/decision", json={"status": "rejected", "comment": "Blurry scan"})
    assert res.status_code == 200
    me = t.get("/api/auth/me").json()
    assert me["tutor_status"] == "rejected" and me["tutor_review_note"] == "Blurry scan"
    assert any("Blurry scan" in text for _, text in sent)

    # Uploading new documents re-applies
    res = t.post("/api/tutor/documents", files=certificates("clear-scan.png"))
    assert res.status_code == 200 and res.json()["tutor_status"] == "pending" and len(res.json()["documents"]) == 2
    assert admin.post(f"/api/admin/tutors/{t.user['id']}/decision", json={"status": "approved"}).status_code == 200
    assert t.get("/api/auth/me").json()["tutor_status"] == "approved"


def test_teacher_without_documents_cannot_be_approved(client):
    from app.models import TutorDocument, User
    from sqlalchemy import delete, select

    admin = make_admin(client)
    t, _ = tutor_application(client)
    with SessionLocal() as db:  # e.g. a teacher who signed up before certificates were required
        db.execute(delete(TutorDocument).where(TutorDocument.tutor_id == t.user["id"]))
        db.commit()
    res = admin.post(f"/api/admin/tutors/{t.user['id']}/decision", json={"status": "approved"})
    assert res.json()["code"] == "tutor_no_documents"
    with SessionLocal() as db:
        assert db.scalar(select(User.tutor_status).where(User.id == t.user["id"])) == "pending"


def test_admin_id_added_while_signed_in_is_applied(client, monkeypatch):
    from app.config import settings

    user = make_student(client, tg_id=4242)
    assert user.get("/api/admin/stats").status_code == 403
    monkeypatch.setattr(type(settings), "admin_ids", property(lambda self: {1000, 4242}))
    assert user.get("/api/auth/me").json()["role"] == "admin"
    assert user.get("/api/admin/stats").status_code == 200


# ---------- course codes ----------

def test_course_codes_generated_validated_and_searchable(client):
    admin = make_admin(client)
    tutor = make_tutor(client, admin)
    tid = tutor.user["id"]
    a = make_group(admin, tid, title="Club A")
    b = make_group(admin, tid, title="Club B")
    m = make_group(admin, tid, title="SAT", category="other", subject="Mathematics")
    custom = make_group(admin, tid, title="IELTS Intensive", code=" ielts-7 ")
    codes = {g["id"]: g["code"] for g in admin.get("/api/admin/groups").json()}
    assert (codes[a], codes[b], codes[m], codes[custom]) == ("EN-101", "EN-102", "MAT-101", "IELTS-7")

    def create(code):
        return admin.post("/api/admin/groups", json={
            "code": code, "title": "Dup", "category": "language", "subject": "en", "price": 1, "tutor_id": tid,
        })

    taken = create("ielts-7")
    assert taken.status_code == 409 and taken.json()["code"] == "course_code_taken" and "IELTS-7" in taken.json()["detail"]
    assert create("bad code!").json()["code"] == "invalid_course_code"
    assert create("-X").json()["code"] == "invalid_course_code"

    # Editing: empty keeps the code, another class's code is rejected, a new free code is accepted
    body = {"title": "Club A", "category": "language", "subject": "en", "price": 1, "tutor_id": tid}
    assert admin.put(f"/api/admin/groups/{a}", json={**body, "code": ""}).json()["code"] == "EN-101"
    assert admin.put(f"/api/admin/groups/{a}", json={**body, "code": "en-102"}).json()["code"] == "course_code_taken"
    assert admin.put(f"/api/admin/groups/{a}", json={**body, "code": "ENG-A1"}).json()["code"] == "ENG-A1"

    # Students find classes by code (any case, partial)
    def found(q):
        return [g["id"] for g in client.get("/api/catalog/groups", params={"q": q}).json()]

    assert found("ielts-7") == [custom]
    assert found("eng-a1") == [a]
    assert set(found("mat-1")) == {m}
    assert client.get(f"/api/catalog/groups/{a}").json()["code"] == "ENG-A1"


# ---------- course posters ----------

def _image_bytes(fmt="PNG", size=(2400, 1600), exif_gps=False):
    from PIL import Image

    img = Image.new("RGB", size, (200, 80, 40))
    buf = io.BytesIO()
    if exif_gps:
        exif = Image.Exif()
        exif[0x8825] = {1: "N", 2: (41.0, 18.0, 0.0)}  # GPS IFD
        img.save(buf, fmt, exif=exif)
    else:
        img.save(buf, fmt)
    return buf.getvalue()


def test_course_poster_upload_replace_remove(client):
    from PIL import Image

    from app.config import settings

    admin = make_admin(client)
    tutor = make_tutor(client, admin)
    gid = make_group(admin, tutor.user["id"])
    assert client.get(f"/api/catalog/groups/{gid}").json()["poster_url"] is None

    jpg = _image_bytes("JPEG", exif_gps=True)
    res = admin.post(f"/api/admin/groups/{gid}/poster", files={"poster": ("photo.jpg", io.BytesIO(jpg), "image/jpeg")})
    assert res.status_code == 200, res.text
    url = res.json()["poster_url"]
    assert client.get(f"/api/catalog/groups/{gid}").json()["poster_url"] == url
    assert client.get("/api/catalog/groups").json()[0]["poster_url"] == url

    img = client.get(url)  # public, cacheable, re-encoded
    assert img.status_code == 200 and img.headers["content-type"] == "image/webp"
    assert "immutable" in img.headers["cache-control"]
    served = Image.open(io.BytesIO(img.content))
    assert served.format == "WEBP" and served.size == (1200, 800)  # fitted into 1280x800, aspect kept
    assert not served.getexif().get_ifd(0x8825)  # GPS stripped

    poster_dir = Path(settings.upload_dir) / "posters"
    first = url.rsplit("/", 1)[1]
    res = admin.post(f"/api/admin/groups/{gid}/poster", files={"poster": ("p.png", io.BytesIO(_image_bytes()), "image/png")})
    second = res.json()["poster_url"].rsplit("/", 1)[1]
    assert second != first and not (poster_dir / first).exists() and (poster_dir / second).exists()

    assert admin.delete(f"/api/admin/groups/{gid}/poster").status_code == 200
    assert client.get(f"/api/catalog/groups/{gid}").json()["poster_url"] is None
    assert not (poster_dir / second).exists()


def test_course_poster_validation_and_cleanup(client):
    from app.config import settings

    admin = make_admin(client)
    student = make_student(client)
    tutor = make_tutor(client, admin)
    gid = make_group(admin, tutor.user["id"])

    def upload(api, name, data, ctype):
        return api.post(f"/api/admin/groups/{gid}/poster", files={"poster": (name, io.BytesIO(data), ctype)})

    assert upload(student, "p.png", _image_bytes(), "image/png").status_code == 403
    assert upload(admin, "doc.pdf", b"%PDF-1.4 x", "application/pdf").json()["code"] == "poster_bad_type"
    assert upload(admin, "fake.png", b"\x89PNG\r\n\x1a\n" + b"garbage" * 10, "image/png").json()["code"] == "poster_bad_type"
    assert upload(admin, "x.txt", b"hello", "text/plain").json()["code"] == "receipt_bad_type"
    assert admin.post(f"/api/admin/groups/{gid}/poster").json()["code"] == "poster_required"
    assert client.get("/api/catalog/posters/..%2F..%2F.env").status_code == 404
    assert client.get("/api/catalog/posters/poster_000000000000000000000000.webp").status_code == 404

    name = upload(admin, "p.png", _image_bytes(), "image/png").json()["poster_url"].rsplit("/", 1)[1]
    assert admin.delete(f"/api/admin/groups/{gid}").status_code == 200  # deleting the class removes its poster
    assert not (Path(settings.upload_dir) / "posters" / name).exists()


# ---------- cache ----------

def test_cache_off_without_redis_url(client):
    from app import cache

    assert cache.client() is None and cache.status() == "off"
    cache.set_json("k", {"a": 1})
    assert cache.get_json("k") is None
    cache.delete("k")
    assert client.get("/health").json()["cache"] == "off"


def test_cache_unreachable_redis_is_a_miss_not_an_error(client, monkeypatch):
    from app import cache
    from app.config import settings

    monkeypatch.setattr(settings, "redis_url", "redis://127.0.0.1:1/0")  # nothing listens on port 1
    monkeypatch.setattr(cache, "_client", None)
    cache.set_json("k", {"a": 1})
    assert cache.get_json("k") is None
    res = client.get("/health")  # status() → "unavailable", and the health check still passes
    assert res.status_code == 200 and res.json()["cache"] == "unavailable"


class FakeRedis:
    """In-memory stand-in for the few Redis commands app.cache uses (TTLs are ignored)."""

    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ex=None):
        self.data[key] = value

    def delete(self, *keys):
        for k in keys:
            self.data.pop(k, None)

    def incr(self, key):
        self.data[key] = str(int(self.data.get(key, 0)) + 1)
        return int(self.data[key])

    def expire(self, key, seconds, nx=False):
        return True

    def ping(self):
        return True

    def pipeline(self, transaction=True):
        fake = self

        class Pipeline:
            def __init__(self):
                self.ops = []

            def __getattr__(self, name):
                return lambda *a, **kw: self.ops.append((name, a, kw))

            def execute(self):
                return [getattr(fake, name)(*a, **kw) for name, a, kw in self.ops]

        return Pipeline()


@pytest.fixture
def fake_redis(monkeypatch):
    from app import cache
    from app.config import settings

    fake = FakeRedis()
    monkeypatch.setattr(settings, "redis_url", "redis://fake")
    monkeypatch.setattr(cache, "_client", fake)
    return fake


def _raw_price(group_id, price):
    """Change the database behind the app's back (no session events), to see whether an answer came from the cache."""
    from sqlalchemy import text

    from app.database import engine

    with engine.begin() as conn:
        conn.execute(text("UPDATE groups SET price = :p WHERE id = :id"), {"p": price, "id": group_id})


def test_catalog_is_cached_and_forgotten_after_changes(client, fake_redis):
    admin = make_admin(client)
    tutor = make_tutor(client, admin)
    gid = make_group(admin, tutor.user["id"], price=300000)
    price = lambda: client.get("/api/catalog/groups").json()[0]["price"]  # noqa: E731
    page = lambda: client.get(f"/api/catalog/groups/{gid}").json()  # noqa: E731

    assert price() == 300000 and page()["price"] == 300000
    _raw_price(gid, 1)
    assert price() == 300000 and page()["price"] == 300000  # served from the cache

    # an edit through the app forgets every catalog answer at once
    body = {"title": "English Club", "category": "language", "subject": "en", "level": "B1", "price": 250000,
            "price_period": "month", "schedule": "Mon 19:00", "max_students": 5, "tutor_id": tutor.user["id"]}
    assert admin.put(f"/api/admin/groups/{gid}", json=body).status_code == 200
    assert price() == 250000 and page()["price"] == 250000

    # an enrollment changes the seats everywhere right away
    student = make_student(client)
    assert page()["seats_left"] == 5
    enroll_and_approve(admin, student, gid)
    assert page()["seats_left"] == 4
    assert client.get("/api/catalog/groups").json()[0]["seats_left"] == 4
    assert client.get(f"/api/catalog/tutors/{tutor.user['id']}").json()["groups"][0]["seats_left"] == 4
    # the per-visitor part is never cached
    assert student.get(f"/api/catalog/groups/{gid}").json()["my"]["enrolled"] is True
    assert client.get(f"/api/catalog/groups/{gid}").json()["my"]["enrolled"] is False


def test_student_sign_in_keeps_the_catalog_cache(client, fake_redis):
    admin = make_admin(client)
    gid = make_group(admin, make_tutor(client, admin).user["id"])
    client.get("/api/catalog/groups")
    version = fake_redis.get("tolk:catalog:version")
    make_student(client, tg_id=3100)
    Api(client, 3100, "Student One").get("/api/auth/me")
    assert fake_redis.get("tolk:catalog:version") == version
    assert client.get(f"/api/catalog/groups/{gid}").status_code == 200


def test_admin_stats_are_cached_and_forgotten_after_changes(client, fake_redis):
    admin = make_admin(client)
    gid = make_group(admin, make_tutor(client, admin).user["id"])
    assert admin.get("/api/admin/stats").json()["pending_payments"] == 0
    assert "tolk:admin:stats" in fake_redis.data

    student = make_student(client)
    res = student.post("/api/student/enroll", data={"group_id": gid}, files=receipt())
    assert res.status_code == 200
    assert admin.get("/api/admin/stats").json()["pending_payments"] == 1  # never a stale "0 to review"
    assert admin.post(f"/api/admin/payments/{res.json()['id']}/review", json={"status": "approved"}).status_code == 200
    s = admin.get("/api/admin/stats").json()
    assert s["pending_payments"] == 0 and s["enrollments"] == 1 and s["revenue_total"] == 300000


# ---------- rate limits ----------

def _forged():
    """A sign-in with a broken signature (rejected with 401)."""
    from tests.conftest import init_data

    return init_data(42).replace("Test", "Evil")


def test_sign_in_is_rate_limited_per_ip(client, fake_redis, monkeypatch):
    from app import ratelimit

    monkeypatch.setitem(ratelimit.LIMITS, "signin", (3, 600))
    for _ in range(3):  # failed attempts count too
        assert client.post("/api/auth/telegram", json={"init_data": _forged()}).status_code == 401
    res = client.post("/api/auth/telegram", json={"init_data": _forged()}, headers={"X-Lang": "ru"})
    assert res.status_code == 429 and res.json()["code"] == "too_many_requests"
    assert "Попробуйте снова через" in res.json()["detail"]
    assert 0 < int(res.headers["Retry-After"]) <= 600


def test_receipt_uploads_are_rate_limited_per_student(client, fake_redis, monkeypatch):
    from app import ratelimit

    monkeypatch.setitem(ratelimit.LIMITS, "enroll", (2, 3600))
    admin = make_admin(client)
    gid = make_group(admin, make_tutor(client, admin).user["id"])
    first, second = make_student(client), make_student(client, tg_id=3001, name="Student Two")
    for _ in range(2):
        assert first.post("/api/student/enroll", data={"group_id": 999}, files=receipt()).status_code == 404
    assert first.post("/api/student/enroll", data={"group_id": gid}, files=receipt()).status_code == 429
    assert second.post("/api/student/enroll", data={"group_id": gid}, files=receipt()).status_code == 200


def test_no_limits_without_redis(client, monkeypatch):
    from app import ratelimit

    monkeypatch.setitem(ratelimit.LIMITS, "signin", (1, 600))  # the cache is off in tests by default
    for _ in range(3):
        assert client.post("/api/auth/telegram", json={"init_data": _forged()}).status_code == 401
