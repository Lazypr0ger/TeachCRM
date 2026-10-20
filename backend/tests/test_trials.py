from uuid import UUID

from app.core.config import Settings, get_settings
from app.main import app
from app.modules.auth.models import StudentProfile
from app.modules.notifications.models import OutboxEvent
from app.modules.trials.models import TrialRequest
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_lessons import create_lesson


def enable_trials() -> None:
    settings = Settings(app_env="test", trial_booking_enabled=True)
    app.dependency_overrides[get_settings] = lambda: settings


def trial_payload(suffix: str = "") -> dict[str, object]:
    return {
        "name": f"Иванов Иван{suffix}",
        "grade": 8,
        "goal": "Подготовка к контрольной",
        "preferred_start": "2030-01-15T19:00:00+03:00",
        "preferred_end": "2030-01-15T20:00:00+03:00",
        "comment": "Удобен вечер",
        "website": "",
    }


def test_public_trial_flag_honeypot_rate_limit_and_authenticated_block(
    auth_context: AuthTestContext,
) -> None:
    public_site = auth_context.client.get("/api/v1/public/site").json()
    assert public_site["trials_enabled"] is False
    assert public_site["brand_name"] == "Tutor CRM"
    assert (
        auth_context.client.post("/api/v1/public/trial-requests", json=trial_payload()).status_code
        == 404
    )
    enable_trials()
    trapped = trial_payload()
    trapped["website"] = "spam.example"
    assert (
        auth_context.client.post("/api/v1/public/trial-requests", json=trapped).status_code == 202
    )
    with auth_context.sessions() as db:
        assert db.query(TrialRequest).count() == 0

    for suffix in ("А", "Б", "В", "Г", "Д"):
        payload = trial_payload()
        payload["name"] = f"Тестов Ученик{suffix}"
        assert (
            auth_context.client.post("/api/v1/public/trial-requests", json=payload).status_code
            == 202
        )
    assert (
        auth_context.client.post("/api/v1/public/trial-requests", json=trial_payload()).status_code
        == 429
    )

    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    assert teacher["csrf_token"]
    assert (
        auth_context.client.post("/api/v1/public/trial-requests", json=trial_payload()).status_code
        == 403
    )


def test_teacher_trial_workflow_conflicts_conversion_and_role_scope(
    auth_context: AuthTestContext,
) -> None:
    enable_trials()
    assert (
        auth_context.client.post("/api/v1/public/trial-requests", json=trial_payload()).status_code
        == 202
    )
    with auth_context.sessions() as db:
        assert db.query(OutboxEvent).filter_by(event_type="TRIAL_RECEIVED").count() == 1

    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    existing = create_student(auth_context, teacher["csrf_token"], "trial-conflict")
    activate(auth_context, existing["activation_token"])
    lesson = create_lesson(auth_context, teacher["csrf_token"], existing["student_id"])
    assert lesson.status_code == 201

    listed = auth_context.client.get("/api/v1/teacher/trial-requests")
    assert listed.status_code == 200
    trial = listed.json()["items"][0]
    overlapping = auth_context.client.patch(
        f"/api/v1/teacher/trial-requests/{trial['id']}",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={
            "status": "CONFIRMED",
            "confirmed_start": "2030-01-15T17:30:00+03:00",
            "confirmed_end": "2030-01-15T18:30:00+03:00",
            "version": trial["version"],
        },
    )
    assert overlapping.status_code == 409
    confirmed = auth_context.client.patch(
        f"/api/v1/teacher/trial-requests/{trial['id']}",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={
            "status": "CONFIRMED",
            "confirmed_start": "2030-01-15T19:00:00+03:00",
            "confirmed_end": "2030-01-15T20:00:00+03:00",
            "version": trial["version"],
        },
    )
    assert confirmed.status_code == 200
    confirmed_trial = confirmed.json()

    blocked_lesson = create_lesson(
        auth_context,
        teacher["csrf_token"],
        existing["student_id"],
        starts_at="2030-01-15T19:30:00+03:00",
        ends_at="2030-01-15T20:30:00+03:00",
    )
    assert blocked_lesson.status_code == 409
    stale = auth_context.client.patch(
        f"/api/v1/teacher/trial-requests/{trial['id']}",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"status": "COMPLETED", "version": trial["version"]},
    )
    assert stale.status_code == 409
    completed = auth_context.client.patch(
        f"/api/v1/teacher/trial-requests/{trial['id']}",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"status": "COMPLETED", "version": confirmed_trial["version"]},
    )
    assert completed.status_code == 200

    converted = auth_context.client.post(
        f"/api/v1/teacher/trial-requests/{trial['id']}/convert",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"login": "trial-student"},
    )
    assert converted.status_code == 200
    assert converted.json()["created"] is True
    assert converted.json()["activation_url"]
    repeated = auth_context.client.post(
        f"/api/v1/teacher/trial-requests/{trial['id']}/convert",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"login": "another-login"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["created"] is False
    assert repeated.json()["student_id"] == converted.json()["student_id"]
    with auth_context.sessions() as db:
        assert db.get(StudentProfile, UUID(converted.json()["student_id"])) is not None

    student_session = login(auth_context, existing["login"], STUDENT_PASSWORD)
    assert auth_context.client.get("/api/v1/teacher/trial-requests").status_code == 403
    assert (
        auth_context.client.patch(
            f"/api/v1/teacher/trial-requests/{trial['id']}",
            headers={"X-CSRF-Token": student_session["csrf_token"]},
            json={"status": "CANCELLED", "version": completed.json()["version"]},
        ).status_code
        == 403
    )
