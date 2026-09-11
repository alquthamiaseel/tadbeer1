"""The pipeline engine.

The engine's contract is that run state is always recoverable from the
database. These tests exercise that directly: a stage that fails must leave a
readable error, a re-run must not silently discard the previous artifact, and
resuming must not redo completed work.
"""

from __future__ import annotations

import pytest

from app.models import ArtifactKind, RunStatus, StageKind, StageStatus
from app.orchestrator import engine
from app.orchestrator.base import ProducedArtifact, StageFailed, StageResult


class FakeStage:
    """A stage whose behaviour each test dictates."""

    def __init__(self, kind, *, outcomes=None):
        self.kind = kind
        self.outcomes = list(outcomes or [])
        self.calls = 0
        self.seen_feedback = []

    async def run(self, ctx):
        self.calls += 1
        self.seen_feedback.append(ctx.feedback)
        outcome = self.outcomes.pop(0) if self.outcomes else _ok(self.kind)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _ok(kind, name="Requirements", value="v1"):
    return StageResult(
        artifacts=[
            ProducedArtifact(kind=ArtifactKind.REQUIREMENTS, name=name, data={"value": value})
        ],
        input_tokens=10,
        output_tokens=20,
        summary=f"{kind} done",
    )


@pytest.fixture
def registry(monkeypatch):
    """Install fake stages, keeping the engine under test rather than the stages."""

    def install(**by_kind):
        monkeypatch.setattr(engine, "REGISTRY", dict(by_kind))
        return by_kind

    return install


async def test_creating_a_run_creates_every_stage_pending(session):
    run = await engine.create_run(session, title="Test")

    assert [s.kind for s in sorted(run.stages, key=lambda s: s.position)] == [
        StageKind.INGEST,
        StageKind.PLAN,
        StageKind.WBS,
        StageKind.DESIGN,
        StageKind.PROTOTYPE,
        StageKind.DONE,
    ]
    assert all(s.status == StageStatus.PENDING for s in run.stages)
    assert run.status == RunStatus.PENDING


async def test_runs_stop_at_the_approval_gate(session, registry):
    ingest = FakeStage(StageKind.INGEST)
    plan = FakeStage(StageKind.PLAN)
    wbs = FakeStage(StageKind.WBS)
    registry(INGEST=ingest, PLAN=plan, WBS=wbs)
    monkey_kinds(ingest, plan, wbs)

    run = await engine.create_run(session, title="Test")
    run = await engine.advance(session, run.id)

    assert run.status == RunStatus.AWAITING_APPROVAL
    assert _stage(run, StageKind.PLAN).status == StageStatus.AWAITING_APPROVAL
    # The gate must actually gate: WBS has not been given the chance to run.
    assert wbs.calls == 0


async def test_approval_resumes_from_the_gate_without_redoing_earlier_work(session, registry):
    ingest = FakeStage(StageKind.INGEST)
    plan = FakeStage(StageKind.PLAN)
    registry(INGEST=ingest, PLAN=plan)
    monkey_kinds(ingest, plan)

    run = await engine.create_run(session, title="Test")
    await engine.advance(session, run.id)
    run = await engine.approve(session, run.id, StageKind.PLAN)

    assert _stage(run, StageKind.PLAN).status == StageStatus.COMPLETE
    assert ingest.calls == 1, "approving must not re-run completed stages"


async def test_requesting_changes_reruns_the_stage_with_the_feedback(session, registry):
    plan = FakeStage(StageKind.PLAN)
    registry(PLAN=plan)
    monkey_kinds(plan)

    run = await engine.create_run(session, title="Test")
    # Skip straight to PLAN so this test is about feedback, not ordering.
    _stage(run, StageKind.INGEST).status = StageStatus.SKIPPED
    await session.commit()

    await engine.advance(session, run.id)
    await engine.request_changes(session, run.id, StageKind.PLAN, "Add a rollback plan")

    assert plan.calls == 2
    assert plan.seen_feedback == [None, "Add a rollback plan"]


async def test_rerunning_a_stage_versions_the_artifact_rather_than_replacing_it(session, registry):
    plan = FakeStage(
        StageKind.PLAN,
        outcomes=[_ok(StageKind.PLAN, value="first"), _ok(StageKind.PLAN, value="second")],
    )
    registry(PLAN=plan)
    monkey_kinds(plan)

    run = await engine.create_run(session, title="Test")
    _stage(run, StageKind.INGEST).status = StageStatus.SKIPPED
    await session.commit()

    await engine.advance(session, run.id)
    run = await engine.request_changes(session, run.id, StageKind.PLAN, "again please")

    versions = sorted(a.version for a in run.artifacts)
    assert versions == [1, 2], "history of what changed after feedback must survive"
    assert {a.data["value"] for a in run.artifacts} == {"first", "second"}


