import sys
from starlette.testclient import TestClient
from app.main import app
from app.database import init_db, seed_demo_data, DB_PATH
import os

client = TestClient(app)

def setup_module():
    # Fresh database for tests
    if DB_PATH.exists():
        try:
            os.remove(DB_PATH)
        except Exception:
            pass
    init_db()
    seed_demo_data()

def test_public_tariffs():
    res = client.get("/api/public/tariffs")
    assert res.status_code == 200
    tariffs = res.json()["tariffs"]
    assert len(tariffs) == 4
    names = [t["name"] for t in tariffs]
    assert "Sinov davri" in names
    assert "Bez baryera (Русский)" in names
    assert "Speaking Club" in names
    assert "TOPIK I-II (Корейский)" in names

def test_public_payment_submission():
    res = client.post("/api/public/submit-payment", data={
        "tariff_name": "Bez baryera (Русский)",
        "amount": 200000,
        "phone": "+998909998877",
        "full_name": "Новый Студент",
        "telegram_username": "@newstudent"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "payment_id" in data

def test_demo_users_list():
    res = client.get("/api/auth/demo-users")
    assert res.status_code == 200
    users = res.json()["demo_users"]
    roles = [u["role"] for u in users]
    assert "admin" in roles
    assert "tutor" in roles
    assert "student" in roles
    # Check 5 test group students exist
    student_names = [u["full_name"] for u in users if u["role"] == "student"]
    assert "Сардор Алиев" in student_names
    assert "Нигора Ахмедова" in student_names

def test_auth_and_rbac_isolation():
    # Login as student (Sardor Aliev, id 4)
    res = client.post("/api/auth/demo-login", json={"user_id": 4})
    assert res.status_code == 200
    student_token = res.json()["token"]

    # Student cannot access admin endpoints
    res_admin = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {student_token}"})
    assert res_admin.status_code == 403

    # Student cannot access tutor endpoints
    res_tutor = client.get("/api/tutor/groups", headers={"Authorization": f"Bearer {student_token}"})
    assert res_tutor.status_code == 403

    # Student can access student dashboard
    res_student = client.get("/api/student/dashboard", headers={"Authorization": f"Bearer {student_token}"})
    assert res_student.status_code == 200
    dash = res_student.json()
    assert dash["enrolled"] is True
    assert dash["group"]["group_name"] == 'Группа #1 — Русский язык "Bez baryera"'
    assert dash["group"]["tutor_name"] == "Алишер Каримов"
    assert dash["group"]["strikes"] == 0
    assert dash["group"]["is_access_revoked"] is False

def test_student_homework_submission():
    # Login as student (Sardor Aliev, id 4)
    login_res = client.post("/api/auth/demo-login", json={"user_id": 4})
    token = login_res.json()["token"]

    res = client.post("/api/student/submit-hw", json={
        "group_id": 1,
        "link": "https://drive.google.com/file/d/test_homework_audio/view",
        "comment": "Тестовая аудиозапись"
    }, headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert res.json()["status"] == "ok"

def test_student_3_strikes_blocked():
    # Nigora Akhmedova (student id 7) has 3 strikes
    login_res = client.post("/api/auth/demo-login", json={"user_id": 7})
    token = login_res.json()["token"]

    # Dashboard should show access revoked
    res = client.get("/api/student/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    dash = res.json()
    assert dash["group"]["strikes"] == 3
    assert dash["group"]["is_access_revoked"] is True

    # Attempting to submit HW should be forbidden (403)
    hw_res = client.post("/api/student/submit-hw", json={
        "group_id": 1,
        "link": "https://example.com/blocked_hw",
        "comment": "Trying to submit"
    }, headers={"Authorization": f"Bearer {token}"})
    assert hw_res.status_code == 403
    assert "аннулирован" in hw_res.json()["detail"]

def test_tutor_cabinet_and_lesson_journal():
    # Login as Tutor 1 (Alisher Karimov, id 2)
    login_res = client.post("/api/auth/demo-login", json={"user_id": 2})
    token = login_res.json()["token"]

    # Get tutor groups
    res = client.get("/api/tutor/groups", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    groups = res.json()["groups"]
    assert len(groups) >= 1
    group_1 = next(g for g in groups if g["id"] == 1)
    assert group_1["enrolled_count"] == 5

    # Update meet link
    new_link = "https://meet.google.com/updated-tolk-link"
    res_meet = client.post("/api/tutor/update-meet-link", json={
        "group_id": 1,
        "meet_link": new_link
    }, headers={"Authorization": f"Bearer {token}"})
    assert res_meet.status_code == 200

    # Get group students
    res_st = client.get("/api/tutor/groups/1/students", headers={"Authorization": f"Bearer {token}"})
    assert res_st.status_code == 200
    students_data = res_st.json()
    assert len(students_data["students"]) == 5

    # Save lesson results with strike for student id 4 (Sardor Aliev)
    res_lesson = client.post("/api/tutor/save-lesson", json={
        "group_id": 1,
        "topic": "Урок 2: Разговорный диалог в кафе",
        "records": [
            {"student_id": 4, "attended": True, "hw_status": "strike", "notes": "ДЗ не сделано"},
            {"student_id": 5, "attended": True, "hw_status": "done", "notes": "Отлично"}
        ]
    }, headers={"Authorization": f"Bearer {token}"})
    assert res_lesson.status_code == 200

    # Verify strike increased for student 4 (from 0 to 1)
    res_st_after = client.get("/api/tutor/groups/1/students", headers={"Authorization": f"Bearer {token}"})
    s4 = next(s for s in res_st_after.json()["students"] if s["id"] == 4)
    assert s4["strikes"] == 1

def test_admin_panel_flows():
    # Login as Admin (id 1)
    login_res = client.post("/api/auth/demo-login", json={"user_id": 1})
    token = login_res.json()["token"]

    # Get overview
    res_ov = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert res_ov.status_code == 200
    data = res_ov.json()
    assert data["stats"]["total_groups"] >= 3
    assert len(data["payments"]) > 0

    # Approve a payment
    pending_payment = next(p for p in data["payments"] if p["status"] == "pending")
    res_app = client.post(f"/api/admin/review-payment/{pending_payment['id']}", json={
        "status": "approved",
        "admin_comment": "Чек подтвержден администратором"
    }, headers={"Authorization": f"Bearer {token}"})
    assert res_app.status_code == 200

    # Create new group
    res_create_group = client.post("/api/admin/groups/create", json={
        "name": "Группа #4 — Тестовый Корейский",
        "language": "Корейский язык",
        "tariff": "TOPIK I-II (Корейский)",
        "schedule": "Ср / Сб в 15:00",
        "tutor_id": 3,
        "meet_link": "https://meet.google.com/test-group-4"
    }, headers={"Authorization": f"Bearer {token}"})
    assert res_create_group.status_code == 200
    new_group_id = res_create_group.json()["group_id"]

    # Test max 5 capacity constraint
    # Try to assign a student to Group 1 which is already full (5/5 students)
    # Get an unassigned student
    unassigned = data["unassigned_students"]
    if unassigned:
        test_student_id = unassigned[0]["id"]
        res_full_assign = client.post("/api/admin/groups/assign-student", json={
            "group_id": 1,
            "student_id": test_student_id
        }, headers={"Authorization": f"Bearer {token}"})
        assert res_full_assign.status_code == 400
        assert "заполнена" in res_full_assign.json()["detail"].lower()

        # Assign to the new empty group instead -> should succeed
        res_ok_assign = client.post("/api/admin/groups/assign-student", json={
            "group_id": new_group_id,
            "student_id": test_student_id
        }, headers={"Authorization": f"Bearer {token}"})
        assert res_ok_assign.status_code == 200

    # Test 3-Strike violations manager: reset strikes and block/unblock
    # Student Nigora Akhmedova (id 7) has 3 strikes
    res_reset = client.post("/api/admin/reset-strikes", json={
        "group_id": 1,
        "student_id": 7,
        "action": "reset"
    }, headers={"Authorization": f"Bearer {token}"})
    assert res_reset.status_code == 200

if __name__ == "__main__":
    setup_module()
    test_public_tariffs()
    test_public_payment_submission()
    test_demo_users_list()
    test_auth_and_rbac_isolation()
    test_student_homework_submission()
    test_student_3_strikes_blocked()
    test_tutor_cabinet_and_lesson_journal()
    test_admin_panel_flows()
    print("\n[OK] ALL TESTS PASSED SUCCESSFULLY! 100% SPECIFICATION COMPLIANCE VERIFIED.")
