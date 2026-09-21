from __future__ import annotations

from app import audit
from app.llm.client import LLMResult
from app.orchestrator import engine
from app.orchestrator.base import StageFailed, StageResult
from app.orchestrator.state import StageKind, StageStatus


def test_recording_outside_a_collector_is_a_no_op():
    audit.record_llm(model="m", ok=True, duration_ms=1)
    audit.record_api(
        service="s", method="GET", url="https://x/y", status=200, ok=True, duration_ms=1
    )


def test_a_collector_totals_the_tokens_it_saw():
    with audit.collecting() as calls:
        audit.record_llm(model="m", ok=True, duration_ms=5, input_tokens=10, output_tokens=20)
        audit.record_llm(model="m", ok=True, duration_ms=5, input_tokens=1, output_tokens=2)
    assert (calls.input_tokens, calls.output_tokens) == (11, 22)


def test_record_api_derives_its_target_from_the_url_path():
    with audit.collecting() as calls:
        audit.record_api(
            service="ExampleAPI",
            method="POST",
            url="https://api.example.com/v1/things",
            status=201,
            ok=True,
            duration_ms=1,
        )

    assert calls.entries[0].target == "ExampleAPI POST /v1/things"
    assert calls.entries[0].ok is True


class _CallingStage:
    kind = StageKind.INGEST

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def run(self, ctx):
        audit.record_llm(
            model="test-model",
            ok=True,
            duration_ms=900,
            input_tokens=100,
            output_tokens=250,
            output_model="Requirements",
        )
        audit.record_api(
            service="ExampleAPI",
            method="POST",
            url="https://api.example.com/v1/things",
            status=201,
            ok=True,
            duration_ms=300,
        )
        if self.fail:
            raise StageFailed("it broke after making its calls")
        return StageResult(summary="done")


async def test_the_engine_records_what_a_stage_called(monkeypatch):
    monkeypatch.setattr(engine, "REGISTRY", {StageKind.INGEST: _CallingStage()})
    run = await engine.create_run(title="Audited")

    await engine.advance(run.id)

    rows = run.audit
    assert {row.kind for row in rows} == {"llm", "api"}
    llm = next(row for row in rows if row.kind == "llm")
    assert (llm.input_tokens, llm.output_tokens) == (100, 250)
    assert llm.detail["schema"] == "Requirements"


async def test_calls_made_before_a_stage_failed_are_still_recorded(monkeypatch):
    monkeypatch.setattr(engine, "REGISTRY", {StageKind.INGEST: _CallingStage(fail=True)})
    run = await engine.create_run(title="Audited")

    run = await engine.advance(run.id)

    stage = next(s for s in run.stages if s.kind == StageKind.INGEST)
    assert stage.status == StageStatus.FAILED
    assert len(run.audit) == 2


async def test_the_llm_client_records_its_own_calls(monkeypatch):
    from app.llm import client as llm_client

    async def _create(**kwargs):
        return llm_client.Completion(
            text='{"text": "hi"}', input_tokens=7, output_tokens=9, thought_tokens=3
        ), 1234

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


async def test_a_failed_stage_still_reports_what_it_spent(monkeypatch):

    class _SpendsThenFails:
        kind = StageKind.INGEST

        async def run(self, ctx):
            audit.record_llm(
                model="test-model", ok=True, duration_ms=100, input_tokens=400, output_tokens=900
            )
            audit.record_llm(
                model="test-model", ok=True, duration_ms=100, input_tokens=500, output_tokens=100
            )
            raise StageFailed("the external API rejected the result")

    monkeypatch.setattr(engine, "REGISTRY", {StageKind.INGEST: _SpendsThenFails()})
    run = await engine.create_run(title="Expensive failure")

    run = await engine.advance(run.id)

    stage = next(s for s in run.stages if s.kind == StageKind.INGEST)
    assert stage.status == StageStatus.FAILED
    assert (stage.input_tokens, stage.output_tokens) == (900, 1000)
