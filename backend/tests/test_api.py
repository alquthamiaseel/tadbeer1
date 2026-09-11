"""The dashboard's API.

Exercised through a real ASGI client against a real (SQLite) database, because
what these tests are checking is the shape the dashboard consumes — a mocked
session would verify none of it.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import db as db_module
from app.api import routes
from app.config import settings
from app.db import Base
from app.main import app
from app.models import Artifact, ArtifactKind, AuditLog, RunStatus, StageKind, StageStatus
from app.orchestrator import engine


@pytest.fixture
async def api(monkeypatch, tmp_path):
    """The app wired to one database shared by requests and fixtures.

    A file rather than :memory: on purpose. SQLAlchemy pools an in-memory SQLite
    database as a single shared connection, and the streaming tests read from
    the stream while writing from the test — two tasks on one aiosqlite
    connection, which deadlocks.
    """
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/api.db")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(async_engine, expire_on_commit=False)

    async def _get_session():
        async with maker() as session:
            yield session

    monkeypatch.setattr(db_module, "SessionLocal", maker)
    monkeypatch.setattr(routes, "SessionLocal", maker)
    app.dependency_overrides[db_module.get_session] = _get_session

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        client.maker = maker
        yield client

    app.dependency_overrides.clear()
    await async_engine.dispose()


async def _make_run(maker, *, title="Campus Event Booking"):
    async with maker() as session:
        run = await engine.create_run(session, title=title)
        session.add(
            Artifact(
                run_id=run.id,
                kind=ArtifactKind.REQUIREMENTS,
                name="Requirements",
                version=1,
                data={"project_name": title},
            )
        )
        session.add(
            AuditLog(
                run_id=run.id,
                kind="llm",
                target="gemini-3.6-flash",
                ok=True,
                duration_ms=9900,
                input_tokens=185,
                output_tokens=346,
                detail={"schema": "Requirements"},
            )
        )
        await session.commit()
        return run.id


async def test_a_new_run_lists_with_all_six_stages_pending(api):
    run_id = await _make_run(api.maker)

    listed = (await api.get("/api/runs")).json()
    assert [run["title"] for run in listed] == ["Campus Event Booking"]

    detail = (await api.get(f"/api/runs/{run_id}")).json()
    assert [stage["kind"] for stage in detail["stages"]] == [
        "INGEST",
        "PLAN",
        "WBS",
        "DESIGN",
        "PROTOTYPE",
        "DONE",
    ]
    assert all(stage["status"] == "PENDING" for stage in detail["stages"])
    assert detail["artifacts"][0]["data"]["project_name"] == "Campus Event Booking"


async def test_a_missing_run_is_404_not_a_500(api):
    response = await api.get("/api/runs/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404


async def test_the_audit_endpoint_returns_the_evidence_trail(api):
    run_id = await _make_run(api.maker)

    rows = (await api.get(f"/api/runs/{run_id}/audit")).json()

    assert len(rows) == 1
    assert rows[0]["target"] == "gemini-3.6-flash"
    assert rows[0]["input_tokens"] == 185


async def test_rerun_returns_immediately_and_works_in_the_background(api, monkeypatch):
    run_id = await _make_run(api.maker)
    started = asyncio.Event()
    seen: dict = {}

    async def _rerun_stage(session, rid, kind, *, feedback=None):
        seen.update(run_id=rid, kind=kind, feedback=feedback)
        started.set()
        return await engine.load_run(session, rid)

    monkeypatch.setattr(engine, "rerun_stage", _rerun_stage)

    response = await api.post(
        f"/api/runs/{run_id}/rerun", json={"stage": "PLAN", "feedback": "add a pilot phase"}
    )

    assert response.status_code == 200, response.text
    await asyncio.wait_for(started.wait(), timeout=2)
    assert seen == {"run_id": run_id, "kind": StageKind.PLAN, "feedback": "add a pilot phase"}


async def test_rerunning_a_stage_the_run_does_not_have_is_rejected(api):
    run_id = await _make_run(api.maker)
    response = await api.post(f"/api/runs/{run_id}/rerun", json={"stage": "NOPE"})
    assert response.status_code == 422


async def test_the_event_stream_sends_state_then_ends_on_a_terminal_run(api):
    """A finished run must close the stream rather than leave the browser waiting."""
    run_id = await _make_run(api.maker)
    async with api.maker() as session:
        run = await engine.load_run(session, run_id)
        run.status = RunStatus.COMPLETE
        for stage in run.stages:
            stage.status = StageStatus.COMPLETE
        await session.commit()

    body = ""
    async with api.stream("GET", f"/api/runs/{run_id}/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        async for chunk in response.aiter_text():
            body += chunk
            if "event: end" in body:
                break

    first = json.loads(body.split("data: ", 1)[1].split("\n\n", 1)[0])
    assert first["status"] == "COMPLETE"
    assert len(first["stages"]) == 6
    assert "event: end" in body


async def test_the_stream_emits_a_frame_when_a_stage_changes(api, monkeypatch):
    """Driven through the response generator rather than an HTTP client.

    httpx's ASGITransport collects a response before handing it back, so an
    incremental stream is invisible through it — the frames only arrive once the
    generator has finished. The generator is the thing under test here, so it is
    iterated directly.
    """
    monkeypatch.setattr(routes, "POLL_SECONDS", 0.02)
    run_id = await _make_run(api.maker)

    response = await routes.stream_events(run_id)
    stream = response.body_iterator.__aiter__()

    first = json.loads((await anext(stream)).split("data: ", 1)[1])
    assert first["stages"][0]["status"] == "PENDING"

    async with api.maker() as session:
        run = await engine.load_run(session, run_id)
        next(s for s in run.stages if s.kind == StageKind.INGEST).status = StageStatus.RUNNING
        run.status = RunStatus.RUNNING
        await session.commit()

    second = json.loads((await asyncio.wait_for(anext(stream), timeout=5)).split("data: ", 1)[1])
    assert second["stages"][0]["status"] == "RUNNING"
    assert second["status"] == "RUNNING"
    await response.body_iterator.aclose()


# --- optional shared-password auth -----------------------------------------


async def test_the_api_is_open_when_auth_is_off(api):
    assert (await api.get("/api/runs")).status_code == 200


async def test_auth_rejects_a_missing_or_wrong_password(api, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_auth", True)
    monkeypatch.setattr(settings, "dashboard_password", "s3cret")

    assert (await api.get("/api/runs")).status_code == 401
    assert (
        await api.get("/api/runs", headers={"Authorization": "Bearer wrong"})
    ).status_code == 401
    assert (
        await api.get("/api/runs", headers={"Authorization": "Bearer s3cret"})
    ).status_code == 200


async def test_auth_on_with_the_default_password_fails_loudly(api, monkeypatch):
    """Silently accepting "changeme" on a public domain would be the worst outcome."""
    monkeypatch.setattr(settings, "dashboard_auth", True)
    monkeypatch.setattr(settings, "dashboard_password", "changeme")

    response = await api.get("/api/runs", headers={"Authorization": "Bearer changeme"})
    assert response.status_code == 500
    assert "DASHBOARD_PASSWORD" in response.json()["detail"]


async def test_health_needs_no_password(api, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_auth", True)
    monkeypatch.setattr(settings, "dashboard_password", "s3cret")
    assert (await api.get("/health")).status_code == 200
