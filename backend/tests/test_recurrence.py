from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.modules.lessons.models import Lesson
from app.modules.scheduling.models import LessonRecurrenceRule, RecurrenceException
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_lessons import create_lesson


def next_weekday(weekday: int) -> date:
    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    days = (weekday - today.weekday()) % 7
    return today + timedelta(days=days or 7)


def recurrence_payload(student_id: str, **changes: object) -> dict[str, object]:
    starts_on = next_weekday(0)
    payload: dict[str, object] = {
        "student_id": student_id,
        "title": "Алгебра по понедельникам",
        "description": "Серия занятий",
        "join_url": "https://telemost.example/series",
        "local_time": "17:00:00",
        "duration_minutes": 60,
        "timezone": "Europe/Moscow",
        "by_weekday": starts_on.weekday(),
        "interval_weeks": 1,
        "starts_on": starts_on.isoformat(),
        "count_limit": 4,
    }
    payload.update(changes)
    return payload


def test_recurrence_materialization_is_idempotent_and_every_other_week(
    auth_context: AuthTestContext,
) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    csrf = teacher_session["csrf_token"]
    student = create_student(auth_context, csrf, "recurrence-idempotent")

    created = auth_context.client.post(
        "/api/v1/teacher/recurrence-rules",
        headers={"X-CSRF-Token": csrf},
        json=recurrence_payload(student["student_id"], interval_weeks=2, count_limit=3),
    )
    assert created.status_code == 201
    assert created.json()["materialized_count"] == 3
    rule_id = created.json()["id"]

    repeated = auth_context.client.post(
        f"/api/v1/teacher/recurrence-rules/{rule_id}/materialize",
        headers={"X-CSRF-Token": csrf},
    )
    assert repeated.status_code == 200
    assert repeated.json()["materialized_count"] == 0
    lessons = auth_context.client.get(
        f"/api/v1/teacher/lessons?student_id={student['student_id']}"
    ).json()["items"]
    assert len(lessons) == 3
    dates = [datetime.fromisoformat(item["starts_at"]).date() for item in lessons]
    assert dates[1] - dates[0] == timedelta(days=14)
    assert all(item["recurrence_rule_id"] == rule_id for item in lessons)


def test_single_occurrence_edit_survives_series_update_and_deactivation(
    auth_context: AuthTestContext,
) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    csrf = teacher_session["csrf_token"]
    student = create_student(auth_context, csrf, "recurrence-edit")
    created = auth_context.client.post(
        "/api/v1/teacher/recurrence-rules",
        headers={"X-CSRF-Token": csrf},
        json=recurrence_payload(student["student_id"], count_limit=3),
    ).json()
    lessons = auth_context.client.get(
        f"/api/v1/teacher/lessons?student_id={student['student_id']}"
    ).json()["items"]

    edited = auth_context.client.patch(
        f"/api/v1/teacher/lessons/{lessons[0]['id']}",
        headers={"X-CSRF-Token": csrf},
        json={"version": lessons[0]["version"], "title": "Индивидуальное изменение"},
    )
    assert edited.status_code == 200
    updated_rule = auth_context.client.patch(
        f"/api/v1/teacher/recurrence-rules/{created['id']}",
        headers={"X-CSRF-Token": csrf},
        json={"version": created["version"], "title": "Новое название серии"},
    )
    assert updated_rule.status_code == 200
    titles = [
        item["title"]
        for item in auth_context.client.get(
            f"/api/v1/teacher/lessons?student_id={student['student_id']}"
        ).json()["items"]
    ]
    assert titles == ["Индивидуальное изменение", "Новое название серии", "Новое название серии"]
    with auth_context.sessions() as db:
        assert db.scalar(select(func.count()).select_from(RecurrenceException)) == 1

    assert (
        auth_context.client.delete(
            f"/api/v1/teacher/recurrence-rules/{created['id']}",
            headers={"X-CSRF-Token": csrf},
        ).status_code
        == 204
    )
    remaining = auth_context.client.get(
        f"/api/v1/teacher/lessons?student_id={student['student_id']}"
    ).json()["items"]
    assert all(item["status"] == "CANCELLED" for item in remaining)


def test_recurrence_conflict_is_atomic_and_role_protected(
    auth_context: AuthTestContext,
) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    csrf = teacher_session["csrf_token"]
    student = create_student(auth_context, csrf, "recurrence-conflict")
    activate(auth_context, student["activation_token"])
    starts_on = next_weekday(0)
    starts_at = datetime.combine(starts_on, time(17), ZoneInfo("Europe/Moscow"))
    assert (
        create_lesson(
            auth_context,
            csrf,
            student["student_id"],
            starts_at=starts_at.isoformat(),
            ends_at=(starts_at + timedelta(hours=1)).isoformat(),
        ).status_code
        == 201
    )

    conflict = auth_context.client.post(
        "/api/v1/teacher/recurrence-rules",
        headers={"X-CSRF-Token": csrf},
        json=recurrence_payload(student["student_id"], starts_on=starts_on.isoformat()),
    )
    assert conflict.status_code == 409
    with auth_context.sessions() as db:
        assert db.scalar(select(func.count()).select_from(LessonRecurrenceRule)) == 0
        assert db.scalar(select(func.count()).select_from(Lesson)) == 1

    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    assert (
        auth_context.client.post(
            "/api/v1/teacher/recurrence-rules",
            headers={"X-CSRF-Token": student_session["csrf_token"]},
            json=recurrence_payload(student["student_id"]),
        ).status_code
        == 403
    )
    login(auth_context, "teacher", TEACHER_PASSWORD)
    assert (
        auth_context.client.post(
            "/api/v1/teacher/recurrence-rules",
            json=recurrence_payload(student["student_id"]),
        ).status_code
        == 403
    )
