from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.modules.auth.dependencies import DbSession, TeacherCsrfUser, TeacherUser
from app.modules.lessons.service import LessonNotFoundError
from app.modules.scheduling.recurrence_schemas import (
    RecurrenceRuleCreateRequest,
    RecurrenceRuleResponse,
    RecurrenceRuleUpdateRequest,
)
from app.modules.scheduling.recurrence_service import (
    RecurrenceConflictError,
    RecurrenceNotFoundError,
    RecurrenceVersionError,
    create_recurrence_rule,
    deactivate_recurrence_rule,
    list_recurrence_rules,
    rematerialize_rule,
    update_recurrence_rule,
)

router = APIRouter(prefix="/api/v1/teacher/recurrence-rules", tags=["lesson-recurrence"])


def recurrence_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (RecurrenceNotFoundError, LessonNotFoundError)):
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=code, detail=str(exc))


@router.get("", response_model=list[RecurrenceRuleResponse])
def rules(teacher: TeacherUser, db: DbSession) -> list[RecurrenceRuleResponse]:
    return list_recurrence_rules(db, teacher.id)


@router.post("", response_model=RecurrenceRuleResponse, status_code=status.HTTP_201_CREATED)
def add_rule(
    payload: RecurrenceRuleCreateRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> RecurrenceRuleResponse:
    try:
        return create_recurrence_rule(db, payload, teacher)
    except (RecurrenceConflictError, LessonNotFoundError) as exc:
        raise recurrence_http_error(exc) from exc


@router.patch("/{rule_id}", response_model=RecurrenceRuleResponse)
def edit_rule(
    rule_id: UUID,
    payload: RecurrenceRuleUpdateRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> RecurrenceRuleResponse:
    try:
        return update_recurrence_rule(db, rule_id, payload, teacher)
    except (
        RecurrenceNotFoundError,
        RecurrenceConflictError,
        RecurrenceVersionError,
    ) as exc:
        raise recurrence_http_error(exc) from exc


@router.post("/{rule_id}/materialize", response_model=RecurrenceRuleResponse)
def materialize(rule_id: UUID, teacher: TeacherCsrfUser, db: DbSession) -> RecurrenceRuleResponse:
    try:
        return rematerialize_rule(db, rule_id, teacher)
    except (RecurrenceNotFoundError, RecurrenceConflictError) as exc:
        raise recurrence_http_error(exc) from exc


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_rule(rule_id: UUID, teacher: TeacherCsrfUser, db: DbSession) -> Response:
    try:
        deactivate_recurrence_rule(db, rule_id, teacher)
    except RecurrenceNotFoundError as exc:
        raise recurrence_http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
