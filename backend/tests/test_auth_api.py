from __future__ import annotations

import json

import httpx
import pytest

from app import users_store
from app.config import settings
from app.main import app
from app.security import hash_password, verify_token


@pytest.fixture
async def api(tmp_path, monkeypatch):
    path = tmp_path / "users.json"
    monkeypatch.setattr(settings, "users_file", str(path))
    users_store.upsert_user("alice", hash_password("s3cret-password"))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_the_right_password_returns_a_working_token(api):
    response = await api.post(
        "/api/auth/login", json={"username": "alice", "password": "s3cret-password"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert verify_token(body["token"]) is not None


async def test_the_wrong_password_is_rejected(api):
    response = await api.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert response.status_code == 401


async def test_an_unknown_username_is_rejected_the_same_way(api):
    response = await api.post(
        "/api/auth/login", json={"username": "nobody", "password": "whatever"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Wrong username or password"


async def test_login_works_when_the_users_file_does_not_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "users_file", str(tmp_path / "missing.json"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/login", json={"username": "a", "password": "b"})
    assert response.status_code == 401


def test_passwords_are_stored_hashed_and_users_are_unique(tmp_path, monkeypatch):
    path = tmp_path / "users.json"
    monkeypatch.setattr(settings, "users_file", str(path))

    assert users_store.upsert_user("bob", hash_password("first-password")) is True
    assert users_store.upsert_user("bob", hash_password("second-password")) is False

    text = path.read_text(encoding="utf-8")
    records = json.loads(text)
    assert len(records) == 1
    assert "second-password" not in text
    assert "$" in records[0]["password_hash"]
