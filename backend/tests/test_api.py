from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.config import settings
from app.main import app
from app.orchestrator import engine
from app.orchestrator.state import Artifact, ArtifactKind, AuditRow, Run, RunStatus, StageStatus
from app.security import create_token


@pytest.fixture
async def api():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _make_run(*, title="Campus Event Booking") -> Run:
    run = await engine.create_run(title=title)
    run.artifacts.append(
        Artifact(
            kind=ArtifactKind.REQUIREMENTS,
            name="Requirements",
            version=1,
            data={"project_name": title},
        )
    )
    run.audit.append(
        AuditRow(
            kind="llm",
            target="gpt-4o-mini",
            ok=True,
            duration_ms=9900,
            input_tokens=185,
            output_tokens=346,
            detail={"schema": "Requirements"},
        )
    )
    return run


async def test_a_new_run_lists_with_both_phase_1_stages_pending(api):
    run = await _make_run()

    listed = (await api.get("/api/runs")).json()
    assert [r["title"] for r in listed] == ["Campus Event Booking"]

    detail = (await api.get(f"/api/runs/{run.id}")).json()
    assert [stage["kind"] for stage in detail["stages"]] == ["INGEST", "PLAN"]
    assert all(stage["status"] == "PENDING" for stage in detail["stages"])
    assert detail["artifacts"][0]["data"]["project_name"] == "Campus Event Booking"


async def test_a_missing_run_is_404_not_a_500(api):
    response = await api.get("/api/runs/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404


async def test_the_audit_endpoint_returns_the_evidence_trail(api):
    run = await _make_run()

    rows = (await api.get(f"/api/runs/{run.id}/audit")).json()

    assert len(rows) == 1
    assert rows[0]["target"] == "gpt-4o-mini"
    assert rows[0]["input_tokens"] == 185


async def test_rerun_returns_immediately_and_works_in_the_background(api, monkeypatch):
    run = await _make_run()
    started = asyncio.Event()
    seen: dict = {}

    async def _rerun_stage(rid, kind, *, feedback=None):
        seen.update(run_id=rid, kind=kind, feedback=feedback)
        started.set()
        return await engine.load_run(rid)

    monkeypatch.setattr(engine, "rerun_stage", _rerun_stage)

    response = await api.post(
        f"/api/runs/{run.id}/rerun", json={"stage": "PLAN", "feedback": "add a pilot phase"}
    )

    assert response.status_code == 200, response.text
    await asyncio.wait_for(started.wait(), timeout=2)
    assert seen == {"run_id": run.id, "kind": "PLAN", "feedback": "add a pilot phase"}


async def test_rerunning_a_stage_the_run_does_not_have_is_rejected(api):
    run = await _make_run()
    response = await api.post(f"/api/runs/{run.id}/rerun", json={"stage": "NOPE"})
    assert response.status_code == 422


async def test_the_event_stream_sends_state_then_ends_on_a_terminal_run(api):
    run = await _make_run()
    run.status = RunStatus.COMPLETE
    for stage in run.stages:
        stage.status = StageStatus.COMPLETE

    body = ""
    async with api.stream("GET", f"/api/runs/{run.id}/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        async for chunk in response.aiter_text():
            body += chunk
            if "event: end" in body:
                break

    first = json.loads(body.split("data: ", 1)[1].split("\n\n", 1)[0])
    assert first["status"] == "COMPLETE"
    assert len(first["stages"]) == 2
    assert "event: end" in body


async def test_the_stream_emits_a_frame_when_a_stage_changes(monkeypatch):
    from app.api import routes

    monkeypatch.setattr(routes, "POLL_SECONDS", 0.02)
    run = await _make_run()

    response = await routes.stream_events(run.id)
    stream = response.body_iterator.__aiter__()

    first = json.loads((await anext(stream)).split("data: ", 1)[1])
    assert first["stages"][0]["status"] == "PENDING"

    next(s for s in run.stages if s.kind.value == "INGEST").status = StageStatus.RUNNING
    run.status = RunStatus.RUNNING

    second = json.loads((await asyncio.wait_for(anext(stream), timeout=5)).split("data: ", 1)[1])
    assert second["stages"][0]["status"] == "RUNNING"
    assert second["status"] == "RUNNING"
    await response.body_iterator.aclose()


async def test_the_api_is_open_when_auth_is_off(api):
    assert (await api.get("/api/runs")).status_code == 200


async def test_auth_rejects_a_missing_or_invalid_token(api, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_auth", True)
    monkeypatch.setattr(settings, "session_secret", "a-real-secret")

    assert (await api.get("/api/runs")).status_code == 401
    assert (
        await api.get("/api/runs", headers={"Authorization": "Bearer garbage"})
    ).status_code == 401

    import uuid

    token = create_token(uuid.uuid4(), "alice")
    assert (
        await api.get("/api/runs", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200


async def test_auth_on_with_the_default_secret_fails_loudly(api, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_auth", True)
    monkeypatch.setattr(settings, "session_secret", "changeme-session-secret")

    response = await api.get("/api/runs", headers={"Authorization": "Bearer whatever"})
    assert response.status_code == 500
    assert "SESSION_SECRET" in response.json()["detail"]


async def test_health_needs_no_token(api, monkeypatch):
    monkeypatch.setattr(settings, "dashboard_auth", True)
    monkeypatch.setattr(settings, "session_secret", "a-real-secret")
    assert (await api.get("/health")).status_code == 200
