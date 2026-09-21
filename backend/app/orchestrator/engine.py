from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from app import audit
from app.orchestrator import store
from app.orchestrator.base import StageContext, StageFailed, StageResult
from app.orchestrator.stages.ingest import IngestStage
from app.orchestrator.stages.plan import PlanStage
from app.orchestrator.state import (
    STAGE_ORDER,
    Artifact,
    AuditRow,
    Run,
    RunStatus,
    Stage,
    StageKind,
    StageStatus,
)

log = logging.getLogger(__name__)

APPROVAL_GATES: set[StageKind] = {StageKind.PLAN}

REGISTRY: dict[StageKind, object] = {
    StageKind.INGEST: IngestStage(),
    StageKind.PLAN: PlanStage(),
}


def _now() -> datetime:
    return datetime.now(UTC)


async def create_run(
    *,
    title: str = "Untitled project",
    slack_channel_id: str | None = None,
    slack_thread_ts: str | None = None,
    started_by: str | None = None,
) -> Run:
    run = Run(
        title=title,
        status=RunStatus.PENDING,
        slack_channel_id=slack_channel_id,
        slack_thread_ts=slack_thread_ts,
        started_by=started_by,
    )
    run.stages = [Stage(kind=kind, position=position) for position, kind in enumerate(STAGE_ORDER)]
    store.add(run)
    log.info("created run %s (%s)", run.id, title)
    return run


async def load_run(run_id: uuid.UUID) -> Run | None:
    return store.get(run_id)


def next_stage(run: Run) -> Stage | None:
    for stage in sorted(run.stages, key=lambda s: s.position):
        if stage.status in (StageStatus.COMPLETE, StageStatus.SKIPPED):
            continue
        return stage
    return None


StageObserver = Callable[[Run, Stage], Awaitable[None]]


async def advance(
    run_id: uuid.UUID,
    *,
    feedback: str | None = None,
    on_stage: StageObserver | None = None,
) -> Run:
    run = store.get(run_id)
    if run is None:
        raise ValueError(f"no such run: {run_id}")

    while True:
        stage = next_stage(run)

        if stage is None:
            run.status = RunStatus.COMPLETE
            run.current_stage = None
            run.updated_at = _now()
            log.info("run %s complete", run.id)
            return run

        if stage.status == StageStatus.AWAITING_APPROVAL:
            log.info("run %s waiting on approval for %s", run.id, stage.kind)
            return run

        implementation = REGISTRY.get(stage.kind)
        if implementation is None:
            log.info("run %s reached unimplemented stage %s; stopping", run.id, stage.kind)
            run.status = RunStatus.RUNNING
            run.current_stage = stage.kind
            run.updated_at = _now()
            return run

        ok = await _run_stage(run, stage, implementation, feedback)
        feedback = None

        if on_stage is not None:
            try:
                await on_stage(run, stage)
            except Exception:
                log.exception("stage observer raised for %s on run %s", stage.kind, run.id)

        if not ok:
            return run
        if stage.status == StageStatus.AWAITING_APPROVAL:
            return run


async def _run_stage(run: Run, stage: Stage, implementation, feedback: str | None) -> bool:
    stage.status = StageStatus.RUNNING
    stage.attempt += 1
    stage.started_at = _now()
    stage.error = None
    run.status = RunStatus.RUNNING
    run.current_stage = stage.kind
    run.updated_at = _now()

    log.info("run %s stage %s starting (attempt %d)", run.id, stage.kind, stage.attempt)

    with audit.collecting() as calls:
        try:
            result: StageResult = await implementation.run(StageContext(run=run, feedback=feedback))
        except StageFailed as exc:
            return _fail(run, stage, str(exc), calls)
        except Exception as exc:
            log.exception("run %s stage %s raised", run.id, stage.kind)
            return _fail(run, stage, f"{type(exc).__name__}: {exc}", calls)

    _record_audit(run, stage, calls)

    for produced in result.artifacts:
        existing = [a for a in run.artifacts if a.kind == produced.kind and a.name == produced.name]
        run.artifacts.append(
            Artifact(
                kind=produced.kind,
                name=produced.name,
                version=max((a.version for a in existing), default=0) + 1,
                data=produced.data,
                text=produced.text,
            )
        )

    for field, value in result.run_updates.items():
        setattr(run, field, value)

    stage.input_tokens += result.input_tokens
    stage.output_tokens += result.output_tokens
    stage.completed_at = _now()

    gated = result.needs_approval or stage.kind in APPROVAL_GATES
    stage.status = StageStatus.AWAITING_APPROVAL if gated else StageStatus.COMPLETE
    run.status = RunStatus.AWAITING_APPROVAL if gated else RunStatus.RUNNING
    run.updated_at = _now()

    log.info(
        "run %s stage %s %s in %.1fs (%d/%d tokens)",
        run.id,
        stage.kind,
        stage.status,
        stage.duration_seconds or 0,
        result.input_tokens,
        result.output_tokens,
    )
    return True


