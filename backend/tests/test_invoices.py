from datetime import datetime

from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_lessons import create_lesson


def set_profile(
    context: AuthTestContext,
    csrf: str,
    student_id: str,
    *,
    price: str = "1500.00",
    family: bool = False,
    version: int | None = None,
) -> dict[str, object]:
    response = context.client.patch(
        f"/api/v1/teacher/students/{student_id}/billing-profile",
        headers={"X-CSRF-Token": csrf},
        json={
            "billing_mode": "PER_LESSON",
            "price_per_lesson": price,
            "family_discount_enabled": family,
            "monthly_due_day": None,
            "version": version,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_completed_lesson_creates_one_immutable_discounted_invoice(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher["csrf_token"], "invoice-owner")
    activate(auth_context, student["activation_token"])
    billing = set_profile(auth_context, teacher["csrf_token"], student["student_id"], family=True)
    lesson = create_lesson(auth_context, teacher["csrf_token"], student["student_id"]).json()
    completed = auth_context.client.post(
        f"/api/v1/teacher/lessons/{lesson['id']}/complete",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
    )
    assert completed.status_code == 200
    assert (
        auth_context.client.post(
            f"/api/v1/teacher/lessons/{lesson['id']}/complete",
            headers={"X-CSRF-Token": teacher["csrf_token"]},
        ).status_code
        == 200
    )
    invoices = auth_context.client.get(
        f"/api/v1/teacher/invoices?student_id={student['student_id']}"
    ).json()
    assert invoices["total"] == 1
    invoice = invoices["items"][0]
    assert invoice["subtotal"] == "1500.00"
    assert invoice["discount_percent"] == "20.00"
    assert invoice["discount_amount"] == "300.00"
    assert invoice["total"] == "1200.00"
    assert invoice["outstanding"] == "1200.00"
    assert invoice["items"][0]["lesson_id"] == lesson["id"]
    completed_at = datetime.fromisoformat(completed.json()["completed_at"])
    due_at = datetime.fromisoformat(invoice["due_at"])
    assert (due_at - completed_at).total_seconds() == 48 * 60 * 60

    set_profile(
        auth_context,
        teacher["csrf_token"],
        student["student_id"],
        price="3000.00",
        version=int(billing["version"]),
    )
    unchanged = auth_context.client.get(
        f"/api/v1/teacher/invoices?student_id={student['student_id']}"
    ).json()["items"][0]
    assert unchanged["total"] == "1200.00"

    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    own = auth_context.client.get("/api/v1/student/invoices")
    assert own.status_code == 200
    assert own.json()["items"][0]["id"] == invoice["id"]
    summary = auth_context.client.get("/api/v1/student/billing").json()
    assert summary["accrued_total"] == "1200.00"
    assert summary["received_total"] == "0.00"
    assert summary["outstanding_total"] == "1200.00"
    assert (
        auth_context.client.get(
            f"/api/v1/teacher/invoices?student_id={student['student_id']}"
        ).status_code
        == 403
    )
    assert student_session["csrf_token"]


def test_invoice_visibility_is_scoped_and_unconfigured_billing_does_not_charge(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    first = create_student(auth_context, teacher["csrf_token"], "invoice-first")
    second = create_student(auth_context, teacher["csrf_token"], "invoice-second")
    activate(auth_context, first["activation_token"])
    activate(auth_context, second["activation_token"])
    set_profile(auth_context, teacher["csrf_token"], first["student_id"])
    first_lesson = create_lesson(
        auth_context,
        teacher["csrf_token"],
        first["student_id"],
        starts_at="2030-01-15T17:00:00+03:00",
        ends_at="2030-01-15T18:00:00+03:00",
    ).json()
    second_lesson = create_lesson(
        auth_context,
        teacher["csrf_token"],
        second["student_id"],
        starts_at="2030-01-16T17:00:00+03:00",
        ends_at="2030-01-16T18:00:00+03:00",
    ).json()
    for lesson in (first_lesson, second_lesson):
        assert (
            auth_context.client.post(
                f"/api/v1/teacher/lessons/{lesson['id']}/complete",
                headers={"X-CSRF-Token": teacher["csrf_token"]},
            ).status_code
            == 200
        )
    login(auth_context, second["login"], STUDENT_PASSWORD)
    assert auth_context.client.get("/api/v1/student/invoices").json()["items"] == []
    login(auth_context, first["login"], STUDENT_PASSWORD)
    assert auth_context.client.get("/api/v1/student/invoices").json()["total"] == 1
