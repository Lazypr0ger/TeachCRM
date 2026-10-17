from typing import Any
from uuid import UUID

from app.modules.auth.models import StudentProfile, User, UserRole, UserStatus
from tests.conftest import TEACHER_PASSWORD, AuthTestContext

STUDENT_PASSWORD = "Student-password-123"


def login(context: AuthTestContext, username: str, password: str) -> dict[str, Any]:
    response = context.client.post(
        "/api/v1/auth/login", json={"login": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()


def create_student(context: AuthTestContext, csrf: str, suffix: str = "one") -> dict[str, Any]:
    response = context.client.post(
        "/api/v1/teacher/students",
        headers={"X-CSRF-Token": csrf},
        json={
            "first_name": "Иван",
            "last_name": "Иванов",
            "grade": 7,
            "login": f"student-{suffix}",
            "role": "TEACHER",
        },
    )
    assert response.status_code == 201
    return response.json()


def activate(context: AuthTestContext, token: str) -> None:
    response = context.client.post(
        "/api/v1/auth/activate",
        json={"token": token, "new_password": STUDENT_PASSWORD},
    )
    assert response.status_code == 200


def test_teacher_creates_and_student_activates_account(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    invitation = create_student(auth_context, teacher_session["csrf_token"])

    with auth_context.sessions() as db:
        user = db.get(User, UUID(invitation["user_id"]))
        assert user is not None
        assert user.role == UserRole.STUDENT
        assert user.status == UserStatus.INVITED

    activate(auth_context, invitation["activation_token"])
    student_session = login(auth_context, invitation["login"], STUDENT_PASSWORD)
    assert student_session["user"]["role"] == UserRole.STUDENT

    reused = auth_context.client.post(
        "/api/v1/auth/activate",
        json={"token": invitation["activation_token"], "new_password": STUDENT_PASSWORD},
    )
    assert reused.status_code == 400


def test_csrf_and_role_protect_teacher_endpoints(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    missing_csrf = auth_context.client.post(
        "/api/v1/teacher/students",
        json={"first_name": "Анна", "last_name": "Петрова", "grade": 8},
    )
    assert missing_csrf.status_code == 403

    invitation = create_student(auth_context, teacher_session["csrf_token"], "role")
    activate(auth_context, invitation["activation_token"])
    student_session = login(auth_context, invitation["login"], STUDENT_PASSWORD)
    forbidden = auth_context.client.post(
        "/api/v1/teacher/students",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json={"first_name": "Чужой", "last_name": "Ученик", "grade": 6},
    )
    assert forbidden.status_code == 403

    assert auth_context.client.post("/api/v1/auth/register", json={}).status_code == 404


def test_suspension_revokes_student_session(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    invitation = create_student(auth_context, teacher_session["csrf_token"], "suspend")
    activate(auth_context, invitation["activation_token"])
    login(auth_context, invitation["login"], STUDENT_PASSWORD)
    student_cookie = auth_context.client.cookies.get("tutorcrm_session")

    current_teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    response = auth_context.client.post(
        f"/api/v1/teacher/students/{invitation['student_id']}/suspend",
        headers={"X-CSRF-Token": current_teacher_session["csrf_token"]},
    )
    assert response.status_code == 200

    auth_context.client.cookies.set("tutorcrm_session", student_cookie)
    assert auth_context.client.get("/api/v1/auth/me").status_code == 401


def test_password_reset_revokes_existing_sessions(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    invitation = create_student(auth_context, teacher_session["csrf_token"], "reset")
    activate(auth_context, invitation["activation_token"])
    login(auth_context, invitation["login"], STUDENT_PASSWORD)
    student_cookie = auth_context.client.cookies.get("tutorcrm_session")

    requested = auth_context.client.post(
        "/api/v1/auth/request-password-reset", json={"login": invitation["login"]}
    )
    assert requested.status_code == 200

    current_teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    pending = auth_context.client.get("/api/v1/teacher/password-reset-requests")
    assert pending.status_code == 200
    assert [item["login"] for item in pending.json()] == [invitation["login"]]
    reset_link = auth_context.client.post(
        f"/api/v1/teacher/students/{invitation['student_id']}/password-reset",
        headers={"X-CSRF-Token": current_teacher_session["csrf_token"]},
    )
    assert reset_link.status_code == 200
    assert auth_context.client.get("/api/v1/teacher/password-reset-requests").json() == []
    new_password = "New-student-password-123"
    reset = auth_context.client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_link.json()["reset_token"], "new_password": new_password},
    )
    assert reset.status_code == 200

    auth_context.client.cookies.set("tutorcrm_session", student_cookie)
    assert auth_context.client.get("/api/v1/auth/me").status_code == 401
    assert login(auth_context, invitation["login"], new_password)["user"]["role"] == "STUDENT"


def test_login_error_does_not_reveal_account_existence(auth_context: AuthTestContext) -> None:
    missing = auth_context.client.post(
        "/api/v1/auth/login", json={"login": "missing", "password": "wrong"}
    )
    wrong = auth_context.client.post(
        "/api/v1/auth/login", json={"login": "teacher", "password": "wrong"}
    )
    assert missing.status_code == wrong.status_code == 401
    assert missing.json()["detail"] == wrong.json()["detail"]


def test_only_minimal_student_profile_is_stored(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    invitation = create_student(auth_context, teacher_session["csrf_token"], "minimal")
    with auth_context.sessions() as db:
        profile = db.get(StudentProfile, UUID(invitation["student_id"]))
        assert profile is not None
        assert profile.first_name == "Иван"
        assert profile.grade == 7
