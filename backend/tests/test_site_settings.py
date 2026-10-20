from app.core.config import Settings, get_settings
from app.main import app
from app.modules.auth.models import AuditLog
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login


def enable_trial_feature() -> None:
    settings = Settings(app_env="test", trial_booking_enabled=True)
    app.dependency_overrides[get_settings] = lambda: settings


def test_public_site_content_and_teacher_versioned_update(
    auth_context: AuthTestContext,
) -> None:
    enable_trial_feature()
    public = auth_context.client.get("/api/v1/public/site")
    assert public.status_code == 200
    assert public.json()["trials_enabled"] is True
    assert "public_phone" not in public.json()
    assert "payment_details" not in public.json()

    assert auth_context.client.get("/api/v1/teacher/settings/site").status_code == 401
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    settings = auth_context.client.get("/api/v1/teacher/settings/site")
    assert settings.status_code == 200
    assert settings.json()["version"] == 0
    assert settings.json()["trial_feature_available"] is True

    missing_csrf = auth_context.client.patch(
        "/api/v1/teacher/settings/site", json={"brand_name": "Математика", "version": 0}
    )
    assert missing_csrf.status_code == 403
    updated = auth_context.client.patch(
        "/api/v1/teacher/settings/site",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={
            "brand_name": "Математика с преподавателем",
            "tagline": "Понятные занятия",
            "directions": ["Алгебра", "Геометрия"],
            "advantages": ["План занятий виден ученику"],
            "confirmed_results": ["Результат подтверждён владельцем"],
            "pricing_text": "Стоимость согласуется до начала занятий.",
            "privacy_text": "Сохраняются только ФИО и класс ученика.",
            "trials_enabled": False,
            "version": 0,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 1
    assert updated.json()["trials_enabled"] is False

    stale = auth_context.client.patch(
        "/api/v1/teacher/settings/site",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"brand_name": "Устаревшее изменение", "version": 0},
    )
    assert stale.status_code == 409

    published = auth_context.client.get("/api/v1/public/site").json()
    assert published["brand_name"] == "Математика с преподавателем"
    assert published["directions"] == ["Алгебра", "Геометрия"]
    assert published["trials_enabled"] is False
    assert "configured_trials_enabled" not in published
    with auth_context.sessions() as db:
        assert db.query(AuditLog).filter_by(action="SITE_SETTINGS_UPDATED").count() == 1


def test_student_cannot_read_or_change_teacher_site_settings(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    invitation = create_student(auth_context, teacher["csrf_token"], "site-student")
    activate(auth_context, invitation["activation_token"])
    student = login(auth_context, invitation["login"], STUDENT_PASSWORD)

    assert auth_context.client.get("/api/v1/teacher/settings/site").status_code == 403
    response = auth_context.client.patch(
        "/api/v1/teacher/settings/site",
        headers={"X-CSRF-Token": student["csrf_token"]},
        json={"brand_name": "Чужое название", "version": 0},
    )
    assert response.status_code == 403


def test_teacher_setting_closes_public_trial_intake(auth_context: AuthTestContext) -> None:
    enable_trial_feature()
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    response = auth_context.client.patch(
        "/api/v1/teacher/settings/site",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"trials_enabled": False, "version": 0},
    )
    assert response.status_code == 200
    auth_context.client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": teacher["csrf_token"]})
    trial = auth_context.client.post(
        "/api/v1/public/trial-requests",
        json={"name": "Иванов Иван", "grade": 8, "website": ""},
    )
    assert trial.status_code == 404
