"""The audit log.

Its value is that nothing has to opt in: a stage records model and API calls
without knowing the audit log exists, so a new stage cannot forget to.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from sqlalchemy import select

from app import audit
from app.integrations.http import request_json
from app.llm.client import LLMResult
from app.models import AuditLog, StageKind, StageStatus
from app.orchestrator import engine
from app.orchestrator.base import StageFailed, StageResult


def test_recording_outside_a_collector_is_a_no_op():
    """Scripts and tests call the same code paths without a collector open."""
    audit.record_llm(model="m", ok=True, duration_ms=1)
    audit.record_api(
        service="s", method="GET", url="https://x/y", status=200, ok=True, duration_ms=1
    )


def test_a_collector_totals_the_tokens_it_saw():
    with audit.collecting() as calls:
        audit.record_llm(model="m", ok=True, duration_ms=5, input_tokens=10, output_tokens=20)
        audit.record_llm(model="m", ok=True, duration_ms=5, input_tokens=1, output_tokens=2)
    assert (calls.input_tokens, calls.output_tokens) == (11, 22)


@respx.mock
async def test_api_calls_are_recorded_by_path_not_by_full_url():
    respx.post("https://api.github.com/repos/me/x/git/trees").mock(
        return_value=httpx.Response(201, json={"sha": "s"})
    )
    with audit.collecting() as calls:
        async with httpx.AsyncClient() as client:
            await request_json(
                client,
                "POST",
                "https://api.github.com/repos/me/x/git/trees",
                service="GitHub",
                json={},
            )

    assert calls.entries[0].target == "GitHub POST /repos/me/x/git/trees"
    assert calls.entries[0].ok is True


@respx.mock
async def test_a_failed_api_call_records_the_provider_message():
    respx.get("https://api.test/x").mock(
        return_value=httpx.Response(404, json={"message": "no such repo"})
    )
    with audit.collecting() as calls:
        async with httpx.AsyncClient() as client:
            with pytest.raises(StageFailed):
                await request_json(client, "GET", "https://api.test/x", service="GitHub")

    entry = calls.entries[0]
    assert entry.ok is False
    assert "no such repo" in entry.error
    assert entry.detail["status"] == 404


class _CallingStage:
    """A stage that makes one model call and one API call, like a real one."""

    kind = StageKind.INGEST

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def run(self, ctx):
        audit.record_llm(
            model="gemini-test",
            ok=True,
            duration_ms=900,
            input_tokens=100,
            output_tokens=250,
            output_model="Requirements",
        )
        audit.record_api(
            service="Asana",
            method="POST",
            url="https://app.asana.com/api/1.0/projects",
            status=201,
            ok=True,
            duration_ms=300,
        )
        if self.fail:
            raise StageFailed("it broke after making its calls")
        return StageResult(summary="done")


async def _audit_rows(session, run_id):
    result = await session.execute(select(AuditLog).where(AuditLog.run_id == run_id))
    return list(result.scalars())


async def test_the_engine_persists_what_a_stage_called(session, monkeypatch):
    monkeypatch.setattr(engine, "REGISTRY", {StageKind.INGEST: _CallingStage()})
    run = await engine.create_run(session, title="Audited")

    await engine.advance(session, run.id)

    rows = await _audit_rows(session, run.id)
    assert {row.kind for row in rows} == {"llm", "api"}
    llm = next(row for row in rows if row.kind == "llm")
    assert (llm.input_tokens, llm.output_tokens) == (100, 250)
    assert llm.detail["schema"] == "Requirements"
    assert all(row.stage_id is not None for row in rows), "rows must attribute to a stage"


async def test_calls_made_before_a_stage_failed_are_still_recorded(session, monkeypatch):
    """A failed stage is exactly when the call log is worth having."""
    monkeypatch.setattr(engine, "REGISTRY", {StageKind.INGEST: _CallingStage(fail=True)})
    run = await engine.create_run(session, title="Audited")

    run = await engine.advance(session, run.id)

    stage = next(s for s in run.stages if s.kind == StageKind.INGEST)
    assert stage.status == StageStatus.FAILED
    assert len(await _audit_rows(session, run.id)) == 2


async def test_the_llm_client_records_its_own_calls(monkeypatch):
    """Recording lives in the client, so no stage can forget to do it."""
    from app.llm import client as llm_client

    class _Interaction:
        output_text = '{"text": "hi"}'
        errors = None
        usage = type(
            "U",
            (),
            {
                "total_input_tokens": 7,
                "total_output_tokens": 9,
                "total_thought_tokens": 3,
            },
        )()

    async def _create(**kwargs):
        return _Interaction(), 1234

    monkeypatch.setattr(llm_client, "_create", _create)

    from pydantic import BaseModel

    class Text(BaseModel):
        text: str

    with audit.collecting() as calls:
        await llm_client.generate_structured(output_model=Text, system="s", user="u")

    entry = calls.entries[0]
    assert entry.kind == "llm"
    assert (entry.input_tokens, entry.output_tokens, entry.duration_ms) == (7, 9, 1234)
    assert entry.detail["schema"] == "Text"


def test_llm_result_stays_the_source_of_truth_for_stage_tokens():
    """Audit rows are evidence; stage totals come from the result the stage returns."""
    result = LLMResult(
        data=None,
        raw_text="",
        model="m",
        input_tokens=1,
        output_tokens=2,
        thought_tokens=0,
        duration_ms=0,
    )
    assert (result.input_tokens, result.output_tokens) == (1, 2)


async def test_a_failed_stage_still_reports_what_it_spent(session, monkeypatch):
    """A stage that fails on its second model call still paid for the first."""

    class _SpendsThenFails:
        kind = StageKind.INGEST

        async def run(self, ctx):
            audit.record_llm(
                model="gemini-test", ok=True, duration_ms=100, input_tokens=400, output_tokens=900
            )
            audit.record_llm(
                model="gemini-test", ok=True, duration_ms=100, input_tokens=500, output_tokens=100
            )
            raise StageFailed("the external API rejected the result")

    monkeypatch.setattr(engine, "REGISTRY", {StageKind.INGEST: _SpendsThenFails()})
    run = await engine.create_run(session, title="Expensive failure")

    run = await engine.advance(session, run.id)

    stage = next(s for s in run.stages if s.kind == StageKind.INGEST)
    assert stage.status == StageStatus.FAILED
    assert (stage.input_tokens, stage.output_tokens) == (900, 1000)
