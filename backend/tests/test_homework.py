from collections.abc import Iterator

import pytest

from app.main import app
from app.modules.files.storage import get_storage
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_lessons import create_lesson
from tests.test_private_files import MemoryStorage


@pytest.fixture
def homework_storage() -> Iterator[MemoryStorage]:
    storage = MemoryStorage()
    app.dependency_overrides[get_storage] = lambda: storage
    yield storage
    app.dependency_overrides.pop(get_storage, None)


def create_assignment(
    context: AuthTestContext, csrf: str, lesson_id: str, description: str = "Решить № 1–5"
) -> dict[str, object]:
    response = context.client.post(
        f"/api/v1/teacher/lessons/{lesson_id}/assignment",
        headers={"X-CSRF-Token": csrf},
        json={"description": description, "due_at": "2026-11-02T18:00:00+03:00"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def upload_file(
    context: AuthTestContext,
    csrf: str,
    *,
    purpose: str,
    assignment_id: str,
    filename: str = "answer.pdf",
) -> dict[str, object]:
    content = b"%PDF-1.7\nprivate-homework"
    initialized = context.client.post(
        "/api/v1/files/upload-init",
        headers={"X-CSRF-Token": csrf},
        json={
            "purpose": purpose,
            "target_type": "ASSIGNMENT",
            "target_id": assignment_id,
            "original_filename": filename,
            "byte_size": len(content),
        },
    )
    assert initialized.status_code == 201, initialized.text
    ticket = initialized.json()
    uploaded = context.client.post(
        ticket["upload_url"],
        headers={"X-CSRF-Token": csrf},
        files={"file": (filename, content, "application/pdf")},
    )
    assert uploaded.status_code == 204, uploaded.text
    completed = context.client.post(
        f"/api/v1/files/upload-complete/{ticket['ticket_id']}",
        headers={"X-CSRF-Token": csrf},
    )
    assert completed.status_code == 200, completed.text
    return completed.json()


def test_assignment_states_update_files_and_role_boundaries(
    auth_context: AuthTestContext, homework_storage: MemoryStorage
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    first = create_student(auth_context, teacher["csrf_token"], "homework-owner")
    second = create_student(auth_context, teacher["csrf_token"], "homework-other")
    activate(auth_context, first["activation_token"])
    activate(auth_context, second["activation_token"])
    lesson = create_lesson(auth_context, teacher["csrf_token"], first["student_id"]).json()

    empty = auth_context.client.get(f"/api/v1/teacher/lessons/{lesson['id']}/homework")
    assert empty.status_code == 200
    assert empty.json() == {
        "state": "NO_HOMEWORK",
        "assignment": None,
        "submission": None,
        "draft_files": [],
    }

    created = create_assignment(auth_context, teacher["csrf_token"], lesson["id"])
    assignment = created["assignment"]
    assert isinstance(assignment, dict)
    assert created["state"] == "NEEDS_RESPONSE"
    assert (
        auth_context.client.post(
            f"/api/v1/teacher/lessons/{lesson['id']}/assignment",
            headers={"X-CSRF-Token": teacher["csrf_token"]},
            json={"description": "Повтор"},
        ).status_code
        == 409
    )
    updated = auth_context.client.patch(
        f"/api/v1/teacher/assignments/{assignment['id']}",
        headers={"X-CSRF-Token": teacher["csrf_token"]},
        json={"version": assignment["version"], "description": "Решить № 1–10"},
    )
    assert updated.status_code == 200
    assert updated.json()["assignment"]["description"] == "Решить № 1–10"
    assert (
        auth_context.client.patch(
            f"/api/v1/teacher/assignments/{assignment['id']}",
            headers={"X-CSRF-Token": teacher["csrf_token"]},
            json={"version": assignment["version"], "description": "Устаревшее"},
        ).status_code
        == 409
    )
    material = upload_file(
        auth_context,
        teacher["csrf_token"],
        purpose="ASSIGNMENT_MATERIAL",
        assignment_id=assignment["id"],
        filename="task.pdf",
    )

    first_session = login(auth_context, first["login"], STUDENT_PASSWORD)
    own = auth_context.client.get(f"/api/v1/student/lessons/{lesson['id']}/homework")
    assert own.status_code == 200
    assert own.json()["assignment"]["files"][0]["id"] == material["id"]
    assert auth_context.client.get(material["download_url"]).status_code == 200
    assert (
        auth_context.client.post(
            f"/api/v1/teacher/lessons/{lesson['id']}/assignment",
            headers={"X-CSRF-Token": first_session["csrf_token"]},
            json={"description": "Нельзя"},
        ).status_code
        == 403
    )
    login(auth_context, second["login"], STUDENT_PASSWORD)
    assert (
        auth_context.client.get(f"/api/v1/student/lessons/{lesson['id']}/homework").status_code
        == 404
    )


def test_final_submission_is_atomic_idempotent_and_immutable(
    auth_context: AuthTestContext, homework_storage: MemoryStorage
) -> None:
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher["csrf_token"], "homework-submit")
    activate(auth_context, student["activation_token"])
    first_lesson = create_lesson(
        auth_context,
        teacher["csrf_token"],
        student["student_id"],
        starts_at="2026-11-01T10:00:00+03:00",
        ends_at="2026-11-01T11:00:00+03:00",
    ).json()
    second_lesson = create_lesson(
        auth_context,
        teacher["csrf_token"],
        student["student_id"],
        starts_at="2026-11-02T10:00:00+03:00",
        ends_at="2026-11-02T11:00:00+03:00",
    ).json()
    first = create_assignment(auth_context, teacher["csrf_token"], first_lesson["id"])["assignment"]
    second = create_assignment(auth_context, teacher["csrf_token"], second_lesson["id"])[
        "assignment"
    ]
    assert isinstance(first, dict) and isinstance(second, dict)

    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    draft = upload_file(
        auth_context,
        student_session["csrf_token"],
        purpose="HOMEWORK",
        assignment_id=first["id"],
    )
    login(auth_context, "teacher", TEACHER_PASSWORD)
    assert auth_context.client.get(draft["download_url"]).status_code == 404
    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    empty = auth_context.client.post(
        f"/api/v1/student/assignments/{first['id']}/submission",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json={"answer_text": "  ", "file_ids": [], "idempotency_key": "empty-request"},
    )
    assert empty.status_code == 422
    wrong_target = auth_context.client.post(
        f"/api/v1/student/assignments/{second['id']}/submission",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json={"file_ids": [draft["id"]], "idempotency_key": "wrong-target-request"},
    )
    assert wrong_target.status_code == 422
    assert (
        auth_context.client.get(f"/api/v1/student/lessons/{second_lesson['id']}/homework").json()[
            "state"
        ]
        == "NEEDS_RESPONSE"
    )

    payload = {
        "answer_text": "Готово",
        "file_ids": [draft["id"]],
        "idempotency_key": "submission-request-001",
    }
    submitted = auth_context.client.post(
        f"/api/v1/student/assignments/{first['id']}/submission",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json=payload,
    )
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["files"][0]["id"] == draft["id"]
    retry = auth_context.client.post(
        f"/api/v1/student/assignments/{first['id']}/submission",
        headers={"X-CSRF-Token": student_session["csrf_token"]},
        json=payload,
    )
    assert retry.status_code == 201
    assert retry.json()["id"] == submitted.json()["id"]
    assert (
        auth_context.client.post(
            f"/api/v1/student/assignments/{first['id']}/submission",
            headers={"X-CSRF-Token": student_session["csrf_token"]},
            json={"answer_text": "Ещё раз", "idempotency_key": "submission-request-002"},
        ).status_code
        == 409
    )
    assert (
        auth_context.client.delete(
            f"/api/v1/files/{draft['id']}",
            headers={"X-CSRF-Token": student_session["csrf_token"]},
        ).status_code
        == 403
    )
    teacher = login(auth_context, "teacher", TEACHER_PASSWORD)
    result = auth_context.client.get(f"/api/v1/teacher/lessons/{first_lesson['id']}/homework")
    assert result.status_code == 200
    assert result.json()["state"] == "ACCEPTED"
    assert result.json()["submission"]["answer_text"] == "Готово"
