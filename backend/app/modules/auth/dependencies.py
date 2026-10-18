import hmac
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.modules.auth.models import SessionRecord, User, UserRole, UserStatus
from app.modules.auth.security import token_hash
from app.modules.auth.service import expired, utc_now

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbSession) -> User:
    settings = get_settings()
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется вход")
    record = db.scalar(
        select(SessionRecord).where(SessionRecord.token_hash == token_hash(raw_token))
    )
    now = utc_now()
    if (
        record is None
        or record.revoked_at is not None
        or expired(record.expires_at, now)
        or expired(record.idle_expires_at, now)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия истекла")
    user = db.get(User, record.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия недействительна"
        )
    record.last_seen_at = now
    record.idle_expires_at = now + timedelta(hours=settings.session_idle_hours)
    request.state.auth_session = record
    db.commit()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_teacher(user: CurrentUser) -> User:
    if user.role != UserRole.TEACHER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Действие запрещено")
    return user


TeacherUser = Annotated[User, Depends(require_teacher)]


def require_student(user: CurrentUser) -> User:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Действие запрещено")
    return user


StudentUser = Annotated[User, Depends(require_student)]


def require_csrf(
    request: Request,
    user: CurrentUser,
    x_csrf_token: Annotated[str | None, Header()] = None,
) -> User:
    record: SessionRecord = request.state.auth_session
    supplied_hash = token_hash(x_csrf_token or "")
    if not hmac.compare_digest(supplied_hash, record.csrf_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="CSRF-токен недействителен"
        )
    return user


CsrfUser = Annotated[User, Depends(require_csrf)]


def require_teacher_csrf(user: CsrfUser) -> User:
    if user.role != UserRole.TEACHER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Действие запрещено")
    return user


TeacherCsrfUser = Annotated[User, Depends(require_teacher_csrf)]


def require_student_csrf(user: CsrfUser) -> User:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Действие запрещено")
    return user


StudentCsrfUser = Annotated[User, Depends(require_student_csrf)]
