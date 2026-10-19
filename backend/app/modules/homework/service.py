from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import StudentProfile, User
from app.modules.auth.service import add_audit, utc_now
from app.modules.files.models import FileLink, FilePurpose, StoredFile
from app.modules.files.service import FileNotFoundError, ensure_lesson_access, file_response
from app.modules.homework.models import Assignment, HomeworkSubmission
from app.modules.homework.schemas import (
    AssignmentCreateRequest,
    AssignmentResponse,
    AssignmentUpdateRequest,
    HomeworkResponse,
    SubmissionCreateRequest,
    SubmissionResponse,
)
from app.modules.lessons.models import Lesson


class HomeworkError(Exception):
    pass


class HomeworkNotFoundError(HomeworkError):
    pass


class HomeworkConflictError(HomeworkError):
    pass


class HomeworkValidationError(HomeworkError):
    pass


def ensure_homework_lesson(db: Session, lesson_id: UUID, user: User) -> None:
    try:
        ensure_lesson_access(db, lesson_id, user)
    except FileNotFoundError as exc:
        raise HomeworkNotFoundError("Урок не найден") from exc


def assignment_files(db: Session, assignment_id: UUID) -> list[StoredFile]:
    return list(
        db.scalars(
            select(StoredFile)
            .join(FileLink, FileLink.file_id == StoredFile.id)
            .where(
                FileLink.entity_type == "ASSIGNMENT",
                FileLink.entity_id == assignment_id,
                StoredFile.purpose == FilePurpose.ASSIGNMENT_MATERIAL,
            )
            .order_by(StoredFile.created_at, StoredFile.id)
        ).all()
    )


def submission_files(db: Session, submission_id: UUID) -> list[StoredFile]:
    return list(
        db.scalars(
            select(StoredFile)
            .join(FileLink, FileLink.file_id == StoredFile.id)
            .where(
                FileLink.entity_type == "SUBMISSION",
                FileLink.entity_id == submission_id,
                StoredFile.purpose == FilePurpose.HOMEWORK,
            )
            .order_by(StoredFile.created_at, StoredFile.id)
        ).all()
    )


def homework_draft_files(db: Session, assignment_id: UUID, owner_user_id: UUID) -> list[StoredFile]:
    return list(
        db.scalars(
            select(StoredFile)
            .join(FileLink, FileLink.file_id == StoredFile.id)
            .where(
                FileLink.entity_type == "ASSIGNMENT",
                FileLink.entity_id == assignment_id,
                StoredFile.purpose == FilePurpose.HOMEWORK,
                StoredFile.owner_user_id == owner_user_id,
            )
            .order_by(StoredFile.created_at, StoredFile.id)
        ).all()
    )


def assignment_response(db: Session, item: Assignment) -> AssignmentResponse:
    return AssignmentResponse(
        id=item.id,
        lesson_id=item.lesson_id,
        description=item.description,
        due_at=item.due_at,
        version=item.version,
        created_at=item.created_at,
        updated_at=item.updated_at,
        files=[file_response(file) for file in assignment_files(db, item.id)],
    )


def submission_response(db: Session, item: HomeworkSubmission) -> SubmissionResponse:
    return SubmissionResponse(
        id=item.id,
        assignment_id=item.assignment_id,
        answer_text=item.answer_text,
        submitted_at=item.submitted_at,
        files=[file_response(file) for file in submission_files(db, item.id)],
    )


def get_assignment(db: Session, assignment_id: UUID) -> Assignment:
    item = db.get(Assignment, assignment_id)
    if item is None:
        raise HomeworkNotFoundError("Задание не найдено")
    return item


def get_homework(db: Session, lesson_id: UUID, user: User) -> HomeworkResponse:
    ensure_homework_lesson(db, lesson_id, user)
    assignment = db.scalar(select(Assignment).where(Assignment.lesson_id == lesson_id))
    if assignment is None:
        return HomeworkResponse(state="NO_HOMEWORK", assignment=None, submission=None)
    submission = db.scalar(
        select(HomeworkSubmission).where(HomeworkSubmission.assignment_id == assignment.id)
    )
    return HomeworkResponse(
        state="ACCEPTED" if submission else "NEEDS_RESPONSE",
        assignment=assignment_response(db, assignment),
        submission=submission_response(db, submission) if submission else None,
        draft_files=(
            [file_response(file) for file in homework_draft_files(db, assignment.id, user.id)]
            if not submission and user.role == "STUDENT"
            else []
        ),
    )


