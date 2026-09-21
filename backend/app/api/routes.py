from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.auth import require_dashboard_auth
from app.orchestrator import engine, store
from app.orchestrator.state import Artifact, AuditRow, Run, RunStatus, Stage, StageKind

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["runs"], dependencies=[Depends(require_dashboard_auth)])

POLL_SECONDS = 1.0
HEARTBEAT_SECONDS = 15.0

TERMINAL_RUN_STATUSES = {RunStatus.COMPLETE, RunStatus.FAILED, RunStatus.CANCELLED}


class StageOut(BaseModel):
    id: uuid.UUID
    kind: str
    position: int
    status: str
    attempt: int
    error: str | None
    duration_seconds: float | None
    input_tokens: int
    output_tokens: int


class ArtifactOut(BaseModel):
    id: uuid.UUID
    kind: str
    name: str
    version: int
    data: dict | None
    text: str | None
    created_at: str


class AuditOut(BaseModel):
    id: uuid.UUID
    kind: str
    target: str
    ok: bool
    duration_ms: int
    input_tokens: int
    output_tokens: int
    detail: dict | None
    error: str | None
    created_at: str


class RunSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    current_stage: str | None
    created_at: str


class RunDetailOut(RunSummaryOut):
    error: str | None
    slack_channel_id: str | None
    slack_thread_ts: str | None
    stages: list[StageOut]
    artifacts: list[ArtifactOut]


class RerunIn(BaseModel):
    stage: StageKind
    feedback: str | None = None


def _summary(run: Run) -> RunSummaryOut:
    return RunSummaryOut(
        id=run.id,
        title=run.title,
        status=run.status.value,
        current_stage=run.current_stage.value if run.current_stage else None,
        created_at=run.created_at.isoformat(),
    )


def _stage_out(stage: Stage) -> StageOut:
    return StageOut(
        id=stage.id,
        kind=stage.kind.value,
        position=stage.position,
        status=stage.status.value,
        attempt=stage.attempt,
        error=stage.error,
        duration_seconds=stage.duration_seconds,
        input_tokens=stage.input_tokens,
        output_tokens=stage.output_tokens,
    )


def _artifact_out(artifact: Artifact) -> ArtifactOut:
    return ArtifactOut(
        id=artifact.id,
        kind=artifact.kind.value,
        name=artifact.name,
        version=artifact.version,
        data=artifact.data,
        text=artifact.text,
        created_at=artifact.created_at.isoformat(),
    )


def _audit_out(row: AuditRow) -> AuditOut:
    return AuditOut(
        id=row.id,
        kind=row.kind,
        target=row.target,
        ok=row.ok,
        duration_ms=row.duration_ms,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        detail=row.detail,
        error=row.error,
        created_at=row.created_at.isoformat(),
    )


def _detail(run: Run) -> RunDetailOut:
    return RunDetailOut(
        **_summary(run).model_dump(),
        error=run.error,
        slack_channel_id=run.slack_channel_id,
        slack_thread_ts=run.slack_thread_ts,
        stages=[_stage_out(s) for s in sorted(run.stages, key=lambda s: s.position)],
        artifacts=[
            _artifact_out(a)
            for a in sorted(run.artifacts, key=lambda a: (a.kind.value, a.name, a.version))
        ],
    )


def _load(run_id: uuid.UUID) -> Run:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs", response_model=list[RunSummaryOut])
async def list_runs() -> list[RunSummaryOut]:
    return [_summary(run) for run in store.list_runs()[:100]]


@router.get("/runs/{run_id}", response_model=RunDetailOut)
async def get_run(run_id: uuid.UUID) -> RunDetailOut:
    return _detail(_load(run_id))


@router.get("/runs/{run_id}/audit", response_model=list[AuditOut])
async def get_audit(run_id: uuid.UUID) -> list[AuditOut]:
    run = _load(run_id)
    return [_audit_out(row) for row in sorted(run.audit, key=lambda r: r.created_at)]


@router.get("/runs/{run_id}/artifacts/{artifact_id}", response_model=ArtifactOut)
async def get_artifact(run_id: uuid.UUID, artifact_id: uuid.UUID) -> ArtifactOut:
    run = _load(run_id)
    artifact = next((a for a in run.artifacts if a.id == artifact_id), None)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _artifact_out(artifact)


@router.get("/stages/{stage_id}", response_model=StageOut)
async def get_stage(stage_id: uuid.UUID) -> StageOut:
    for run in store.list_runs():
        stage = next((s for s in run.stages if s.id == stage_id), None)
        if stage is not None:
            return _stage_out(stage)
    raise HTTPException(status_code=404, detail="Stage not found")


@router.post("/runs/{run_id}/rerun", response_model=RunDetailOut)
async def rerun(run_id: uuid.UUID, body: RerunIn) -> RunDetailOut:
    run = _load(run_id)
    if not any(stage.kind == body.stage for stage in run.stages):
        raise HTTPException(status_code=400, detail=f"{body.stage} is not a stage of this run")

    asyncio.create_task(_rerun_in_background(run_id, body.stage, body.feedback))
    return _detail(run)


async def _rerun_in_background(run_id: uuid.UUID, stage: StageKind, feedback: str | None) -> None:
    try:
        await engine.rerun_stage(run_id, stage, feedback=feedback)
    except Exception:
        log.exception("background re-run of %s on run %s failed", stage, run_id)


def _signature(run: Run) -> tuple:
    return (
        run.status,
        run.current_stage,
        run.error,
        len(run.artifacts),
        tuple(sorted((s.kind, s.status, s.attempt, s.error) for s in run.stages)),
    )


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: uuid.UUID) -> StreamingResponse:

    async def frames() -> AsyncIterator[str]:
        previous: tuple | None = None
        since_heartbeat = 0.0
        try:
            while True:
                run = store.get(run_id)
                if run is None:
                    yield 'event: error\ndata: {"detail": "Run not found"}\n\n'
                    return

                signature = _signature(run)
                if signature != previous:
                    previous = signature
                    since_heartbeat = 0.0
                    payload = _detail(run).model_dump(mode="json")
                    yield f"data: {json.dumps(payload)}\n\n"
                if run.status in TERMINAL_RUN_STATUSES:
                    yield "event: end\ndata: {}\n\n"
                    return

                await asyncio.sleep(POLL_SECONDS)
                since_heartbeat += POLL_SECONDS
                if since_heartbeat >= HEARTBEAT_SECONDS:
                    since_heartbeat = 0.0
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            raise

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
