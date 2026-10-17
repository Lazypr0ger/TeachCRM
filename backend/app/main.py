from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.db import create_db_engine, database_is_ready


class HealthResponse(BaseModel):
    status: str
    service: str


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    application.state.db_engine = create_db_engine()
    yield
    application.state.db_engine.dispose()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


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

