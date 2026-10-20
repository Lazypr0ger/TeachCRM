from datetime import datetime

from pydantic import BaseModel


class SystemDiagnostics(BaseModel):
    status: str
    pending_outbox: int
    retrying_outbox: int
    due_outbox: int
    oldest_pending_at: datetime | None
    active_sessions: int
