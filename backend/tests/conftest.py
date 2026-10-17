from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import get_db
from app.core.models import Base
from app.main import app
from app.modules.auth.models import User
from app.modules.auth.service import bootstrap_teacher

TEACHER_PASSWORD = "Teacher-password-123"


@dataclass
class AuthTestContext:
    client: TestClient
    sessions: sessionmaker[Session]
    teacher: User


@pytest.fixture
def auth_context(tmp_path: Path) -> Iterator[AuthTestContext]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth.sqlite3'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        teacher = bootstrap_teacher(db, "teacher", TEACHER_PASSWORD)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield AuthTestContext(client=client, sessions=factory, teacher=teacher)
    app.dependency_overrides.clear()
    engine.dispose()