async def test_a_failure_is_recorded_where_the_user_can_see_it(session, registry):
    ingest = FakeStage(StageKind.INGEST, outcomes=[StageFailed("conversation too short")])
    registry(INGEST=ingest)
    monkey_kinds(ingest)

    run = await engine.create_run(session, title="Test")
    run = await engine.advance(session, run.id)

    assert run.status == RunStatus.FAILED
    assert "conversation too short" in _stage(run, StageKind.INGEST).error
    assert "conversation too short" in run.error


async def test_an_unexpected_exception_still_lands_in_the_database(session, registry):
    """A crashing stage must fail the run visibly, not just log a traceback."""
    ingest = FakeStage(StageKind.INGEST, outcomes=[ZeroDivisionError("boom")])
    registry(INGEST=ingest)
    monkey_kinds(ingest)

    run = await engine.create_run(session, title="Test")
    run = await engine.advance(session, run.id)

    assert run.status == RunStatus.FAILED
    assert "ZeroDivisionError: boom" in _stage(run, StageKind.INGEST).error


async def test_a_failed_run_resumes_from_the_failed_stage(session, registry):
    ingest = FakeStage(StageKind.INGEST, outcomes=[StageFailed("transient"), _ok("INGEST")])
    registry(INGEST=ingest)
    monkey_kinds(ingest)

    run = await engine.create_run(session, title="Test")
    await engine.advance(session, run.id)
    run = await engine.advance(session, run.id)

    assert _stage(run, StageKind.INGEST).status == StageStatus.COMPLETE
    assert _stage(run, StageKind.INGEST).attempt == 2


async def test_an_unimplemented_stage_stops_the_run_cleanly(session, registry):
    """Stages arrive over the build; reaching a gap is not a failure."""
    ingest = FakeStage(StageKind.INGEST)
    registry(INGEST=ingest)
    monkey_kinds(ingest)

    run = await engine.create_run(session, title="Test")
    run = await engine.advance(session, run.id)

    assert run.status == RunStatus.RUNNING
    assert run.error is None
    assert run.current_stage == StageKind.PLAN


async def test_token_usage_accumulates_across_attempts(session, registry):
    plan = FakeStage(StageKind.PLAN)
    registry(PLAN=plan)
    monkey_kinds(plan)

    run = await engine.create_run(session, title="Test")
    _stage(run, StageKind.INGEST).status = StageStatus.SKIPPED
    await session.commit()

    await engine.advance(session, run.id)
    run = await engine.request_changes(session, run.id, StageKind.PLAN, "redo")

    stage = _stage(run, StageKind.PLAN)
    assert (stage.input_tokens, stage.output_tokens) == (20, 40)


async def test_run_updates_are_applied(session, registry):
    class Titling(FakeStage):
        async def run(self, ctx):
            return StageResult(run_updates={"title": "Campus Booking"}, summary="named it")

    stage = Titling(StageKind.INGEST)
    registry(INGEST=stage)
    monkey_kinds(stage)

    run = await engine.create_run(session, title="Untitled project")
    run = await engine.advance(session, run.id)

    assert run.title == "Campus Booking"


async def test_load_run_sees_artifacts_written_after_an_earlier_load(session):
    """A later stage must read what an earlier one wrote, in the same session.

    Sessions use ``expire_on_commit=False``, so a query that returns an
    already-identity-mapped Run will not refresh its collections unless the
    load asks it to. Without that, PLAN reads an empty ``run.artifacts`` and
    fails claiming INGEST never produced requirements.
    """
    from app.models import Artifact

    run = await engine.create_run(session, title="Campus Booking")
    assert run.artifacts == []

    ingest = _stage(run, StageKind.INGEST)
    session.add(
        Artifact(
            run_id=run.id,
            stage_id=ingest.id,
            kind=ArtifactKind.REQUIREMENTS,
            name="Requirements",
            version=1,
            data={"project_name": "Campus Booking"},
        )
    )
    await session.commit()

    reloaded = await engine.load_run(session, run.id)
    assert [a.kind for a in reloaded.artifacts] == [ArtifactKind.REQUIREMENTS]


# --------------------------------------------------------------------------


def _stage(run, kind):
    return next(s for s in run.stages if s.kind == kind)


def monkey_kinds(*stages):
    """The registry is keyed by StageKind; keep each fake's `kind` consistent."""
    for stage in stages:
        if isinstance(stage.kind, str):
            stage.kind = StageKind(stage.kind)
