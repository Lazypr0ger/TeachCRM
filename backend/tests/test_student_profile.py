from uuid import UUID

from app.modules.auth.models import AuditLog
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login


def test_student_reads_and_updates_only_own_profile(auth_context: AuthTestContext) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    invited = create_student(auth_context, teacher["csrf_token"], "own-profile")
    activate(auth_context, invited["activation_token"])
    assert auth_context.client.get("/api/v1/student/profile").status_code == 403

    student = login(auth_context, invited["login"], STUDENT_PASSWORD)
    profile = auth_context.client.get("/api/v1/student/profile")
    assert profile.status_code == 200
    assert profile.json()["id"] == invited["student_id"]
    assert "login" not in profile.json()
    assert (
        auth_context.client.patch(
            "/api/v1/student/profile",
            json={"first_name": "Новое"},
        ).status_code
        == 403
    )
    updated = auth_context.client.patch(
        "/api/v1/student/profile",
        headers={"X-CSRF-Token": student["csrf_token"]},
        json={
            "first_name": "Мария",
            "last_name": "Иванова",
            "patronymic": "",
            "grade": 9,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["first_name"] == "Мария"
    assert updated.json()["patronymic"] is None
    assert updated.json()["grade"] == 9
    with auth_context.sessions() as db:
        audit = (
            db.query(AuditLog)
            .filter_by(
                action="STUDENT_PROFILE_UPDATED",
                entity_id=UUID(invited["student_id"]),
            )
            .one()
        )
        assert audit.actor_user_id == UUID(student["user"]["id"])
