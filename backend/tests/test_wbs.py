"""Dependency and Asana-payload checks for the WBS stage."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.config import settings
from app.integrations.asana import AsanaClient
from app.llm.client import LLMResult
from app.models import Artifact, ArtifactKind, StageKind, StageStatus
from app.orchestrator import engine
from app.orchestrator.base import StageContext, StageFailed
from app.orchestrator.stages.wbs import WbsStage
from app.schemas.wbs import WbsTask, WorkBreakdownStructure


def task(task_id: str, depends_on: list[str] | None = None) -> WbsTask:
    return WbsTask(
        id=task_id,
        phase="Build",
        name=task_id,
        description="Complete the task",
        owner_role="Developer",
        estimate_days=2,
        depends_on=depends_on or [],
        constraints=[],
    )


def test_dependencies_must_point_backwards_to_existing_tasks():
    WbsStage._validate_dependencies(
        WorkBreakdownStructure(project_summary="x", tasks=[task("a"), task("b", ["a"])])
    )

    with pytest.raises(StageFailed, match="forward or unknown"):
        WbsStage._validate_dependencies(
            WorkBreakdownStructure(project_summary="x", tasks=[task("a", ["b"])])
        )


def test_duplicate_ids_are_rejected_before_asana_is_called():
    with pytest.raises(StageFailed, match="duplicate"):
        WbsStage._validate_dependencies(
            WorkBreakdownStructure(project_summary="x", tasks=[task("a"), task("a")])
        )


def test_asana_payload_carries_section_due_date_and_delivery_context():
    item = task("build-01")
    item.due_offset_days = 4
    item.constraints = ["Use Slack Socket Mode"]
    payload = AsanaClient._task_payload(item, "P1", "S1", __import__("datetime").date(2026, 1, 1))

    assert payload["memberships"] == [{"project": "P1", "section": "S1"}]
    assert payload["due_on"] == "2026-01-05"
    assert "Slack Socket Mode" in payload["notes"]


def test_missing_asana_credentials_have_an_actionable_error():
    with pytest.raises(StageFailed, match="ASANA_ACCESS_TOKEN"):
        AsanaClient(token="", workspace_gid="")._headers()


@respx.mock
async def test_a_free_tier_workspace_is_diagnosed_rather_than_reported_as_a_402():
    """Dependencies need Premium. By then the project and tasks already exist."""
    respx.post("https://app.asana.com/api/1.0/projects").mock(
        return_value=httpx.Response(201, json={"data": {"gid": "P1"}})
    )
    respx.post(url__regex=r".*/projects/P1/sections").mock(
        return_value=httpx.Response(201, json={"data": {"gid": "S1"}})
    )
    respx.post("https://app.asana.com/api/1.0/tasks").mock(
        side_effect=[
            httpx.Response(201, json={"data": {"gid": "T1"}}),
            httpx.Response(201, json={"data": {"gid": "T2"}}),
        ]
    )
    respx.post(url__regex=r".*/tasks/T2/addDependencies").mock(
        return_value=httpx.Response(402, json={"errors": [{"message": "payment required"}]})
    )

    wbs = WorkBreakdownStructure(project_summary="x", tasks=[task("a"), task("b", ["a"])])
    with pytest.raises(StageFailed) as caught:
        await AsanaClient(token="t", workspace_gid="W1").publish("Campus", wbs)

    message = str(caught.value)
    assert "Premium" in message, "name the actual cause"
    assert "app.asana.com/0/P1/list" in message, "the tasks that were created still exist"
    assert caught.value.retryable is False


# --- running without Asana --------------------------------------------------


def _fake_llm(monkeypatch, wbs: WorkBreakdownStructure):
    async def _generate(**kwargs):
        return LLMResult(
            data=wbs,
            raw_text="{}",
            model="fake",
            input_tokens=300,
            output_tokens=800,
            thought_tokens=0,
            duration_ms=1,
        )

    monkeypatch.setattr("app.orchestrator.stages.wbs.generate_structured", _generate)


async def _ready_run(session):
    run = await engine.create_run(session, title="Campus Event Booking")
    for kind, artifact_kind, data in (
        (StageKind.INGEST, ArtifactKind.REQUIREMENTS, {"project_name": "Campus"}),
        (StageKind.PLAN, ArtifactKind.PLAN, {"executive_summary": "Book seats"}),
    ):
        stage = next(s for s in run.stages if s.kind == kind)
        stage.status = StageStatus.COMPLETE
        session.add(
            Artifact(
                run_id=run.id,
                stage_id=stage.id,
                kind=artifact_kind,
                name=artifact_kind.value,
                version=1,
                data=data,
            )
        )
    await session.commit()
    return await engine.load_run(session, run.id)


async def test_the_work_breakdown_survives_asana_being_turned_off(session, monkeypatch):
    """The task graph is the artifact; Asana is only where it gets shown."""
    monkeypatch.setattr(settings, "asana_enabled", False)
    _fake_llm(
        monkeypatch,
        WorkBreakdownStructure(project_summary="Build it", tasks=[task("a"), task("b", ["a"])]),
    )
    run = await _ready_run(session)

    result = await WbsStage().run(StageContext(run=run, session=session))

    stored = result.artifacts[0]
    assert stored.kind == ArtifactKind.WBS
    assert len(stored.data["tasks"]) == 2
    assert stored.data["tasks"][1]["depends_on"] == ["a"], "dependencies survive too"
    assert result.run_updates == {}, "no Asana URL to record"
    assert "turned off" in result.summary, "the skip must be visible, not silent"


async def test_asana_is_not_called_at_all_when_disabled(session, monkeypatch):
    monkeypatch.setattr(settings, "asana_enabled", False)
    _fake_llm(monkeypatch, WorkBreakdownStructure(project_summary="x", tasks=[task("a")]))

    async def _explode(self, *args, **kwargs):
        raise AssertionError("Asana must not be contacted when publishing is off")

    monkeypatch.setattr(AsanaClient, "publish", _explode)
    run = await _ready_run(session)

    await WbsStage().run(StageContext(run=run, session=session))


async def test_a_missing_token_still_fails_when_publishing_is_on(session, monkeypatch):
    """Skipping must be a decision, never an accident of configuration."""
    monkeypatch.setattr(settings, "asana_enabled", True)
    monkeypatch.setattr(settings, "asana_access_token", "")
    monkeypatch.setattr(settings, "asana_workspace_gid", "")
    _fake_llm(monkeypatch, WorkBreakdownStructure(project_summary="x", tasks=[task("a")]))
    run = await _ready_run(session)

    with pytest.raises(StageFailed, match="ASANA_ACCESS_TOKEN"):
        await WbsStage().run(StageContext(run=run, session=session))
