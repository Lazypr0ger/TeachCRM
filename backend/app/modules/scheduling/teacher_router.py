from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.modules.auth.dependencies import DbSession, TeacherCsrfUser, TeacherUser
from app.modules.scheduling.schemas import (
    AvailabilityExceptionRequest,
    AvailabilityExceptionResponse,
    AvailabilityRuleRequest,
    AvailabilityRuleResponse,
)
from app.modules.scheduling.service import (
    AvailabilityConflictError,
    AvailabilityNotFoundError,
    create_exception,
    create_rule,
    delete_exception,
    delete_rule,
    list_exceptions,
    list_rules,
    update_exception,
    update_rule,
)

router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-availability"])


def availability_http_error(exc: Exception) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc, AvailabilityNotFoundError)
        else status.HTTP_409_CONFLICT
    )
    return HTTPException(status_code=code, detail=str(exc))


@router.get("/availability-rules", response_model=list[AvailabilityRuleResponse])
def rules(teacher: TeacherUser, db: DbSession) -> list[AvailabilityRuleResponse]:
    return list_rules(db, teacher.id)


@router.post(
    "/availability-rules",
    response_model=AvailabilityRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_rule(
    payload: AvailabilityRuleRequest, teacher: TeacherCsrfUser, db: DbSession
) -> AvailabilityRuleResponse:
    return create_rule(db, payload, teacher)


@router.patch("/availability-rules/{rule_id}", response_model=AvailabilityRuleResponse)
def edit_rule(
    rule_id: UUID,
    payload: AvailabilityRuleRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> AvailabilityRuleResponse:
    try:
        return update_rule(db, rule_id, payload, teacher)
    except AvailabilityNotFoundError as exc:
        raise availability_http_error(exc) from exc


@router.delete("/availability-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_rule(rule_id: UUID, teacher: TeacherCsrfUser, db: DbSession) -> Response:
    try:
        delete_rule(db, rule_id, teacher)
    except AvailabilityNotFoundError as exc:
        raise availability_http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/availability-exceptions", response_model=list[AvailabilityExceptionResponse])
def exceptions(teacher: TeacherUser, db: DbSession) -> list[AvailabilityExceptionResponse]:
    return list_exceptions(db, teacher.id)


@router.post(
    "/availability-exceptions",
    response_model=AvailabilityExceptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_exception(
    payload: AvailabilityExceptionRequest, teacher: TeacherCsrfUser, db: DbSession
) -> AvailabilityExceptionResponse:
    try:
        return create_exception(db, payload, teacher)
    except AvailabilityConflictError as exc:
        raise availability_http_error(exc) from exc


@router.patch("/availability-exceptions/{item_id}", response_model=AvailabilityExceptionResponse)
def edit_exception(
    item_id: UUID,
    payload: AvailabilityExceptionRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> AvailabilityExceptionResponse:
    try:
        return update_exception(db, item_id, payload, teacher)
    except (AvailabilityNotFoundError, AvailabilityConflictError) as exc:
        raise availability_http_error(exc) from exc


@router.delete("/availability-exceptions/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_exception(item_id: UUID, teacher: TeacherCsrfUser, db: DbSession) -> Response:
    try:
        delete_exception(db, item_id, teacher)
    except AvailabilityNotFoundError as exc:
        raise availability_http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
