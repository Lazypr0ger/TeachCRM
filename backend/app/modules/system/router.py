from fastapi import APIRouter
from sqlalchemy import func, select

from app.modules.auth.dependencies import DbSession, TeacherUser
from app.modules.auth.models import SessionRecord
from app.modules.auth.service import utc_now
from app.modules.notifications.models import OutboxEvent
from app.modules.system.schemas import SystemDiagnostics

router = APIRouter(prefix="/api/v1/teacher/system", tags=["teacher-system"])


@router.get("/diagnostics", response_model=SystemDiagnostics)
def diagnostics(_teacher: TeacherUser, db: DbSession) -> SystemDiagnostics:
    now = utc_now()
    pending_filter = OutboxEvent.status == "PENDING"
    pending = db.scalar(select(func.count()).select_from(OutboxEvent).where(pending_filter)) or 0
    retrying = (
        db.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(pending_filter, OutboxEvent.attempt_count > 0)
        )
        or 0
    )
    due = (
        db.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(pending_filter, OutboxEvent.next_attempt_at <= now)
        )
        or 0
    )
    oldest = db.scalar(select(func.min(OutboxEvent.created_at)).where(pending_filter))
    active_sessions = (
        db.scalar(
            select(func.count())
            .select_from(SessionRecord)
            .where(
                SessionRecord.revoked_at.is_(None),
                SessionRecord.expires_at > now,
                SessionRecord.idle_expires_at > now,
            )
        )
        or 0
    )
    return SystemDiagnostics(
        status="attention" if retrying or due else "ok",
        pending_outbox=pending,
        retrying_outbox=retrying,
        due_outbox=due,
        oldest_pending_at=oldest,
        active_sessions=active_sessions,
    )
