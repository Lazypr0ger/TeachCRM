from datetime import timedelta

from app.modules.auth.service import utc_now
from app.modules.billing.models import Invoice
from app.modules.notifications.models import Notification, OutboxEvent
from app.modules.notifications.service import enqueue_payment_due_notifications, process_outbox
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_invoices import set_profile
from tests.test_lessons import create_lesson


def test_transactional_outbox_delivery_is_idempotent_and_scoped(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher["csrf_token"], "notification-owner")
    activate(auth_context, student["activation_token"])
    lesson = create_lesson(auth_context, teacher["csrf_token"], student["student_id"]).json()
    with auth_context.sessions() as db:
        assert db.query(OutboxEvent).count() == 1
        assert db.query(Notification).count() == 0
        assert process_outbox(db) == 1
        assert process_outbox(db) == 0
        assert db.query(Notification).count() == 1

    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    items = auth_context.client.get("/api/v1/notifications?is_read=false")
    assert items.status_code == 200
    assert items.json()["total"] == 1
    notification = items.json()["items"][0]
    assert notification["type"] == "LESSON_CREATED"
    assert notification["target_id"] == lesson["id"]
    assert notification["read_at"] is None

    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    assert auth_context.client.get("/api/v1/notifications").json()["items"] == []
    assert (
        auth_context.client.post(
            f"/api/v1/notifications/{notification['id']}/read",
            headers={"X-CSRF-Token": teacher["csrf_token"]},
        ).status_code
        == 404
    )
    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    marked = auth_context.client.post(
        f"/api/v1/notifications/{notification['id']}/read",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
    )
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None
    assert (
        auth_context.client.post(
            "/api/v1/notifications/read-all",
            headers={"X-CSRF-Token": student_session["csrf_token"]},
        ).json()["updated"]
        == 0
    )


def test_overdue_notification_is_enqueued_once(auth_context: AuthTestContext) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher["csrf_token"], "payment-due-owner")
    activate(auth_context, student["activation_token"])
    set_profile(auth_context, teacher["csrf_token"], student["student_id"])
    lesson = create_lesson(auth_context, teacher["csrf_token"], student["student_id"]).json()
    assert (
        auth_context.client.post(
            f"/api/v1/teacher/lessons/{lesson['id']}/complete",
            headers={"X-CSRF-Token": teacher["csrf_token"]},
        ).status_code
        == 200
    )
    with auth_context.sessions() as db:
        invoice = db.query(Invoice).one()
        invoice.due_at = utc_now() - timedelta(minutes=1)
        db.commit()
        assert enqueue_payment_due_notifications(db) == 1
        assert enqueue_payment_due_notifications(db) == 0
        process_outbox(db)

    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    response = auth_context.client.get("/api/v1/notifications?type=PAYMENT_DUE")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["target_type"] == "INVOICE"
    assert student_session["csrf_token"]
