"""Dependency checks and artifact shape for the WBS stage.

Asana publishing has been removed from this build (see
``app.orchestrator.stages.wbs``); this stage now only produces and validates
the task graph.
"""

from __future__ import annotations

import pytest
from app.schemas.wbs import WbsTask, WorkBreakdownStructure

from app.llm.client import LLMResult
from app.orchestrator import engine
from app.orchestrator.base import StageContext, StageFailed
from app.orchestrator.stages.wbs import WbsStage
from app.orchestrator.state import Artifact, ArtifactKind, StageKind, StageStatus


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


def test_duplicate_ids_are_rejected():
    with pytest.raises(StageFailed, match="duplicate"):
        WbsStage._validate_dependencies(
            WorkBreakdownStructure(project_summary="x", tasks=[task("a"), task("a")])
        )


# --- the stage itself --------------------------------------------------------


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


async def _ready_run():
    run = await engine.create_run(title="Campus Event Booking")
    for kind, artifact_kind, data in (
        (StageKind.INGEST, ArtifactKind.REQUIREMENTS, {"project_name": "Campus"}),
        (StageKind.PLAN, ArtifactKind.PLAN, {"executive_summary": "Book seats"}),
    ):
        stage = next(s for s in run.stages if s.kind == kind)
        stage.status = StageStatus.COMPLETE
        run.artifacts.append(
            Artifact(kind=artifact_kind, name=artifact_kind.value, version=1, data=data)
        )
    return run


async def test_the_stage_produces_the_task_graph_with_its_dependencies(monkeypatch):
    _fake_llm(
        monkeypatch,
        WorkBreakdownStructure(project_summary="Build it", tasks=[task("a"), task("b", ["a"])]),
    )
    run = await _ready_run()

    result = await WbsStage().run(StageContext(run=run))

    stored = result.artifacts[0]
    assert stored.kind == ArtifactKind.WBS
    assert len(stored.data["tasks"]) == 2
    assert stored.data["tasks"][1]["depends_on"] == ["a"], "dependencies survive too"
    assert "2 tasks" in result.summary
