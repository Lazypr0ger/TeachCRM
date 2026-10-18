from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.db import create_db_engine, create_session_factory, database_is_ready
from app.modules.auth.router import router as auth_router
from app.modules.auth.teacher_router import router as teacher_auth_router
from app.modules.lessons.dashboard_router import router as teacher_dashboard_router
from app.modules.lessons.student_router import router as student_lessons_router
from app.modules.lessons.teacher_router import router as teacher_lessons_router
from app.modules.students.router import router as teacher_students_router


class HealthResponse(BaseModel):
    status: str
    service: str


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    application.state.db_engine = create_db_engine()
    application.state.session_factory = create_session_factory(application.state.db_engine)
    yield
    application.state.db_engine.dispose()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(teacher_auth_router)
app.include_router(teacher_students_router)
app.include_router(teacher_lessons_router)
app.include_router(student_lessons_router)
app.include_router(teacher_dashboard_router)


@app.get("/health/live", response_model=HealthResponse, tags=["health"])
def live() -> HealthResponse:
    return HealthResponse(status="ok", service="api")


@app.get("/health/ready", response_model=HealthResponse, tags=["health"])
def ready() -> HealthResponse:
    try:
        is_ready = database_is_ready(app.state.db_engine)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "database_unavailable", "message": "База данных недоступна"},
        ) from exc
    if not is_ready:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return HealthResponse(status="ready", service="api")
