import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

os.environ.setdefault("MF_ENV", "test")
os.environ.setdefault("MF_LOG_JSON", "false")

import app.core.outbox
import app.modules
from app.core.db import Base, get_session
from app.core.sms import ConsoleSmsSender, get_sms_sender
from app.main import create_app


@pytest.fixture
async def engine(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """A fresh database per test.

    Postgres when MF_TEST_DATABASE_URL is set (CI sets it, so row locks, atomic updates and
    timezones are exercised for real); otherwise a file-backed SQLite database. A file, not
    :memory:, so the app's sessions and the test's own session see the same data.
    """
    url = os.environ.get("MF_TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def session(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as s:
        yield s


@pytest.fixture
def sms() -> ConsoleSmsSender:
    return ConsoleSmsSender()


@pytest.fixture
def app(sessionmaker: async_sessionmaker[AsyncSession], sms: ConsoleSmsSender) -> FastAPI:
    app = create_app()

    async def test_session() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as s:
            try:
                yield s
                await s.commit()
            except Exception:
                await s.rollback()
                raise

    app.dependency_overrides[get_session] = test_session
    app.dependency_overrides[get_sms_sender] = lambda: sms
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
