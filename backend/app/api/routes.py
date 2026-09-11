"""REST API consumed by the dashboard.

The dashboard is read-only over pipeline state, with one exception: re-running a
stage. Approvals stay in Slack, because the approval conversation is the point —
a decision made in the dashboard would leave no trace where the stakeholders are
talking.

Progress is streamed rather than polled by the browser. The stream itself polls
the database once a second, which is the right trade here: runs are minutes
long and low-volume, and a pub/sub broker would be a second service to install
and keep alive for a signal this small.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import require_dashboard_auth
from app.db import SessionLocal, get_session
from app.models import Artifact, AuditLog, Run, RunStatus, Stage, StageKind
from app.orchestrator import engine

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["runs"], dependencies=[Depends(require_dashboard_auth)])

#: How often the event stream re-reads the run. A stage takes tens of seconds,
#: so this is far finer-grained than the thing it is watching.
POLL_SECONDS = 1.0
#: Comment frames keep proxies from closing an idle stream.
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
    asana_project_url: str | None
    github_repo_url: str | None
    vercel_url: str | None


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
        asana_project_url=run.asana_project_url,
        github_repo_url=run.github_repo_url,
        vercel_url=run.vercel_url,
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


async def _load(session: AsyncSession, run_id: uuid.UUID) -> Run:
    result = await session.execute(
        select(Run)
        .where(Run.id == run_id)
        .options(selectinload(Run.stages), selectinload(Run.artifacts))
        .execution_options(populate_existing=True)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs", response_model=list[RunSummaryOut])
async def list_runs(session: AsyncSession = Depends(get_session)) -> list[RunSummaryOut]:
    result = await session.execute(select(Run).order_by(Run.created_at.desc()).limit(100))
    return [_summary(run) for run in result.scalars()]


@router.get("/runs/{run_id}", response_model=RunDetailOut)
async def get_run(run_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> RunDetailOut:
    return _detail(await _load(session, run_id))


@router.get("/runs/{run_id}/audit", response_model=list[AuditOut])
async def get_audit(
    run_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[AuditOut]:
    """Every model and external API call this run made."""
    result = await session.execute(
        select(AuditLog).where(AuditLog.run_id == run_id).order_by(AuditLog.created_at)
    )
    return [
        AuditOut(
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
        for row in result.scalars()
    ]


@router.get("/runs/{run_id}/artifacts/{artifact_id}", response_model=ArtifactOut)
async def get_artifact(
    run_id: uuid.UUID,
    artifact_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ArtifactOut:
    result = await session.execute(
        select(Artifact).where(Artifact.id == artifact_id, Artifact.run_id == run_id)
    )
    artifact = result.scalar_one_or_none()
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return _artifact_out(artifact)


@router.get("/stages/{stage_id}", response_model=StageOut)
async def get_stage(stage_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> StageOut:
    stage = await session.get(Stage, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")
    return _stage_out(stage)


@router.post("/runs/{run_id}/rerun", response_model=RunDetailOut)
async def rerun(
    run_id: uuid.UUID, body: RerunIn, session: AsyncSession = Depends(get_session)
) -> RunDetailOut:
    """Reset a stage and everything after it, then run forward in the background.

    Returns immediately with the reset state. A run takes minutes; holding the
    HTTP request open for it would only invite a proxy to time it out.
    """
    run = await _load(session, run_id)
    if not any(stage.kind == body.stage for stage in run.stages):
        raise HTTPException(status_code=400, detail=f"{body.stage} is not a stage of this run")

    asyncio.create_task(_rerun_in_background(run_id, body.stage, body.feedback))
    return _detail(run)


async def _rerun_in_background(run_id: uuid.UUID, stage: StageKind, feedback: str | None) -> None:
    """Own session: the request's is closed the moment the response is sent."""
    try:
        async with SessionLocal() as session:
            await engine.rerun_stage(session, run_id, stage, feedback=feedback)
    except Exception:  # noqa: BLE001 - a background task must not die silently
        log.exception("background re-run of %s on run %s failed", stage, run_id)


def _signature(run: Run) -> tuple:
    """What has to change for the dashboard to need a new frame."""
    return (
        run.status,
        run.current_stage,
        run.error,
        run.asana_project_url,
        run.github_repo_url,
        run.vercel_url,
        len(run.artifacts),
        tuple(sorted((s.kind, s.status, s.attempt, s.error) for s in run.stages)),
    )


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: uuid.UUID) -> StreamingResponse:
    """Server-sent events: one frame per actual change, then done."""

    async def frames() -> AsyncIterator[str]:
        previous: tuple | None = None
        since_heartbeat = 0.0
        try:
            while True:
                async with SessionLocal() as session:
                    run = await _load(session, run_id)
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
        except asyncio.CancelledError:  # the browser navigated away
            raise
        except HTTPException:
            yield 'event: error\ndata: {"detail": "Run not found"}\n\n'

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Nginx and friends buffer streamed responses into uselessness.
            "X-Accel-Buffering": "no",
        },
    )
