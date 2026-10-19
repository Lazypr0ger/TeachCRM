from collections.abc import Iterator
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.main import app
from app.modules.auth.models import User
from app.modules.auth.service import utc_now
from app.modules.files.models import FileUploadTicket, UploadStatus
from app.modules.files.service import cleanup_expired_uploads
from app.modules.files.storage import ObjectStorage, get_storage
from tests.conftest import TEACHER_PASSWORD, AuthTestContext
from tests.test_auth_security import STUDENT_PASSWORD, activate, create_student, login
from tests.test_lessons import create_lesson


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, content: bytes, content_type: str) -> None:
        self.objects[key] = content

    def copy(self, source_key: str, destination_key: str, content_type: str) -> None:
        self.objects[destination_key] = self.objects[source_key]

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@pytest.fixture
def memory_storage() -> Iterator[MemoryStorage]:
    storage = MemoryStorage()
    app.dependency_overrides[get_storage] = lambda: storage
    yield storage
    app.dependency_overrides.pop(get_storage, None)


def initialize_file(
    context: AuthTestContext,
    csrf: str,
    lesson_id: str,
    filename: str,
    content: bytes,
) -> dict[str, object]:
    response = context.client.post(
        "/api/v1/files/upload-init",
        headers={"X-CSRF-Token": csrf},
        json={
            "purpose": "LESSON_MATERIAL",
            "target_type": "LESSON",
            "target_id": lesson_id,
            "original_filename": filename,
            "byte_size": len(content),
        },
    )
    assert response.status_code == 201
    return response.json()


def test_private_lesson_file_upload_download_and_delete(
    auth_context: AuthTestContext, memory_storage: ObjectStorage
) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    first = create_student(auth_context, teacher_session["csrf_token"], "file-owner")
    second = create_student(auth_context, teacher_session["csrf_token"], "file-other")
    activate(auth_context, first["activation_token"])
    activate(auth_context, second["activation_token"])
    lesson = create_lesson(auth_context, teacher_session["csrf_token"], first["student_id"]).json()
    content = b"\x89PNG\r\n\x1a\nprivate-image"
    ticket = initialize_file(
        auth_context,
        teacher_session["csrf_token"],
        lesson["id"],
        "lesson.png",
        content,
    )
    uploaded = auth_context.client.post(
        str(ticket["upload_url"]),
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        files={"file": ("lesson.png", content, "image/png")},
    )
    assert uploaded.status_code == 204
    completed = auth_context.client.post(
        f"/api/v1/files/upload-complete/{ticket['ticket_id']}",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
    )
    assert completed.status_code == 200
    file_record = completed.json()
    assert file_record["mime_type"] == "image/png"
    assert (
        auth_context.client.post(
            f"/api/v1/files/upload-complete/{ticket['ticket_id']}",
            headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        ).json()["id"]
        == file_record["id"]
    )

    first_session = login(auth_context, first["login"], STUDENT_PASSWORD)
    own_files = auth_context.client.get(f"/api/v1/files/lesson/{lesson['id']}")
    assert own_files.status_code == 200
    assert [item["id"] for item in own_files.json()] == [file_record["id"]]
    downloaded = auth_context.client.get(file_record["download_url"])
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert downloaded.headers["cache-control"] == "private, no-store"
    assert (
        auth_context.client.delete(
            f"/api/v1/files/{file_record['id']}",
            headers={"X-CSRF-Token": first_session["csrf_token"]},
        ).status_code
        == 403
    )

    login(auth_context, second["login"], STUDENT_PASSWORD)
    assert auth_context.client.get(file_record["download_url"]).status_code == 404
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    assert (
        auth_context.client.delete(
            f"/api/v1/files/{file_record['id']}",
            headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        ).status_code
        == 204
    )
    assert auth_context.client.get(f"/api/v1/files/lesson/{lesson['id']}").json() == []


def test_file_signature_size_ticket_ownership_and_roles(
    auth_context: AuthTestContext, memory_storage: ObjectStorage
) -> None:
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    student = create_student(auth_context, teacher_session["csrf_token"], "file-validation")
    activate(auth_context, student["activation_token"])
    lesson = create_lesson(
        auth_context, teacher_session["csrf_token"], student["student_id"]
    ).json()
    bad_content = b"not-a-png"
    ticket = initialize_file(
        auth_context,
        teacher_session["csrf_token"],
        lesson["id"],
        "fake.png",
        bad_content,
    )
    bad_upload = auth_context.client.post(
        str(ticket["upload_url"]),
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        files={"file": ("fake.png", bad_content, "image/png")},
    )
    assert bad_upload.status_code == 422

    student_session = login(auth_context, student["login"], STUDENT_PASSWORD)
    assert (
        auth_context.client.post(
            str(ticket["upload_url"]),
            headers={"X-CSRF-Token": student_session["csrf_token"]},
            files={"file": ("fake.png", bad_content, "image/png")},
        ).status_code
        == 404
    )
    assert (
        auth_context.client.post(
            "/api/v1/files/upload-init",
            headers={"X-CSRF-Token": student_session["csrf_token"]},
            json={
                "purpose": "LESSON_MATERIAL",
                "target_type": "LESSON",
                "target_id": lesson["id"],
                "original_filename": "student.pdf",
                "byte_size": 10,
            },
        ).status_code
        == 403
    )
    teacher_session = login(auth_context, "teacher", TEACHER_PASSWORD)
    oversized = auth_context.client.post(
        "/api/v1/files/upload-init",
        headers={"X-CSRF-Token": teacher_session["csrf_token"]},
        json={
            "purpose": "LESSON_MATERIAL",
            "target_type": "LESSON",
            "target_id": lesson["id"],
            "original_filename": "large.pdf",
            "byte_size": 15 * 1024 * 1024 + 1,
        },
    )
    assert oversized.status_code == 422


def test_docx_validation_rejects_generic_zip() -> None:
    from app.modules.files.service import FileValidationError, detect_mime

    buffer = BytesIO()
    import zipfile

    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("random.txt", "not a document")
    with pytest.raises(FileValidationError):
        detect_mime(buffer.getvalue(), "fake.docx")


def test_expired_upload_cleanup_removes_object_and_ticket(
    auth_context: AuthTestContext, memory_storage: ObjectStorage
) -> None:
    with auth_context.sessions() as db:
        teacher_id = db.scalar(select(User.id).where(User.login == "teacher"))
        assert teacher_id is not None
        ticket = FileUploadTicket(
            owner_user_id=teacher_id,
            purpose="LESSON_MATERIAL",
            target_type="LESSON",
            target_id=uuid4(),
            storage_key="temporary/expired",
            original_filename="expired.pdf",
            declared_byte_size=5,
            status=UploadStatus.UPLOADED,
            expires_at=utc_now() - timedelta(minutes=1),
            created_at=utc_now() - timedelta(hours=1),
        )
        db.add(ticket)
        db.commit()
        ticket_id = ticket.id
    assert isinstance(memory_storage, MemoryStorage)
    memory_storage.objects["temporary/expired"] = b"%PDF"
    with auth_context.sessions() as db:
        assert cleanup_expired_uploads(db, memory_storage) == 1
        assert db.get(FileUploadTicket, ticket_id) is None
    assert "temporary/expired" not in memory_storage.objects
