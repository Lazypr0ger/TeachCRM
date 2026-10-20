from uuid import UUID

from app.modules.auth.models import AuditLog
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_lessons import create_lesson
from tests.test_payment_claims import prepare_invoice


def test_teacher_lists_searches_and_filters_students(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    first = create_student(auth_context, teacher_session["csrf_token"], "list-one")
    second = auth_context.client.post(
        "/api/v1/teacher/students",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        json={
            "first_name": "Анна",
            "last_name": "Петрова",
            "grade": 9,
            "login": "student-list-two",
        },
    )
    assert second.status_code == 201

    listed = auth_context.client.get(
        "/api/v1/teacher/students?page_size=1&sort=created_desc"
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert len(listed.json()["items"]) == 1

    searched = auth_context.client.get("/api/v1/teacher/students?search=Петрова&grade=9")
    assert searched.status_code == 200
    assert [item["login"] for item in searched.json()["items"]] == ["student-list-two"]

    invited = auth_context.client.get("/api/v1/teacher/students?student_status=INVITED")
    assert {item["id"] for item in invited.json()["items"]} == {
        first["student_id"],
        second.json()["student_id"],
    }


def test_student_list_includes_next_lesson_debt_and_status_totals(
    auth_context: AuthTestContext,
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student, _invoice = prepare_invoice(auth_context, teacher, "list-operational")
    upcoming = create_lesson(
        auth_context,
        teacher["csrf_token"],
        student["student_id"],
        starts_at="2045-04-10T17:00:00+03:00",
        ends_at="2045-04-10T18:00:00+03:00",
    )
    assert upcoming.status_code == 201

    listed = auth_context.client.get(
        "/api/v1/teacher/students?search=student-list-operational&has_debt=true"
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["next_lesson_at"] == upcoming.json()["starts_at"]
    assert listed.json()["items"][0]["outstanding_total"] == "1200.00"
    assert listed.json()["status_counts"] == {
        "ACTIVE": 1,
        "INVITED": 0,
        "SUSPENDED": 0,
        "TOTAL": 1,
    }
    assert auth_context.client.get(
        "/api/v1/teacher/students?search=student-list-operational&has_debt=false"
    ).json()["total"] == 0


def test_teacher_reads_and_updates_student_card(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    invitation = create_student(auth_context, teacher_session["csrf_token"], "edit")
    student_id = invitation["student_id"]

    updated = auth_context.client.patch(
        f"/api/v1/teacher/students/{student_id}",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        json={"first_name": "  Иван ", "patronymic": "", "grade": 8},
    )
    assert updated.status_code == 200
    assert updated.json()["first_name"] == "Иван"
    assert updated.json()["patronymic"] is None
    assert updated.json()["grade"] == 8

    card = auth_context.client.get(f"/api/v1/teacher/students/{student_id}")
    assert card.status_code == 200
    assert card.json()["login"] == invitation["login"]

    with auth_context.sessions() as db:
        audit = db.query(AuditLog).filter_by(
            action="STUDENT_UPDATED", entity_id=UUID(student_id)
        ).one()
        assert audit.actor_user_id == auth_context.teacher.id


def test_student_cannot_read_or_edit_student_management(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    invitation = create_student(auth_context, teacher_session["csrf_token"], "forbidden-card")
    activate(auth_context, invitation["activation_token"])
    student_session = login(auth_context, invitation["login"], STUDENT_PASSWORD)

    assert auth_context.client.get("/api/v1/teacher/students").status_code == 403
    response = auth_context.client.patch(
        f"/api/v1/teacher/students/{invitation['student_id']}",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json={"grade": 11},
    )
    assert response.status_code == 403


def test_student_card_validation_and_not_found(auth_context: AuthTestContext) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    invitation = create_student(auth_context, teacher_session["csrf_token"], "validation")
    student_url = f"/api/v1/teacher/students/{invitation['student_id']}"

    assert auth_context.client.patch(
        student_url,
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        json={},
    ).status_code == 422
    assert auth_context.client.patch(
        student_url,
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        json={"last_name": "   "},
    ).status_code == 422
    assert auth_context.client.get(
        "/api/v1/teacher/students/00000000-0000-0000-0000-000000000000"
    ).status_code == 404
