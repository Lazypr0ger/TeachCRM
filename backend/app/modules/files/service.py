import hashlib
import logging
import re
import zipfile
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.models import StudentProfile, User, UserRole
from app.modules.auth.service import add_audit, expired, utc_now
from app.modules.files.models import (
    FileLink,
    FilePurpose,
    FileUploadTicket,
    StoredFile,
    UploadStatus,
)
from app.modules.files.schemas import FileResponse, UploadInitRequest, UploadTicketResponse
from app.modules.files.storage import ObjectStorage
from app.modules.lessons.models import Lesson

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class FileError(Exception):
    pass


class FileNotFoundError(FileError):
    pass


class FilePermissionError(FileError):
    pass


class FileValidationError(FileError):
    pass


class FileConflictError(FileError):
    pass


def safe_filename(value: str) -> str:
    name = Path(value.replace("\\", "/")).name.strip()
    if not name or name in {".", ".."} or re.search(r"[\x00-\x1f\x7f]", name):
        raise FileValidationError("Некорректное имя файла")
    return name


def detect_mime(content: bytes, filename: str) -> str:
    extension = Path(filename).suffix.lower()
    expected = ALLOWED_EXTENSIONS.get(extension)
    if expected is None:
        raise FileValidationError("Тип файла не разрешён")
    detected: str | None = None
    if content.startswith(b"%PDF-"):
        detected = "application/pdf"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        detected = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        detected = "image/jpeg"
    elif len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        detected = "image/webp"
    elif content.startswith(b"PK"):
        detected = validate_docx(content)
    if detected is None or detected != expected:
        raise FileValidationError("Содержимое файла не соответствует его расширению")
    return detected


def validate_docx(content: bytes) -> str:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            names = {member.filename for member in members}
            if "[Content_Types].xml" not in names or not any(
                name.startswith("word/") for name in names
            ):
                raise FileValidationError("Файл не является документом DOCX")
            if len(members) > 2_000:
                raise FileValidationError("В документе слишком много вложенных элементов")
            expanded = sum(member.file_size for member in members)
            compressed = sum(max(member.compress_size, 1) for member in members)
            if expanded > 100 * 1024 * 1024 or expanded / compressed > 100:
                raise FileValidationError("Документ имеет опасную степень сжатия")
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise FileValidationError("Повреждённый документ DOCX") from exc
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def ensure_lesson_access(db: Session, lesson_id: UUID, user: User) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise FileNotFoundError("Урок не найден")
    if user.role == UserRole.TEACHER and lesson.teacher_id != user.id:
        raise FileNotFoundError("Урок не найден")
    if user.role == UserRole.STUDENT:
        profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
        if profile is None or lesson.student_id != profile.id:
            raise FileNotFoundError("Урок не найден")
    return lesson


def validate_upload_target(db: Session, payload: UploadInitRequest, user: User) -> None:
    if payload.purpose == FilePurpose.LESSON_MATERIAL and payload.target_type == "LESSON":
        if user.role != UserRole.TEACHER:
            raise FilePermissionError("Только преподаватель добавляет материалы урока")
        ensure_lesson_access(db, payload.target_id, user)
        return
    if payload.target_type == "ASSIGNMENT" and payload.purpose in {
        FilePurpose.ASSIGNMENT_MATERIAL,
        FilePurpose.HOMEWORK,
    }:
        from app.modules.homework.models import Assignment, HomeworkSubmission

        assignment = db.get(Assignment, payload.target_id)
        if assignment is None:
            raise FileNotFoundError("Задание не найдено")
        ensure_lesson_access(db, assignment.lesson_id, user)
        if payload.purpose == FilePurpose.ASSIGNMENT_MATERIAL:
            if user.role != UserRole.TEACHER:
                raise FilePermissionError("Материалы задания добавляет преподаватель")
        else:
            if user.role != UserRole.STUDENT:
                raise FilePermissionError("Ответ на задание загружает ученик")
            if db.scalar(
                select(HomeworkSubmission.id).where(
                    HomeworkSubmission.assignment_id == assignment.id
                )
            ):
                raise FileConflictError("Ответ на это задание уже отправлен")
        return
    raise FileValidationError("Тип вложения не соответствует объекту")


def file_response(item: StoredFile) -> FileResponse:
    return FileResponse(
        id=item.id,
        original_filename=item.original_filename,
        mime_type=item.mime_type,
        byte_size=item.byte_size,
        purpose=item.purpose,
        checksum_sha256=item.checksum_sha256,
        created_at=item.created_at,
        download_url=f"/api/v1/files/{item.id}/download",
    )


