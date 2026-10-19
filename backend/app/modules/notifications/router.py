from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.modules.auth.dependencies import CsrfUser, CurrentUser, DbSession
from app.modules.notifications.schemas import NotificationPage, NotificationResponse
from app.modules.notifications.service import (
    NotificationNotFoundError,
    list_notifications,
    mark_all_read,
    mark_notification_read,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


class ReadAllResponse(BaseModel):
    updated: int


@router.get("", response_model=NotificationPage)
def notifications(
    user: CurrentUser,
    db: DbSession,
    notification_type: str | None = Query(default=None, alias="type", max_length=40),
    is_read: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> NotificationPage:
    return list_notifications(
        db,
        user,
        notification_type=notification_type,
        is_read=is_read,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def read_notification(notification_id: UUID, user: CsrfUser, db: DbSession) -> NotificationResponse:
    try:
        return mark_notification_read(db, notification_id, user)
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/read-all", response_model=ReadAllResponse)
def read_all(user: CsrfUser, db: DbSession) -> ReadAllResponse:
    return ReadAllResponse(updated=mark_all_read(db, user))
