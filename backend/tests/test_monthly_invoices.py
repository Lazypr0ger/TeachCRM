from datetime import datetime
from zoneinfo import ZoneInfo

from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_lessons import create_lesson


def set_monthly_profile(
    context: AuthTestContext,
    csrf: str,
    student_id: str,
    *,
    due_day: int = 31,
    family: bool = False,
) -> dict[str, object]:
    response = context.client.patch(
        f"/api/v1/teacher/students/{student_id}/billing-profile",
        headers={"X-CSRF-Token": csrf},
        json={
            "billing_mode": "MONTHLY",
            "price_per_lesson": "1000.00",
            "family_discount_enabled": family,
            "monthly_due_day": due_day,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_monthly_invoice_short_month_idempotency_snapshot_and_adjustment(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher["csrf_token"], "monthly-owner")
    activate(auth_context, student["activation_token"])
    set_monthly_profile(auth_context, teacher["csrf_token"], student["student_id"], family=True)
    for day in (10, 17):
        response = create_lesson(
            auth_context,
            teacher["csrf_token"],
            student["student_id"],
            starts_at=f"2030-02-{day:02d}T17:00:00+03:00",
            ends_at=f"2030-02-{day:02d}T18:00:00+03:00",
            title=f"Урок {day}",
        )
        assert response.status_code == 201
    payload = {"student_id": student["student_id"], "year": 2030, "month": 2}
    created = auth_context.client.post(
        "/api/v1/teacher/invoices/monthly",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json=payload,
    )
    assert created.status_code == 200, created.text
    invoice = created.json()
    assert invoice["period_start"] == "2030-02-01"
    assert invoice["period_end"] == "2030-02-28"
    assert invoice["subtotal"] == "2000.00"
    assert invoice["discount_percent"] == "20.00"
    assert invoice["total"] == "1600.00"
    due = datetime.fromisoformat(invoice["due_at"]).astimezone(ZoneInfo("Europe/Moscow"))
    assert (due.day, due.hour, due.minute) == (28, 23, 59)
    duplicate = auth_context.client.post(
        "/api/v1/teacher/invoices/monthly",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json=payload,
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == invoice["id"]

    adjusted = auth_context.client.post(
        f"/api/v1/teacher/invoices/{invoice['id']}/adjustments",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"amount": "100.00", "reason": "Дополнительное занятие"},
    )
    assert adjusted.status_code == 200, adjusted.text
    assert adjusted.json()["subtotal"] == "2100.00"
    assert adjusted.json()["discount_percent"] == "20.00"
    assert adjusted.json()["total"] == "1680.00"
    assert adjusted.json()["items"][-1]["kind"] == "ADJUSTMENT"

    profile = auth_context.client.get(
        f"/api/v1/teacher/students/{student['student_id']}/billing-profile"
    ).json()
    changed = auth_context.client.patch(
        f"/api/v1/teacher/students/{student['student_id']}/billing-profile",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={
            "billing_mode": "MONTHLY",
            "price_per_lesson": "5000.00",
            "family_discount_enabled": False,
            "monthly_due_day": 15,
            "version": profile["version"],
        },
    )
    assert changed.status_code == 200
    unchanged = auth_context.client.get(
        f"/api/v1/teacher/invoices?student_id={student['student_id']}"
    ).json()["items"][0]
    assert unchanged["total"] == "1680.00"


def test_monthly_invoice_validation_and_role_protection(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher["csrf_token"], "monthly-empty")
    activate(auth_context, student["activation_token"])
    set_monthly_profile(auth_context, teacher["csrf_token"], student["student_id"])
    payload = {"student_id": student["student_id"], "year": 2030, "month": 3}
    assert (
        auth_context.client.post(
            "/api/v1/teacher/invoices/monthly",
            headers={"X-CSRF-Token": teacher["csrf_token"]},
            json=payload,
        ).status_code
        == 422
    )
    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    assert (
        auth_context.client.post(
            "/api/v1/teacher/invoices/monthly",
            headers={"X-CSRF-Token": student_session["csrf_token"]},
            json=payload,
        ).status_code
        == 403
    )