def create_assignment(
    db: Session, lesson_id: UUID, payload: AssignmentCreateRequest, teacher: User
) -> HomeworkResponse:
    ensure_homework_lesson(db, lesson_id, teacher)
    if db.scalar(select(Assignment.id).where(Assignment.lesson_id == lesson_id)):
        raise HomeworkConflictError("Для урока уже создано задание")
    item = Assignment(
        lesson_id=lesson_id,
        description=payload.description,
        due_at=payload.due_at,
        created_by_user_id=teacher.id,
        version=1,
    )
    db.add(item)
    try:
        db.flush()
        add_audit(db, teacher.id, "ASSIGNMENT_CREATED", "assignment", item.id)
        lesson = db.get(Lesson, lesson_id)
        student_profile = db.get(StudentProfile, lesson.student_id) if lesson else None
        if student_profile is not None:
            from app.modules.notifications.service import enqueue_notification

            enqueue_notification(
                db,
                event_type="HOMEWORK_ASSIGNED",
                aggregate_id=item.id,
                recipient_user_id=student_profile.user_id,
                title="Новое домашнее задание",
                body="Преподаватель добавил домашнее задание к уроку.",
                target_type="LESSON",
                target_id=lesson_id,
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HomeworkConflictError("Для урока уже создано задание") from exc
    db.refresh(item)
    return HomeworkResponse(
        state="NEEDS_RESPONSE",
        assignment=assignment_response(db, item),
        submission=None,
        draft_files=[],
    )


def update_assignment(
    db: Session, assignment_id: UUID, payload: AssignmentUpdateRequest, teacher: User
) -> HomeworkResponse:
    item = db.scalar(select(Assignment).where(Assignment.id == assignment_id).with_for_update())
    if item is None:
        raise HomeworkNotFoundError("Задание не найдено")
    ensure_homework_lesson(db, item.lesson_id, teacher)
    if item.version != payload.version:
        raise HomeworkConflictError("Задание уже было изменено")
    if "description" in payload.model_fields_set and payload.description is not None:
        item.description = payload.description
    if "due_at" in payload.model_fields_set:
        item.due_at = payload.due_at
    item.version += 1
    add_audit(db, teacher.id, "ASSIGNMENT_UPDATED", "assignment", item.id)
    db.commit()
    db.refresh(item)
    submission = db.scalar(
        select(HomeworkSubmission).where(HomeworkSubmission.assignment_id == item.id)
    )
    return HomeworkResponse(
        state="ACCEPTED" if submission else "NEEDS_RESPONSE",
        assignment=assignment_response(db, item),
        submission=submission_response(db, submission) if submission else None,
        draft_files=[],
    )


def create_submission(
    db: Session, assignment_id: UUID, payload: SubmissionCreateRequest, student: User
) -> SubmissionResponse:
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == student.id))
    if profile is None:
        raise HomeworkNotFoundError("Профиль ученика не найден")
    assignment = db.scalar(
        select(Assignment).where(Assignment.id == assignment_id).with_for_update()
    )
    if assignment is None:
        raise HomeworkNotFoundError("Задание не найдено")
    try:
        ensure_lesson_access(db, assignment.lesson_id, student)
    except FileNotFoundError as exc:
        raise HomeworkNotFoundError("Задание не найдено") from exc
    existing = db.scalar(
        select(HomeworkSubmission).where(HomeworkSubmission.assignment_id == assignment.id)
    )
    if existing is not None:
        if (
            existing.student_id == profile.id
            and existing.idempotency_key == payload.idempotency_key
        ):
            return submission_response(db, existing)
        raise HomeworkConflictError("Финальный ответ уже отправлен")

    files: list[tuple[StoredFile, FileLink]] = []
    if payload.file_ids:
        files = list(
            db.execute(
                select(StoredFile, FileLink)
                .join(FileLink, FileLink.file_id == StoredFile.id)
                .where(
                    StoredFile.id.in_(payload.file_ids),
                    StoredFile.owner_user_id == student.id,
                    StoredFile.purpose == FilePurpose.HOMEWORK,
                    FileLink.entity_type == "ASSIGNMENT",
                    FileLink.entity_id == assignment.id,
                )
                .with_for_update()
            ).all()
        )
        if len(files) != len(payload.file_ids):
            raise HomeworkValidationError("Один или несколько файлов недоступны")

    now = utc_now()
    item = HomeworkSubmission(
        assignment_id=assignment.id,
        student_id=profile.id,
        answer_text=payload.answer_text,
        idempotency_key=payload.idempotency_key,
        submitted_at=now,
        created_at=now,
    )
    db.add(item)
    try:
        db.flush()
        for _file, link in files:
            link.entity_type = "SUBMISSION"
            link.entity_id = item.id
        add_audit(
            db,
            student.id,
            "HOMEWORK_SUBMITTED",
            "homework_submission",
            item.id,
            request_id=payload.idempotency_key,
        )
        lesson = db.get(Lesson, assignment.lesson_id)
        if lesson is not None:
            from app.modules.notifications.service import enqueue_notification

            enqueue_notification(
                db,
                event_type="HOMEWORK_SUBMITTED",
                aggregate_id=item.id,
                recipient_user_id=lesson.teacher_id,
                title="Получен ответ на домашнее задание",
                body="Ученик отправил финальный ответ.",
                target_type="LESSON",
                target_id=lesson.id,
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(
            select(HomeworkSubmission).where(
                HomeworkSubmission.student_id == profile.id,
                HomeworkSubmission.idempotency_key == payload.idempotency_key,
            )
        )
        if existing is not None and existing.assignment_id == assignment.id:
            return submission_response(db, existing)
        if existing is not None:
            raise HomeworkConflictError("Идентификатор запроса уже использован") from exc
        raise HomeworkConflictError("Финальный ответ уже отправлен") from exc
    db.refresh(item)
    return submission_response(db, item)
