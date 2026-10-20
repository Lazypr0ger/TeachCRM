from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_homework import create_assignment
from tests.test_lessons import create_lesson
from tests.test_payment_claims import claim, prepare_invoice
from tests.test_reschedule import request_payload


def test_teacher_dashboard_counts_real_pending_work(auth_context: AuthTestContext) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)

    payer, invoice = prepare_invoice(auth_context, teacher, "dashboard-payment")
    payer_session = login(auth_context, payer["login"], STUDENT_PASSWORD)
    payment_claim = claim(
        auth_context, payer_session["csrf_token"], invoice["id"], "1200.00"
    )
    assert payment_claim.status_code == 201

    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    homework_student = create_student(
        auth_context, teacher["csrf_token"], "dashboard-homework"
    )
    activate(auth_context, homework_student["activation_token"])
    homework_lesson = create_lesson(
        auth_context,
        teacher["csrf_token"],
        homework_student["student_id"],
        starts_at="2031-02-10T17:00:00+03:00",
        ends_at="2031-02-10T18:00:00+03:00",
    ).json()
    assignment = create_assignment(
        auth_context, teacher["csrf_token"], homework_lesson["id"]
    )["assignment"]
    homework_session = login(auth_context, homework_student["login"], STUDENT_PASSWORD)
    submitted = auth_context.client.post(
        f"/api/v1/student/assignments/{assignment['id']}/submission",
        headers={"X-CSRF-Token": homework_session["csrf_token"]},
        json={
            "answer_text": "Готово",
            "file_ids": [],
            "idempotency_key": "dashboard-homework-submit",
        },
    )
    assert submitted.status_code == 201

    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    moving_student = create_student(auth_context, teacher["csrf_token"], "dashboard-move")
    activate(auth_context, moving_student["activation_token"])
    moving_lesson = create_lesson(
        auth_context,
        teacher["csrf_token"],
        moving_student["student_id"],
        starts_at="2032-03-10T17:00:00+03:00",
        ends_at="2032-03-10T18:00:00+03:00",
    ).json()
    moving_session = login(auth_context, moving_student["login"], STUDENT_PASSWORD)
    requested = auth_context.client.post(
        f"/api/v1/student/lessons/{moving_lesson['id']}/reschedule-requests",
        headers={"X-CSRF-Token": moving_session["csrf_token"]},
        json=request_payload(
            starts_at="2032-03-11T17:00:00+03:00",
            ends_at="2032-03-11T18:00:00+03:00",
        ),
    )
    assert requested.status_code == 201

    login(auth_context, "teacher", TEACHER_PASSWORD)
    dashboard = auth_context.client.get("/api/v1/teacher/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["pending_payment_claims"] == 1
    assert dashboard.json()["homework_submissions_today"] == 1
    assert dashboard.json()["pending_reschedule_requests"] == 1
