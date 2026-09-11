"""PLAN stage contract: requirements in, reviewable plan artifact out."""

from __future__ import annotations

import pytest

from app.llm.client import LLMResult
from app.models import Artifact, ArtifactKind, RunStatus, StageKind, StageStatus
from app.orchestrator import engine
from app.orchestrator.base import StageContext
from app.orchestrator.stages.plan import PlanStage
from app.schemas.plan import Milestone, PlanPhase, ProjectPlan, Risk

PLAN = ProjectPlan(
    executive_summary=(
        "A student event platform that lets attendees reserve places and organisers run events."
    ),
    in_scope=["Browse events", "Reserve a seat", "Manage event capacity"],
    out_of_scope=["Payments"],
    phases=[
        PlanPhase(
            name="Discovery",
            objective="Confirm event and booking rules",
            deliverables=["Validated requirements"],
            estimated_duration_days=3,
        ),
        PlanPhase(
            name="Delivery",
            objective="Build and test the MVP",
            deliverables=["Working web application"],
            estimated_duration_days=10,
        ),
    ],
    milestones=[
        Milestone(
            name="Requirements approved",
            success_criteria="Stakeholders approve the scope",
            target_phase="Discovery",
        )
    ],
    risks=[
        Risk(
            title="Late scope changes",
            likelihood="medium",
            impact="high",
            mitigation="Use an approval gate before implementation",
        )
    ],
    assumptions=["Students sign in with university accounts"],
    open_questions=["What is the maximum capacity per event?"],
    estimated_total_days=13,
)


@pytest.fixture
def fake_llm(monkeypatch):
    captured = {}

    async def _generate(*, output_model, system, user, **kwargs):
        captured.update(output_model=output_model, system=system, user=user)
        return LLMResult(
            data=PLAN,
            raw_text="{}",
            model="fake",
            input_tokens=120,
            output_tokens=300,
            thought_tokens=0,
            duration_ms=5,
        )

    monkeypatch.setattr("app.orchestrator.stages.plan.generate_structured", _generate)
    return captured


async def _ready_run(session):
    run = await engine.create_run(session, title="Campus Event Booking")
    ingest = next(stage for stage in run.stages if stage.kind == StageKind.INGEST)
    ingest.status = StageStatus.COMPLETE
    session.add(
        Artifact(
            run_id=run.id,
            stage_id=ingest.id,
            kind=ArtifactKind.REQUIREMENTS,
            name="Requirements",
            version=1,
            data={"project_name": "Campus Event Booking", "features": [{"title": "Reserve seat"}]},
        )
    )
    await session.commit()
    loaded = await engine.load_run(session, run.id)
    assert loaded is not None
    return loaded


async def test_plan_uses_the_requirements_artifact(session, fake_llm):
    run = await _ready_run(session)

    result = await PlanStage().run(StageContext(run=run, session=session))

    assert result.artifacts[0].kind == ArtifactKind.PLAN
    assert result.artifacts[0].data["estimated_total_days"] == 13
    assert result.needs_approval is True
    assert "Campus Event Booking" in fake_llm["user"]
    assert "2 phases" in result.summary


async def test_feedback_is_given_to_the_revision(session, fake_llm):
    run = await _ready_run(session)

    await PlanStage().run(
        StageContext(run=run, session=session, feedback="Include a pilot before delivery")
    )

    assert "Include a pilot before delivery" in fake_llm["user"]
    assert "rejected the previous plan" in fake_llm["user"]


async def test_engine_stores_plan_and_waits_for_human_approval(session, fake_llm, monkeypatch):
    run = await _ready_run(session)
    monkeypatch.setattr(engine, "REGISTRY", {StageKind.PLAN: PlanStage()})

    run = await engine.advance(session, run.id)

    plan = next(stage for stage in run.stages if stage.kind == StageKind.PLAN)
    assert plan.status == StageStatus.AWAITING_APPROVAL
    assert run.status == RunStatus.AWAITING_APPROVAL
    assert any(artifact.kind == ArtifactKind.PLAN for artifact in run.artifacts)