def initiate_upload(
    db: Session, payload: UploadInitRequest, user: User, settings: Settings
) -> UploadTicketResponse:
    filename = safe_filename(payload.original_filename)
    if payload.byte_size > settings.file_max_bytes:
        raise FileValidationError("Файл превышает лимит 15 МБ")
    validate_upload_target(db, payload, user)
    linked_count = (
        db.scalar(
            select(func.count())
            .select_from(FileLink)
            .where(
                FileLink.entity_type == payload.target_type,
                FileLink.entity_id == payload.target_id,
                StoredFile.purpose == payload.purpose,
            )
            .join(StoredFile, StoredFile.id == FileLink.file_id)
        )
        or 0
    )
    active_tickets = (
        db.scalar(
            select(func.count())
            .select_from(FileUploadTicket)
            .where(
                FileUploadTicket.target_type == payload.target_type,
                FileUploadTicket.target_id == payload.target_id,
                FileUploadTicket.purpose == payload.purpose,
                FileUploadTicket.status != UploadStatus.COMPLETED,
                FileUploadTicket.expires_at > utc_now(),
            )
        )
        or 0
    )
    if linked_count + active_tickets >= settings.file_max_per_target:
        raise FileConflictError("Для объекта уже достигнут лимит 10 файлов")
    ticket = FileUploadTicket(
        owner_user_id=user.id,
        purpose=payload.purpose,
        target_type=payload.target_type,
        target_id=payload.target_id,
        storage_key=f"temporary/{user.id}/{uuid4()}",
        original_filename=filename,
        declared_byte_size=payload.byte_size,
        status=UploadStatus.INITIATED,
        expires_at=utc_now() + timedelta(minutes=settings.upload_ticket_ttl_minutes),
        created_at=utc_now(),
    )
    db.add(ticket)
    db.flush()
    add_audit(db, user.id, "FILE_UPLOAD_INITIATED", "file_upload_ticket", ticket.id)
    db.commit()
    db.refresh(ticket)
    return UploadTicketResponse(
        ticket_id=ticket.id,
        upload_url=f"/api/v1/files/upload-tickets/{ticket.id}/content",
        expires_at=ticket.expires_at,
        max_bytes=settings.file_max_bytes,
    )


def get_owned_ticket(db: Session, ticket_id: UUID, user: User) -> FileUploadTicket:
    ticket = db.scalar(
        select(FileUploadTicket).where(
            FileUploadTicket.id == ticket_id,
            FileUploadTicket.owner_user_id == user.id,
        )
    )
    if ticket is None:
        raise FileNotFoundError("Upload ticket не найден")
    if expired(ticket.expires_at, utc_now()):
        raise FileConflictError("Upload ticket истёк")
    return ticket


def upload_content(
    db: Session,
    ticket_id: UUID,
    content: bytes,
    user: User,
    settings: Settings,
    storage: ObjectStorage,
) -> None:
    ticket = get_owned_ticket(db, ticket_id, user)
    if ticket.status == UploadStatus.COMPLETED:
        raise FileConflictError("Загрузка уже завершена")
    if not content or len(content) > settings.file_max_bytes:
        raise FileValidationError("Размер файла должен быть от 1 байта до 15 МБ")
    if len(content) != ticket.declared_byte_size:
        raise FileValidationError("Размер файла не совпадает с заявленным")
    mime_type = detect_mime(content, ticket.original_filename)
    checksum = hashlib.sha256(content).hexdigest()
    storage.put(ticket.storage_key, content, mime_type)
    ticket.detected_mime_type = mime_type
    ticket.actual_byte_size = len(content)
    ticket.checksum_sha256 = checksum
    ticket.status = UploadStatus.UPLOADED
    ticket.uploaded_at = utc_now()
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(ticket.storage_key)
        raise


