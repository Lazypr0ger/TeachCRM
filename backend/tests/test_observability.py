from app.modules.auth.models import AuditLog
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import login


def test_request_id_is_returned_validated_and_written_to_audit(
    auth_context: AuthTestContext,
) -> None:
    generated = auth_context.client.get("/health/live")
    assert len(generated.headers["X-Request-ID"]) == 32

    supplied = "release-check-123"
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    updated = auth_context.client.patch(
        "/api/v1/teacher/settings/site",
        headers={"X-CSRF-Token": teacher["csrf_token"], "X-Request-ID": supplied},
        json={"brand_name": "Наблюдаемая CRM", "version": 0},
    )
    assert updated.status_code == 200
    assert updated.headers["X-Request-ID"] == supplied
    with auth_context.sessions() as db:
        audit = db.query(AuditLog).filter_by(action="SITE_SETTINGS_UPDATED").one()
        assert audit.request_id == supplied

    rejected = auth_context.client.get("/health/live", headers={"X-Request-ID": "bad id"})
    assert rejected.headers["X-Request-ID"] != "bad id"


def test_diagnostics_are_teacher_only(auth_context: AuthTestContext) -> None:
    assert auth_context.client.get("/api/v1/teacher/system/diagnostics").status_code == 401
    login(auth_context, "teacher", TEACHER_PASSWORD)
    response = auth_context.client.get("/api/v1/teacher/system/diagnostics")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "pending_outbox": 0,
        "retrying_outbox": 0,
        "due_outbox": 0,
        "oldest_pending_at": None,
        "active_sessions": 1,
    }
