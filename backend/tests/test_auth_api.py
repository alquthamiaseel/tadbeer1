"""The login endpoint.

Exercised against a real (SQLite) database, since what matters here is the
actual round trip: a stored hash, a request with a password, a token back.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_session
from app.main import app
from app.models import User
from app.security import hash_password, verify_token


@pytest.fixture
async def api(tmp_path):
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/auth.db")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(async_engine, expire_on_commit=False)

    async def _get_session():
        async with maker() as session:
            yield session

    async with maker() as session:
        session.add(User(username="alice", password_hash=hash_password("s3cret-password")))
        await session.commit()

    app.dependency_overrides[get_session] = _get_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await async_engine.dispose()


async def test_the_right_password_returns_a_working_token(api):
    response = await api.post(
        "/api/auth/login", json={"username": "alice", "password": "s3cret-password"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert verify_token(body["token"]) is not None


async def test_the_wrong_password_is_rejected(api):
    response = await api.post(
        "/api/auth/login", json={"username": "alice", "password": "wrong"}
    )
    assert response.status_code == 401


async def test_an_unknown_username_is_rejected_the_same_way(api):
    """A wrong username must not leak that the account doesn't exist."""
    response = await api.post(
        "/api/auth/login", json={"username": "nobody", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Wrong username or password"
