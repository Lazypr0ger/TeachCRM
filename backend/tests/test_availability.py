from datetime import date

from app.modules.scheduling.service import week_matches
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_lessons import create_lesson


def rule_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "timezone": "Europe/Moscow",
        "weekday": 1,
        "local_start_time": "17:00:00",
        "local_end_time": "18:00:00",
        "week_parity": "ALL",
        "cycle_anchor_date": "2030-01-15",
        "effective_from": "2030-01-01",
        "effective_until": None,
        "is_available": True,
    }
    payload.update(changes)
    return payload


def exception_payload(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "starts_at": "2030-01-15T17:15:00+03:00",
        "ends_at": "2030-01-15T17:45:00+03:00",
        "kind": "BLOCKED",
        "private_reason": "Личная причина",
    }
    payload.update(changes)
    return payload


def test_teacher_rules_restrict_lesson_times(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    csrf = teacher_session["csrf_token"]
    student = create_student(auth_context, csrf, "availability-rule")

    created_rule = auth_context.client.post(
        "/api/v1/teacher/availability-rules",
        headers={"X-CSRF-Token": csrf},
        json=rule_payload(),
    )
    assert created_rule.status_code == 201
    assert len(auth_context.client.get("/api/v1/teacher/availability-rules").json()) == 1

    outside = create_lesson(
        auth_context,
        csrf,
        student["student_id"],
        starts_at="2030-01-15T18:00:00+03:00",
        ends_at="2030-01-15T19:00:00+03:00",
    )
    assert outside.status_code == 409
    assert "доступное время" in outside.json()["detail"]
    assert create_lesson(auth_context, csrf, student["student_id"]).status_code == 201

    deleted = auth_context.client.delete(
        f"/api/v1/teacher/availability-rules/{created_rule.json()['id']}",
        headers={"X-CSRF-Token": csrf},
    )
    assert deleted.status_code == 204


def test_block_and_override_exceptions_are_enforced(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    csrf = teacher_session["csrf_token"]
    student = create_student(auth_context, csrf, "availability-exception")

    blocked = auth_context.client.post(
        "/api/v1/teacher/availability-exceptions",
        headers={"X-CSRF-Token": csrf},
        json=exception_payload(),
    )
    assert blocked.status_code == 201
    conflict = create_lesson(auth_context, csrf, student["student_id"])
    assert conflict.status_code == 409
    assert "недоступен" in conflict.json()["detail"]

    overlapping = auth_context.client.post(
        "/api/v1/teacher/availability-exceptions",
        headers={"X-CSRF-Token": csrf},
        json=exception_payload(kind="AVAILABLE_OVERRIDE"),
    )
    assert overlapping.status_code == 409
    assert (
        auth_context.client.delete(
            f"/api/v1/teacher/availability-exceptions/{blocked.json()['id']}",
            headers={"X-CSRF-Token": csrf},
        ).status_code
        == 204
    )

    assert (
        auth_context.client.post(
            "/api/v1/teacher/availability-rules",
            headers={"X-CSRF-Token": csrf},
            json=rule_payload(),
        ).status_code
        == 201
    )
    override = auth_context.client.post(
        "/api/v1/teacher/availability-exceptions",
        headers={"X-CSRF-Token": csrf},
        json=exception_payload(
            starts_at="2030-01-15T18:00:00+03:00",
            ends_at="2030-01-15T19:00:00+03:00",
            kind="AVAILABLE_OVERRIDE",
        ),
    )
    assert override.status_code == 201
    assert (
        create_lesson(
            auth_context,
            csrf,
            student["student_id"],
            starts_at="2030-01-15T18:00:00+03:00",
            ends_at="2030-01-15T19:00:00+03:00",
        ).status_code
        == 201
    )


def test_student_busy_mark_warns_but_keeps_lesson(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher_session["csrf_token"], "student-busy")
    activate(auth_context, student["activation_token"])
    lesson = create_lesson(
        auth_context, teacher_session["csrf_token"], student["student_id"]
    ).json()

    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    created = auth_context.client.post(
        "/api/v1/student/availability",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json={
            "starts_at": "2030-01-15T17:30:00+03:00",
            "ends_at": "2030-01-15T18:30:00+03:00",
            "state": "BUSY",
        },
    )
    assert created.status_code == 201
    assert created.json()["conflicts_with_lesson"] is True
    schedule = auth_context.client.get("/api/v1/student/schedule")
    assert schedule.status_code == 200
    assert [item["id"] for item in schedule.json()["lessons"]] == [lesson["id"]]
    assert schedule.json()["lessons"][0]["status"] == "SCHEDULED"
    assert "private_reason" not in str(schedule.json())

    overlap = auth_context.client.post(
        "/api/v1/student/availability",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json={
            "starts_at": "2030-01-15T18:00:00+03:00",
            "ends_at": "2030-01-15T19:00:00+03:00",
            "state": "AVAILABLE",
        },
    )
    assert overlap.status_code == 409


def test_student_mark_ownership_csrf_and_roles(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    first = create_student(auth_context, teacher_session["csrf_token"], "mark-owner")
    second = create_student(auth_context, teacher_session["csrf_token"], "mark-other")
    activate(auth_context, first["activation_token"])
    activate(auth_context, second["activation_token"])

    first_session = login(auth_context, first["login"], STUDENT_PASSWORD)
    payload = {
        "starts_at": "2030-01-16T17:00:00+03:00",
        "ends_at": "2030-01-16T18:00:00+03:00",
        "state": "AVAILABLE",
    }
    assert auth_context.client.post("/api/v1/student/availability", json=payload).status_code == 403
    created = auth_context.client.post(
        "/api/v1/student/availability",
        headers={"X-CSRF-Token": first_session["csrf_token"]},
        json=payload,
    )
    assert created.status_code == 201

    second_session = login(auth_context, second["login"], STUDENT_PASSWORD)
    assert (
        auth_context.client.patch(
            f"/api/v1/student/availability/{created.json()['id']}",
            headers={"X-CSRF-Token": second_session["csrf_token"]},
            json={**payload, "state": "BUSY"},
        ).status_code
        == 404
    )
    assert auth_context.client.get("/api/v1/teacher/availability-rules").status_code == 403

    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    assert (
        auth_context.client.post(
            "/api/v1/student/availability",
            headers={"X-CSRF-Token": teacher_session["csrf_token"]},
            json=payload,
        ).status_code
        == 403
    )


def test_ab_week_parity_uses_anchor_week() -> None:
    anchor = date(2030, 1, 7)
    assert week_matches(date(2030, 1, 7), anchor, "A")
    assert not week_matches(date(2030, 1, 14), anchor, "A")
    assert week_matches(date(2030, 1, 14), anchor, "B")
    assert week_matches(date(2029, 12, 31), anchor, "B")
    assert week_matches(date(2030, 1, 14), anchor, "ALL")