def complete_upload(
    db: Session,
    ticket_id: UUID,
    user: User,
    storage: ObjectStorage,
) -> FileResponse:
    ticket = get_owned_ticket(db, ticket_id, user)
    if ticket.status == UploadStatus.COMPLETED and ticket.completed_file_id is not None:
        existing = db.get(StoredFile, ticket.completed_file_id)
        if existing is None:
            raise FileConflictError("Запись завершённого файла повреждена")
        return file_response(existing)
    if (
        ticket.status != UploadStatus.UPLOADED
        or ticket.detected_mime_type is None
        or ticket.actual_byte_size is None
        or ticket.checksum_sha256 is None
    ):
        raise FileConflictError("Содержимое файла ещё не загружено")
    validate_upload_target(
        db,
        UploadInitRequest(
            purpose=ticket.purpose,
            target_type=ticket.target_type,
            target_id=ticket.target_id,
            original_filename=ticket.original_filename,
            byte_size=ticket.actual_byte_size,
        ),
        user,
    )
    file_id = uuid4()
    final_key = f"files/{file_id}/{ticket.original_filename}"
    storage.copy(ticket.storage_key, final_key, ticket.detected_mime_type)
    item = StoredFile(
        id=file_id,
        owner_user_id=user.id,
        storage_key=final_key,
        original_filename=ticket.original_filename,
        mime_type=ticket.detected_mime_type,
        byte_size=ticket.actual_byte_size,
        checksum_sha256=ticket.checksum_sha256,
        purpose=ticket.purpose,
        created_at=utc_now(),
    )
    db.add(item)
    db.add(FileLink(file_id=file_id, entity_type=ticket.target_type, entity_id=ticket.target_id))
    ticket.status = UploadStatus.COMPLETED
    ticket.completed_at = utc_now()
    ticket.completed_file_id = file_id
    try:
        db.flush()
        add_audit(db, user.id, "FILE_COMMITTED", "file", file_id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        storage.delete(final_key)
        raise FileConflictError("Не удалось завершить загрузку") from exc
    try:
        storage.delete(ticket.storage_key)
    except Exception:
        logger.exception("temporary_file_delete_failed ticket_id=%s", ticket.id)
    db.refresh(item)
    return file_response(item)


def list_lesson_files(db: Session, lesson_id: UUID, user: User) -> list[FileResponse]:
    ensure_lesson_access(db, lesson_id, user)
    items = db.scalars(
        select(StoredFile)
        .join(FileLink, FileLink.file_id == StoredFile.id)
        .where(FileLink.entity_type == "LESSON", FileLink.entity_id == lesson_id)
        .order_by(StoredFile.created_at)
    ).all()
    return [file_response(item) for item in items]


def get_authorized_file_link(db: Session, file_id: UUID, user: User) -> tuple[StoredFile, FileLink]:
    row = db.execute(
        select(StoredFile, FileLink)
        .join(FileLink, FileLink.file_id == StoredFile.id)
        .where(StoredFile.id == file_id)
    ).one_or_none()
    if row is None:
        raise FileNotFoundError("Файл не найден")
    item, link = row
    if link.entity_type == "LESSON":
        ensure_lesson_access(db, link.entity_id, user)
    elif link.entity_type == "ASSIGNMENT":
        from app.modules.homework.models import Assignment

        assignment = db.get(Assignment, link.entity_id)
        if assignment is None:
            raise FileNotFoundError("Файл не найден")
        ensure_lesson_access(db, assignment.lesson_id, user)
        if item.purpose == FilePurpose.HOMEWORK and item.owner_user_id != user.id:
            raise FileNotFoundError("Файл не найден")
    elif link.entity_type == "SUBMISSION":
        from app.modules.homework.models import Assignment, HomeworkSubmission

        submission = db.get(HomeworkSubmission, link.entity_id)
        assignment = db.get(Assignment, submission.assignment_id) if submission else None
        if assignment is None:
            raise FileNotFoundError("Файл не найден")
        ensure_lesson_access(db, assignment.lesson_id, user)
    else:
        raise FileNotFoundError("Файл не найден")
    return item, link


def get_authorized_file(db: Session, file_id: UUID, user: User) -> StoredFile:
    return get_authorized_file_link(db, file_id, user)[0]


def delete_file(db: Session, file_id: UUID, user: User, storage: ObjectStorage) -> None:
    item, link = get_authorized_file_link(db, file_id, user)
    teacher_file = item.purpose in {
        FilePurpose.LESSON_MATERIAL,
        FilePurpose.ASSIGNMENT_MATERIAL,
    }
    student_draft = item.purpose == FilePurpose.HOMEWORK and link.entity_type == "ASSIGNMENT"
    if (teacher_file and user.role != UserRole.TEACHER) or (
        student_draft and user.role != UserRole.STUDENT
    ):
        raise FilePermissionError("Удалять этот файл нельзя")
    if not teacher_file and not student_draft:
        raise FilePermissionError("Финальный ответ нельзя изменить")
    storage_key = item.storage_key
    add_audit(db, user.id, "FILE_DELETED", "file", item.id)
    db.delete(item)
    db.commit()
    try:
        storage.delete(storage_key)
    except Exception:
        logger.exception("stored_file_delete_failed file_id=%s", file_id)


def cleanup_expired_uploads(db: Session, storage: ObjectStorage, *, batch_size: int = 100) -> int:
    tickets = db.scalars(
        select(FileUploadTicket)
        .where(
            FileUploadTicket.status != UploadStatus.COMPLETED,
            FileUploadTicket.expires_at <= utc_now(),
        )
        .order_by(FileUploadTicket.expires_at)
        .limit(batch_size)
    ).all()
    deleted = 0
    for ticket in tickets:
        try:
            storage.delete(ticket.storage_key)
        except Exception:
            logger.exception("expired_upload_delete_failed ticket_id=%s", ticket.id)
            continue
        db.delete(ticket)
        deleted += 1
    db.commit()
    return deleted
