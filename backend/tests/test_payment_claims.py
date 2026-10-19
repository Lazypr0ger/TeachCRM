from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_invoices import set_profile
from tests.test_lessons import create_lesson


def prepare_invoice(
    context: AuthTestContext, teacher: dict[str, str], suffix: str
) -> tuple[dict, dict]:
    student = create_student(context, teacher["csrf_token"], suffix)
    activate(context, student["activation_token"])
    set_profile(context, teacher["csrf_token"], student["student_id"], price="1200.00")
    lesson = create_lesson(context, teacher["csrf_token"], student["student_id"]).json()
    assert (
        context.client.post(
            f"/api/v1/teacher/lessons/{lesson['id']}/complete",
            headers={"X-CSRF-Token": teacher["csrf_token"]},
        ).status_code
        == 200
    )
    invoice = context.client.get(
        f"/api/v1/teacher/invoices?student_id={student['student_id']}"
    ).json()["items"][0]
    return student, invoice


def claim(context: AuthTestContext, csrf: str, invoice_id: str, amount: str) -> object:
    return context.client.post(
        f"/api/v1/student/invoices/{invoice_id}/payment-claims",
        headers={"X-CSRF-Token": csrf},
        json={
            "declared_amount": amount,
            "paid_at": "2026-10-19T18:30:00+03:00",
            "comment": "Перевёл по реквизитам",
        },
    )


def test_reject_retry_partial_and_full_confirmation_are_consistent(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student, invoice = prepare_invoice(auth_context, teacher, "claim-flow")
    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    first = claim(auth_context, student_session["csrf_token"], invoice["id"], "600.00")
    assert first.status_code == 201
    assert (
        claim(auth_context, student_session["csrf_token"], invoice["id"], "600.00").status_code
        == 409
    )

    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    rejected = auth_context.client.post(
        f"/api/v1/teacher/payment-claims/{first.json()['id']}/reject",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"reason": "Не найден перевод"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"

    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    second = claim(auth_context, student_session["csrf_token"], invoice["id"], "600.00")
    assert second.status_code == 201
    claim_history = auth_context.client.get("/api/v1/student/payment-claims").json()
    rejected_history = next(item for item in claim_history if item["status"] == "REJECTED")
    assert rejected_history["rejection_reason"] == "Не найден перевод"
    assert (
        auth_context.client.post(
            f"/api/v1/teacher/payment-claims/{second.json()['id']}/confirm",
            headers={"X-CSRF-Token": student_session["csrf_token"]},
            json={
                "confirmed_amount": "600.00",
                "received_at": "2026-10-19T18:32:00+03:00",
                "idempotency_key": "confirm-partial-001",
            },
        ).status_code
        == 403
    )

    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    confirm_payload = {
        "confirmed_amount": "600.00",
        "received_at": "2026-10-19T18:32:00+03:00",
        "idempotency_key": "confirm-partial-001",
    }
    confirmed = auth_context.client.post(
        f"/api/v1/teacher/payment-claims/{second.json()['id']}/confirm",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json=confirm_payload,
    )
    assert confirmed.status_code == 200, confirmed.text
    retry = auth_context.client.post(
        f"/api/v1/teacher/payment-claims/{second.json()['id']}/confirm",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json=confirm_payload,
    )
    assert retry.status_code == 200
    assert retry.json()["id"] == confirmed.json()["id"]
    partial = auth_context.client.get(
        f"/api/v1/teacher/invoices?student_id={student['student_id']}"
    ).json()["items"][0]
    assert partial["status"] == "PARTIALLY_PAID"
    assert partial["outstanding"] == "600.00"
    assert partial["can_submit_claim"] is True

    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    third = claim(auth_context, student_session["csrf_token"], invoice["id"], "600.00")
    assert third.status_code == 201
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    final = auth_context.client.post(
        f"/api/v1/teacher/payment-claims/{third.json()['id']}/confirm",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={
            "confirmed_amount": "600.00",
            "received_at": "2026-10-20T10:00:00+03:00",
            "idempotency_key": "confirm-final-002",
        },
    )
    assert final.status_code == 200
    paid = auth_context.client.get(
        f"/api/v1/teacher/invoices?student_id={student['student_id']}"
    ).json()["items"][0]
    assert paid["status"] == "PAID"
    assert paid["outstanding"] == "0.00"
    assert paid["can_submit_claim"] is False


def test_claim_ownership_amount_and_pending_visibility(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    owner, invoice = prepare_invoice(auth_context, teacher, "claim-owner")
    other = create_student(auth_context, teacher["csrf_token"], "claim-other")
    activate(auth_context, other["activation_token"])
    other_session = login(auth_context, other["login"], STUDENT_PASSWORD)
    assert (
        claim(auth_context, other_session["csrf_token"], invoice["id"], "100.00").status_code == 404
    )
    owner_session = login(auth_context, owner["login"], STUDENT_PASSWORD)
    assert (
        claim(auth_context, owner_session["csrf_token"], invoice["id"], "1200.01").status_code
        == 422
    )
    pending = claim(auth_context, owner_session["csrf_token"], invoice["id"], "1200.00")
    assert pending.status_code == 201
    invoice_state = auth_context.client.get("/api/v1/student/invoices").json()["items"][0]
    assert invoice_state["pending_claim_id"] == pending.json()["id"]
    assert invoice_state["can_submit_claim"] is False
