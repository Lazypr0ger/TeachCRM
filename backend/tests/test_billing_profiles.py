from decimal import Decimal

from app.modules.billing.service import discounted_amount, effective_discount, money_round
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login


def test_discount_uses_maximum_and_decimal_rounding() -> None:
    assert effective_discount("PER_LESSON", False) == Decimal("0")
    assert effective_discount("MONTHLY", False) == Decimal("0.10")
    assert effective_discount("PER_LESSON", True) == Decimal("0.20")
    assert effective_discount("MONTHLY", True) == Decimal("0.20")
    assert discounted_amount(Decimal("10000"), Decimal("0.20")) == Decimal("8000.00")
    assert money_round(Decimal("1.005")) == Decimal("1.01")


def test_teacher_creates_and_updates_billing_profile_with_version(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher["csrf_token"], "billing-profile")
    activate(auth_context, student["activation_token"])
    endpoint = f"/api/v1/teacher/students/{student['student_id']}/billing-profile"
    assert auth_context.client.get(endpoint).status_code == 404

    created = auth_context.client.patch(
        endpoint,
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={
            "billing_mode": "MONTHLY",
            "price_per_lesson": "10000.00",
            "family_discount_enabled": True,
            "monthly_due_day": 31,
        },
    )
    assert created.status_code == 200, created.text
    profile = created.json()
    assert profile["currency"] == "RUB"
    assert profile["effective_discount_percent"] == "20.00"
    assert profile["effective_price_per_lesson"] == "8000.00"
    assert profile["monthly_settlement_rule"] == "PREPAY_SCHEDULED"

    stale = auth_context.client.patch(
        endpoint,
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={
            "billing_mode": "PER_LESSON",
            "price_per_lesson": "1500.00",
            "monthly_due_day": None,
            "version": profile["version"] + 1,
        },
    )
    assert stale.status_code == 409
    updated = auth_context.client.patch(
        endpoint,
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={
            "billing_mode": "PER_LESSON",
            "price_per_lesson": "1500.00",
            "family_discount_enabled": True,
            "monthly_due_day": None,
            "version": profile["version"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["effective_price_per_lesson"] == "1200.00"
    assert updated.json()["version"] == 2

    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    forbidden = auth_context.client.patch(
        endpoint,
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json={
            "billing_mode": "PER_LESSON",
            "price_per_lesson": "0.00",
            "monthly_due_day": None,
            "version": 2,
        },
    )
    assert forbidden.status_code == 403


def test_billing_profile_validates_mode_due_day_and_student(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher["csrf_token"], "billing-validation")
    endpoint = f"/api/v1/teacher/students/{student['student_id']}/billing-profile"
    invalid = auth_context.client.patch(
        endpoint,
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"billing_mode": "MONTHLY", "price_per_lesson": "1000.00"},
    )
    assert invalid.status_code == 422
    assert (
        auth_context.client.patch(
            "/api/v1/teacher/students/00000000-0000-0000-0000-000000000001/billing-profile",
            headers={"X-CSRF-Token": teacher["csrf_token"]},
            json={
                "billing_mode": "PER_LESSON",
                "price_per_lesson": "1000.00",
                "monthly_due_day": None,
            },
        ).status_code
        == 404
    )
