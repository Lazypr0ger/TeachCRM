from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.config import Settings, get_settings
from app.modules.auth.dependencies import DbSession, TeacherCsrfUser, TeacherUser
from app.modules.auth.schemas import MessageResponse
from app.modules.auth.security import token_hash
from app.modules.site_settings.service import trials_are_enabled
from app.modules.trials.schemas import (
    TrialConversionResponse,
    TrialConvertRequest,
    TrialCreateRequest,
    TrialPage,
    TrialResponse,
    TrialUpdateRequest,
)
from app.modules.trials.service import (
    TrialConflictError,
    TrialNotFoundError,
    TrialRateLimitError,
    convert_trial_request,
    create_trial_request,
    has_active_session,
    list_trial_requests,
    update_trial_request,
    web_intake,
)

public_router = APIRouter(prefix="/api/v1/public", tags=["public"])
teacher_router = APIRouter(prefix="/api/v1/teacher/trial-requests", tags=["teacher-trials"])
AppSettings = Annotated[Settings, Depends(get_settings)]


@public_router.post(
    "/trial-requests",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_public_trial(
    payload: TrialCreateRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> MessageResponse:
    if not trials_are_enabled(db, settings):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Приём заявок выключен")
    if has_active_session(db, request.cookies.get(settings.session_cookie_name)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Авторизованные пользователи не могут подать публичную заявку",
        )
    if payload.website:
        return MessageResponse(message="Заявка принята")
    host = request.client.host if request.client else "unknown"
    agent = request.headers.get("user-agent", "")[:200]
    client_hash = token_hash(f"trial:{host}:{agent}")
    try:
        create_trial_request(db, web_intake(payload), client_hash=client_hash)
    except TrialRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except TrialConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MessageResponse(message="Заявка принята")


@teacher_router.get("", response_model=TrialPage)
def trials(
    _teacher: TeacherUser,
    db: DbSession,
    request_status: Literal[
        "NEW",
        "IN_REVIEW",
        "RESCHEDULE_REQUESTED",
        "CONFIRMED",
        "COMPLETED",
        "REJECTED",
        "CANCELLED",
    ]
    | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TrialPage:
    return list_trial_requests(
        db,
        request_status=request_status,
        page=page,
        page_size=page_size,
    )


@teacher_router.patch("/{trial_id}", response_model=TrialResponse)
def update_trial(
    trial_id: UUID,
    payload: TrialUpdateRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> TrialResponse:
    try:
        return update_trial_request(db, trial_id, payload, teacher)
    except TrialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrialConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@teacher_router.post("/{trial_id}/convert", response_model=TrialConversionResponse)
def convert_trial(
    trial_id: UUID,
    payload: TrialConvertRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
    settings: AppSettings,
) -> TrialConversionResponse:
    try:
        return convert_trial_request(db, trial_id, payload, teacher, settings)
    except TrialNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TrialConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
