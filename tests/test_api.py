from datetime import timedelta

from sqlalchemy import update

from app.database import SessionLocal
from app.models import Lesson, utcnow
from tests.conftest import ADMIN_TG_ID, Api, receipt

SOON = lambda **kw: (utcnow() + timedelta(**kw)).isoformat()  # noqa: E731


def make_admin(client):
    return Api(client, ADMIN_TG_ID, "Admin")


def make_tutor(client, admin, tg_id=2000, name="Teacher One"):
    tutor = Api(client, tg_id, name)
    res = tutor.post("/api/auth/onboarding", json={
        "role": "tutor", "full_name": name, "subjects": "English", "bio": "I have taught English for five years.",
    })
    assert res.status_code == 200 and res.json()["tutor_status"] == "pending"
    assert admin.post(f"/api/admin/tutors/{tutor.user['id']}/decision", json={"status": "approved"}).status_code == 200
    return tutor


def make_student(client, tg_id=3000, name="Student One"):
    student = Api(client, tg_id, name)
    assert student.post("/api/auth/onboarding", json={"role": "student", "full_name": name}).status_code == 200
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
    res = t.post("/api/auth/onboarding", json={"role": "tutor", "full_name": "Short", "subjects": "", "bio": "hi"})
    assert res.json()["code"] == "tutor_profile_incomplete"
    t.post("/api/auth/onboarding", json={
        "role": "tutor", "full_name": "Short", "subjects": "Math", "bio": "Twenty characters of bio text",
    })
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
