from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, login
from tests.test_payment_claims import claim, prepare_invoice


def test_payment_reversal_reopens_debt_and_is_idempotent(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student, invoice = prepare_invoice(auth_context, teacher, "payment-reversal")
    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    created_claim = claim(
        auth_context, student_session["csrf_token"], invoice["id"], "1200.00"
    ).json()
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    confirmed = auth_context.client.post(
        f"/api/v1/teacher/payment-claims/{created_claim['id']}/confirm",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={
            "confirmed_amount": "1200.00",
            "received_at": "2026-10-19T18:32:00+03:00",
            "idempotency_key": "reversal-original-confirm",
        },
    ).json()
    payload = {
        "reason": "Подтверждён ошибочный перевод",
        "reversed_at": "2026-10-20T12:00:00+03:00",
        "idempotency_key": "reversal-operation-001",
    }
    reversed_payment = auth_context.client.post(
        f"/api/v1/teacher/payments/{confirmed['id']}/reverse",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json=payload,
    )
    assert reversed_payment.status_code == 200, reversed_payment.text
    assert reversed_payment.json()["amount"] == "-1200.00"
    assert reversed_payment.json()["reversal_of_payment_id"] == confirmed["id"]
    assert reversed_payment.json()["reversal_reason"] == payload["reason"]
    retry = auth_context.client.post(
        f"/api/v1/teacher/payments/{confirmed['id']}/reverse",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json=payload,
    )
    assert retry.status_code == 200
    assert retry.json()["id"] == reversed_payment.json()["id"]
    assert (
        auth_context.client.post(
            f"/api/v1/teacher/payments/{confirmed['id']}/reverse",
            headers={"X-CSRF-Token": teacher["csrf_token"]},
            json={**payload, "idempotency_key": "reversal-operation-002"},
        ).status_code
        == 409
    )
    reopened = auth_context.client.get(
        f"/api/v1/teacher/invoices?student_id={student['student_id']}"
    ).json()["items"][0]
    assert reopened["outstanding"] == "1200.00"
    assert reopened["status"] == "UNPAID"
    assert len(auth_context.client.get("/api/v1/teacher/payments").json()) == 2
    teacher_summary = auth_context.client.get("/api/v1/teacher/finances/summary").json()
    assert teacher_summary["received_total"] == "0.00"
    assert teacher_summary["outstanding_total"] == "1200.00"

    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    summary = auth_context.client.get("/api/v1/student/billing").json()
    assert summary["received_total"] == "0.00"
    assert (
        auth_context.client.post(
            f"/api/v1/teacher/payments/{confirmed['id']}/reverse",
            headers={"X-CSRF-Token": student_session["csrf_token"]},
            json={**payload, "idempotency_key": "student-cannot-reverse"},
        ).status_code
        == 403
    )
