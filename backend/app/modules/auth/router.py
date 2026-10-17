from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import Settings, get_settings
from app.modules.auth.dependencies import CsrfUser, CurrentUser, DbSession
from app.modules.auth.models import SessionRecord
from app.modules.auth.schemas import (
    LoginRequest,
    MessageResponse,
    PasswordResetRequest,
    PasswordTokenRequest,
    SessionResponse,
    UserResponse,
)
from app.modules.auth.service import (
    AuthError,
    RateLimitError,
    activate_invitation,
    authenticate,
    create_session,
    reset_password,
    utc_now,
)
from app.modules.auth.service import (
    request_password_reset as save_password_reset_request,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> SessionResponse:
    try:
        user = authenticate(db, payload.login, payload.password)
    except RateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    session_token, csrf_token = create_session(
        db, user, settings, request.headers.get("user-agent")
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        max_age=settings.session_absolute_hours * 3600,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        key="tutorcrm_csrf",
        value=csrf_token,
        max_age=settings.session_absolute_hours * 3600,
        httponly=False,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/",
    )
    return SessionResponse(user=UserResponse.model_validate(user), csrf_token=csrf_token)


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    _user: CsrfUser,
    db: DbSession,
    settings: AppSettings,
) -> MessageResponse:
    record: SessionRecord = request.state.auth_session
    record.revoked_at = utc_now()
    db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie("tutorcrm_csrf", path="/")
    return MessageResponse(message="Вы вышли из системы")


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/activate", response_model=MessageResponse)
def activate(payload: PasswordTokenRequest, db: DbSession) -> MessageResponse:
    try:
        activate_invitation(db, payload.token, payload.new_password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MessageResponse(message="Аккаунт активирован. Теперь можно войти")


@router.post("/request-password-reset", response_model=MessageResponse)
def request_password_reset(payload: PasswordResetRequest, db: DbSession) -> MessageResponse:
    save_password_reset_request(db, payload.login)
    return MessageResponse(
        message="Если аккаунт существует, запрос принят. Получите ссылку у преподавателя"
    )


@router.post("/reset-password", response_model=MessageResponse)
def complete_password_reset(payload: PasswordTokenRequest, db: DbSession) -> MessageResponse:
    try:
        reset_password(db, payload.token, payload.new_password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MessageResponse(message="Пароль изменён. Все прежние сессии завершены")
