from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Keep tests independent from developer-local .env values.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./apex.pytest.db")
os.environ.setdefault("AUTH_MODE", "dev")
os.environ.setdefault("ADMIN_API_KEY", "dev-admin-key")

from apex_predict.api.main import app
from apex_predict.config import get_settings
from apex_predict.db import Base, get_async_session
from apex_predict.enums import QuestionType, SessionState, SessionType
from apex_predict.models import Event, QuestionInstance, ScoringRule, Season, Session


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture()
async def session_maker(tmp_path: Path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    yield maker

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture()
async def db_session(session_maker) -> AsyncGenerator[AsyncSession, None]:
    async with session_maker() as session:
        yield session


@pytest.fixture()
async def client(session_maker) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_async_session] = _override_get_async_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    return {"X-User-Id": "user-alpha"}


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return {"X-User-Id": "user-alpha", "X-Admin-Key": get_settings().admin_api_key}


@pytest.fixture()
async def seeded_core(db_session: AsyncSession) -> dict[str, str]:
    season_id = str(uuid4())
    event_id = str(uuid4())
    session_id = str(uuid4())
    rule_id = str(uuid4())
    rule_two_id = str(uuid4())
    question_one_id = str(uuid4())
    question_two_id = str(uuid4())

    season = Season(id=season_id, year=2026, is_current=True)
    db_session.add(season)

    start = now_utc() + timedelta(days=1)
    event = Event(
        id=event_id,
        season_id=season.id,
        name="Australian GP",
        slug=f"2026-australian-gp-{event_id[:6]}",
        country="Australia",
        start_at=start,
        end_at=start + timedelta(days=3),
    )
    db_session.add(event)

    session_obj = Session(
        id=session_id,
        event_id=event.id,
        name="Qualifying",
        session_type=SessionType.QUALIFYING,
        state=SessionState.OPEN,
        starts_at=start,
        lock_at=start + timedelta(minutes=10),
        ends_at=start + timedelta(hours=1),
    )
    db_session.add(session_obj)

    rule = ScoringRule(
        id=rule_id,
        name=f"Pole Base {rule_id[:6]}",
        question_type=QuestionType.POLE,
        base_points=20,
    )
    db_session.add(rule)

    question = QuestionInstance(
        id=question_one_id,
        session_id=session_obj.id,
        question_type=QuestionType.POLE,
        prompt="Who takes pole?",
        options=["VER", "NOR", "LEC"],
        lock_at=session_obj.lock_at,
        scoring_rule_id=rule.id,
        correct_option="VER",
    )
    db_session.add(question)

    rule_two = ScoringRule(
        id=rule_two_id,
        name=f"Winner Base {rule_two_id[:6]}",
        question_type=QuestionType.WINNER,
        base_points=25,
    )
    db_session.add(rule_two)
    question_two = QuestionInstance(
        id=question_two_id,
        session_id=session_obj.id,
        question_type=QuestionType.WINNER,
        prompt="Who wins race?",
        options=["VER", "NOR", "LEC"],
        lock_at=session_obj.lock_at,
        scoring_rule_id=rule_two.id,
        correct_option="NOR",
    )
    db_session.add(question_two)

    await db_session.commit()
    return {
        "season_id": season.id,
        "event_id": event.id,
        "session_id": session_obj.id,
        "question_one": question.id,
        "question_two": question_two.id,
    }