def _record_audit(run: Run, stage: Stage, calls: audit.Collector) -> None:
    for entry in calls.entries:
        run.audit.append(
            AuditRow(
                kind=entry.kind,
                target=entry.target,
                ok=entry.ok,
                duration_ms=entry.duration_ms,
                input_tokens=entry.input_tokens,
                output_tokens=entry.output_tokens,
                detail=entry.detail,
                error=entry.error,
            )
        )


def _fail(run: Run, stage: Stage, message: str, calls: audit.Collector) -> bool:
    _record_audit(run, stage, calls)
    stage.input_tokens += calls.input_tokens
    stage.output_tokens += calls.output_tokens
    stage.status = StageStatus.FAILED
    stage.completed_at = _now()
    stage.error = message
    run.status = RunStatus.FAILED
    run.error = f"{stage.kind}: {message}"
    run.updated_at = _now()
    log.error("run %s stage %s failed: %s", run.id, stage.kind, message)
    return False


async def mark_stage_approved(run_id: uuid.UUID, stage_kind: StageKind) -> Run:
    run = store.get(run_id)
    if run is None:
        raise ValueError(f"no such run: {run_id}")

    stage = next((s for s in run.stages if s.kind == stage_kind), None)
    if stage is None or stage.status != StageStatus.AWAITING_APPROVAL:
        raise ValueError(f"{stage_kind} is not awaiting approval on run {run_id}")

    stage.status = StageStatus.COMPLETE
    return run


async def approve(
    run_id: uuid.UUID,
    stage_kind: StageKind,
    *,
    on_stage: StageObserver | None = None,
) -> Run:
    await mark_stage_approved(run_id, stage_kind)
    return await advance(run_id, on_stage=on_stage)


async def request_changes(
    run_id: uuid.UUID,
    stage_kind: StageKind,
    feedback: str,
    *,
    on_stage: StageObserver | None = None,
) -> Run:
    run = store.get(run_id)
    if run is None:
        raise ValueError(f"no such run: {run_id}")

    stage = next((s for s in run.stages if s.kind == stage_kind), None)
    if stage is None:
        raise ValueError(f"{stage_kind} is not a stage of run {run_id}")

    stage.status = StageStatus.PENDING
    return await advance(run_id, feedback=feedback, on_stage=on_stage)


async def rerun_stage(
    run_id: uuid.UUID,
    stage_kind: StageKind,
    *,
    feedback: str | None = None,
    on_stage: StageObserver | None = None,
) -> Run:
    run = store.get(run_id)
    if run is None:
        raise ValueError(f"no such run: {run_id}")

    target = next((s for s in run.stages if s.kind == stage_kind), None)
    if target is None:
        raise ValueError(f"{stage_kind} is not a stage of run {run_id}")

    for stage in run.stages:
        if stage.position >= target.position:
            stage.status = StageStatus.PENDING
            stage.error = None
            stage.started_at = None
            stage.completed_at = None

    run.error = None
    run.status = RunStatus.PENDING
    return await advance(run_id, feedback=feedback, on_stage=on_stage)
