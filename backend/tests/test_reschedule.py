from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_lessons import create_lesson


def request_payload(
    starts_at: str = "2030-01-16T17:00:00+03:00",
    ends_at: str = "2030-01-16T18:00:00+03:00",
) -> dict[str, str]:
    return {
        "proposed_starts_at": starts_at,
        "proposed_ends_at": ends_at,
        "reason": "Не успеваю к прежнему времени",
    }


def test_student_request_teacher_counter_student_accepts_atomically(
    auth_context: AuthTestContext,
) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    first = create_student(auth_context, teacher_session["csrf_token"], "move-owner")
    second = create_student(auth_context, teacher_session["csrf_token"], "move-other")
    activate(auth_context, first["activation_token"])
    activate(auth_context, second["activation_token"])
    lesson = create_lesson(auth_context, teacher_session["csrf_token"], first["student_id"]).json()

    first_session = login(auth_context, first["login"], STUDENT_PASSWORD)
    created = auth_context.client.post(
        f"/api/v1/student/lessons/{lesson['id']}/reschedule-requests",
        headers={"X-CSRF-Token": first_session["csrf_token"]},
        json=request_payload(),
    )
    assert created.status_code == 201
    assert created.json()["status"] == "PENDING"
    request_id = created.json()["id"]
    assert (
        auth_context.client.post(
            f"/api/v1/student/lessons/{lesson['id']}/reschedule-requests",
            headers={"X-CSRF-Token": first_session["csrf_token"]},
            json=request_payload(),
        ).status_code
        == 409
    )

    second_session = login(auth_context, second["login"], STUDENT_PASSWORD)
    assert auth_context.client.get("/api/v1/student/reschedule-requests").json() == []
    assert (
        auth_context.client.post(
            f"/api/v1/student/reschedule-requests/{request_id}/accept-counter",
            headers={"X-CSRF-Token": second_session["csrf_token"]},
        ).status_code
        == 404
    )

    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    teacher_list = auth_context.client.get(
        "/api/v1/teacher/reschedule-requests?request_status=PENDING"
    )
    assert teacher_list.status_code == 200
    assert [item["id"] for item in teacher_list.json()] == [request_id]
    countered = auth_context.client.post(
        f"/api/v1/teacher/reschedule-requests/{request_id}/counter",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        json={
            "counter_starts_at": "2030-01-17T19:00:00+03:00",
            "counter_ends_at": "2030-01-17T20:00:00+03:00",
            "response_note": "Могу предложить вечер четверга",
        },
    )
    assert countered.status_code == 200
    assert countered.json()["status"] == "COUNTER_OFFER"
    assert (
        auth_context.client.get(f"/api/v1/teacher/lessons/{lesson['id']}").json()["starts_at"]
        == lesson["starts_at"]
    )

    first_session = login(auth_context, first["login"], STUDENT_PASSWORD)
    accepted = auth_context.client.post(
        f"/api/v1/student/reschedule-requests/{request_id}/accept-counter",
        headers={"X-CSRF-Token": first_session["csrf_token"]},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"
    moved = auth_context.client.get(f"/api/v1/student/lessons/{lesson['id']}").json()
    assert moved["starts_at"].startswith("2030-01-17T16:00:00")
    assert moved["version"] == lesson["version"] + 1


def test_teacher_accept_conflict_rolls_back_request_and_lesson(
    auth_context: AuthTestContext,
) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    first = create_student(auth_context, teacher_session["csrf_token"], "move-conflict-one")
    second = create_student(auth_context, teacher_session["csrf_token"], "move-conflict-two")
    activate(auth_context, first["activation_token"])
    lesson = create_lesson(auth_context, teacher_session["csrf_token"], first["student_id"]).json()
    assert (
        create_lesson(
            auth_context,
            teacher_session["csrf_token"],
            second["student_id"],
            starts_at="2030-01-16T17:00:00+03:00",
            ends_at="2030-01-16T18:00:00+03:00",
        ).status_code
        == 201
    )

    student_session = login(auth_context, first["login"], STUDENT_PASSWORD)
    request = auth_context.client.post(
        f"/api/v1/student/lessons/{lesson['id']}/reschedule-requests",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json=request_payload(),
    ).json()
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    accepted = auth_context.client.post(
        f"/api/v1/teacher/reschedule-requests/{request['id']}/accept",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
    )
    assert accepted.status_code == 409
    stored_request = auth_context.client.get("/api/v1/teacher/reschedule-requests").json()[0]
    assert stored_request["status"] == "PENDING"
    stored_lesson = auth_context.client.get(f"/api/v1/teacher/lessons/{lesson['id']}").json()
    assert stored_lesson["starts_at"] == lesson["starts_at"]
    assert stored_lesson["version"] == lesson["version"]


def test_reschedule_reject_cancel_csrf_and_roles(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher_session["csrf_token"], "move-decisions")
    activate(auth_context, student["activation_token"])
    lesson = create_lesson(
        auth_context, teacher_session["csrf_token"], student["student_id"]
    ).json()
    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    endpoint = f"/api/v1/student/lessons/{lesson['id']}/reschedule-requests"
    assert auth_context.client.post(endpoint, json=request_payload()).status_code == 403
    created = auth_context.client.post(
        endpoint,
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json=request_payload(),
    ).json()
    assert (
        auth_context.client.post(
            f"/api/v1/teacher/reschedule-requests/{created['id']}/accept",
            headers={"X-CSRF-Token": student_session["csrf_token"]},
        ).status_code
        == 403
    )

    cancelled = auth_context.client.post(
        f"/api/v1/student/reschedule-requests/{created['id']}/cancel",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    second = auth_context.client.post(
        endpoint,
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json=request_payload("2030-01-18T17:00:00+03:00", "2030-01-18T18:00:00+03:00"),
    ).json()
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    rejected = auth_context.client.post(
        f"/api/v1/teacher/reschedule-requests/{second['id']}/reject",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        json={"response_note": "В этот день занятий не будет"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["response_note"] == "В этот день занятий не будет"
