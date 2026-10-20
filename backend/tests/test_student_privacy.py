from uuid import UUID

from app.modules.auth.models import AuditLog, SessionRecord, StudentProfile, User
from app.modules.billing.models import Invoice
from app.modules.files.storage import get_storage
from app.modules.notifications.models import Notification
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_invoices import set_profile
from tests.test_lessons import create_lesson


class FakeStorage:
    def delete(self, _key: str) -> None:
        pass


def test_teacher_exports_then_anonymizes_student_and_preserves_finance(
    auth_context: AuthTestContext,
) -> None:
    auth_context.client.app.dependency_overrides[get_storage] = lambda: FakeStorage()
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher["csrf_token"], "privacy")
    activate(auth_context, student["activation_token"])
    set_profile(auth_context, teacher["csrf_token"], student["student_id"])
    lesson = create_lesson(auth_context, teacher["csrf_token"], student["student_id"]).json()
    assert auth_context.client.post(
        f"/api/v1/teacher/lessons/{lesson['id']}/complete",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
    ).status_code == 200
    login(auth_context, student["login"], STUDENT_PASSWORD)
    student_cookie = auth_context.client.cookies.get("tutorcrm_session")
    assert (
        auth_context.client.get(
            f"/api/v1/teacher/students/{student['student_id']}/export"
        ).status_code
        == 403
    )

    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    exported = auth_context.client.get(
        f"/api/v1/teacher/students/{student['student_id']}/export"
    )
    assert exported.status_code == 200
    assert exported.headers["Cache-Control"] == "private, no-store"
    assert exported.json()["profile"]["last_name"] == "Иванов"
    assert len(exported.json()["invoices"]) == 1
    assert "password_hash" not in exported.text
    assert "storage_key" not in exported.text

    wrong = auth_context.client.post(
        f"/api/v1/teacher/students/{student['student_id']}/anonymize",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"confirmation": "wrong-login"},
    )
    assert wrong.status_code == 409
    anonymized = auth_context.client.post(
        f"/api/v1/teacher/students/{student['student_id']}/anonymize",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"confirmation": student["login"]},
    )
    assert anonymized.status_code == 200

    with auth_context.sessions() as db:
        profile = db.get(StudentProfile, UUID(student["student_id"]))
        user = db.get(User, UUID(student["user_id"]))
        assert profile is not None and user is not None
        assert (profile.last_name, profile.first_name, profile.grade) == (
            "Удалённый",
            "Ученик",
            None,
        )
        assert user.login.startswith("anonymized-")
        assert user.password_hash is None
        assert db.query(Invoice).filter_by(student_id=profile.id).count() == 1
        assert db.query(SessionRecord).filter_by(user_id=user.id).count() == 0
        assert db.query(Notification).filter_by(recipient_user_id=user.id).count() == 0
        assert db.query(AuditLog).filter_by(action="STUDENT_DATA_EXPORTED").count() == 1
        assert db.query(AuditLog).filter_by(action="STUDENT_ANONYMIZED").count() == 1

    auth_context.client.cookies.set("tutorcrm_session", student_cookie)
    assert auth_context.client.get("/api/v1/auth/me").status_code == 401
