from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login


def create_lesson(
    context: AuthTestContext,
    csrf: str,
    student_id: str,
    *,
    starts_at: str = "2030-01-15T17:00:00+03:00",
    ends_at: str = "2030-01-15T18:00:00+03:00",
    title: str = "Алгебра",
) -> Any:
    return context.client.post(
        "/api/v1/teacher/lessons",
        headers={"X-CSRF-Token": csrf},
        json={
            "student_id": student_id,
            "title": title,
            "description": "Квадратные уравнения",
            "starts_at": starts_at,
            "ends_at": ends_at,
            "join_url": "https://telemost.example/lesson",
        },
    )


def test_teacher_creates_and_student_sees_only_own_lesson(
    auth_context: AuthTestContext,
) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    first = create_student(auth_context, teacher_session["csrf_token"], "lesson-owner")
    second = create_student(auth_context, teacher_session["csrf_token"], "lesson-other")
    activate(auth_context, first["activation_token"])
    activate(auth_context, second["activation_token"])

    created = create_lesson(
        auth_context, teacher_session["csrf_token"], first["student_id"]
    )
    assert created.status_code == 201
    assert auth_context.client.get("/api/v1/student/lessons").status_code == 403
    lesson = created.json()
    assert lesson["student_id"] == first["student_id"]
    assert lesson["status"] == "SCHEDULED"

    student_session = login(auth_context, first["login"], STUDENT_PASSWORD)
    own = auth_context.client.get("/api/v1/student/lessons")
    assert own.status_code == 200
    assert [item["id"] for item in own.json()["items"]] == [lesson["id"]]
    assert auth_context.client.get(f"/api/v1/student/lessons/{lesson['id']}").status_code == 200
    assert auth_context.client.post(
        "/api/v1/teacher/lessons",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json={},
    ).status_code == 403

    login(auth_context, second["login"], STUDENT_PASSWORD)
    assert auth_context.client.get(f"/api/v1/student/lessons/{lesson['id']}").status_code == 404
    assert auth_context.client.get("/api/v1/student/lessons").json()["items"] == []


def test_overlap_is_rejected_and_adjacent_lessons_are_allowed(
    auth_context: AuthTestContext,
) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    first = create_student(auth_context, teacher_session["csrf_token"], "overlap-one")
    second = create_student(auth_context, teacher_session["csrf_token"], "overlap-two")
    assert create_lesson(
        auth_context, teacher_session["csrf_token"], first["student_id"]
    ).status_code == 201

    overlapping = create_lesson(
        auth_context,
        teacher_session["csrf_token"],
        second["student_id"],
        starts_at="2030-01-15T17:30:00+03:00",
        ends_at="2030-01-15T18:30:00+03:00",
    )
    assert overlapping.status_code == 409

    adjacent = create_lesson(
        auth_context,
        teacher_session["csrf_token"],
        second["student_id"],
        starts_at="2030-01-15T18:00:00+03:00",
        ends_at="2030-01-15T19:00:00+03:00",
    )
    assert adjacent.status_code == 201


def test_lesson_update_version_and_terminal_states(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher_session["csrf_token"], "states")
    created = create_lesson(
        auth_context, teacher_session["csrf_token"], student["student_id"]
    ).json()
    lesson_url = f"/api/v1/teacher/lessons/{created['id']}"

    stale = auth_context.client.patch(
        lesson_url,
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        json={"version": 99, "title": "Новое название"},
    )
    assert stale.status_code == 409

    updated = auth_context.client.patch(
        lesson_url,
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        json={"version": created["version"], "title": "Новое название"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    completed = auth_context.client.post(
        f"{lesson_url}/complete",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"
    repeated = auth_context.client.post(
        f"{lesson_url}/complete",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
    )
    assert repeated.status_code == 200
    assert repeated.json()["version"] == completed.json()["version"]
    assert auth_context.client.post(
        f"{lesson_url}/cancel",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
    ).status_code == 409


def test_cancelled_slot_becomes_available(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    first = create_student(auth_context, teacher_session["csrf_token"], "cancel-one")
    second = create_student(auth_context, teacher_session["csrf_token"], "cancel-two")
    lesson = create_lesson(
        auth_context, teacher_session["csrf_token"], first["student_id"]
    ).json()
    assert auth_context.client.post(
        f"/api/v1/teacher/lessons/{lesson['id']}/cancel",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
    ).status_code == 200
    replacement = create_lesson(
        auth_context, teacher_session["csrf_token"], second["student_id"]
    )
    assert replacement.status_code == 201


def test_lesson_validation_filters_and_dashboard(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher_session["csrf_token"], "dashboard")
    activate(auth_context, student["activation_token"])
    invalid = create_lesson(
        auth_context,
        teacher_session["csrf_token"],
        student["student_id"],
        starts_at="2030-01-15T18:00:00",
        ends_at="2030-01-15T17:00:00",
    )
    assert invalid.status_code == 422
    bad_url = auth_context.client.post(
        "/api/v1/teacher/lessons",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        json={
            "student_id": student["student_id"],
            "title": "Некорректная ссылка",
            "starts_at": "2030-01-16T17:00:00+03:00",
            "ends_at": "2030-01-16T18:00:00+03:00",
            "join_url": "https://",
        },
    )
    assert bad_url.status_code == 422
    created = create_lesson(
        auth_context, teacher_session["csrf_token"], student["student_id"]
    )
    assert created.status_code == 201
    filtered = auth_context.client.get("/api/v1/teacher/lessons?lesson_status=SCHEDULED")
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1

    login(auth_context, student["login"], STUDENT_PASSWORD)
    dashboard = auth_context.client.get("/api/v1/student/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["next_lesson"]["id"] == created.json()["id"]


def test_teacher_dashboard_lists_today_lessons(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher_session["csrf_token"], "teacher-dashboard")
    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    starts_at = datetime.combine(today, time(0, 1), ZoneInfo("Europe/Moscow"))
    ends_at = datetime.combine(today, time(0, 31), ZoneInfo("Europe/Moscow"))
    created = create_lesson(
        auth_context,
        teacher_session["csrf_token"],
        student["student_id"],
        starts_at=starts_at.isoformat(),
        ends_at=ends_at.isoformat(),
        title="Сегодняшний урок",
    )
    assert created.status_code == 201
    tomorrow = today + timedelta(days=1)
    next_created = create_lesson(
        auth_context,
        teacher_session["csrf_token"],
        student["student_id"],
        starts_at=datetime.combine(tomorrow, time(12), ZoneInfo("Europe/Moscow")).isoformat(),
        ends_at=datetime.combine(tomorrow, time(13), ZoneInfo("Europe/Moscow")).isoformat(),
        title="Следующий урок",
    )
    assert next_created.status_code == 201
    dashboard = auth_context.client.get("/api/v1/teacher/dashboard")
    assert dashboard.status_code == 200
    assert [lesson["id"] for lesson in dashboard.json()["today_lessons"]] == [
        created.json()["id"]
    ]
    assert dashboard.json()["next_lesson"]["id"] == next_created.json()["id"]
    assert dashboard.json()["lessons_today"] == 1
    assert dashboard.json()["pending_payment_claims"] == 0
    assert dashboard.json()["homework_submissions_today"] == 0
    assert dashboard.json()["pending_reschedule_requests"] == 0
