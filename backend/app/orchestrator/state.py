"""Runtime pipeline state.

Nothing here is persisted. A run lives for as long as the process that created
it: the database is authentication only, so the pipeline's own state — which
stage it is on, what each stage produced, what it called — is plain Python
objects held in memory for the lifetime of one run.
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(UTC)


class StageKind(enum.StrEnum):
    """The six pipeline stages, in execution order."""

    INGEST = "INGEST"
    PLAN = "PLAN"
    WBS = "WBS"
    DESIGN = "DESIGN"
    PROTOTYPE = "PROTOTYPE"
    DONE = "DONE"


#: Execution order. The orchestrator walks this list; there is no other ordering.
#:
#: Phase 1 runs only INGEST and PLAN — Slack conversation to requirements to a
#: reviewable plan. WBS, DESIGN, PROTOTYPE and DONE stay fully implemented
#: (``app.orchestrator.stages``) for a later phase; they are simply not part of
#: a run's stage list until they are added back here.
STAGE_ORDER: list[StageKind] = [
    StageKind.INGEST,
    StageKind.PLAN,
]


class StageStatus(enum.StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class RunStatus(enum.StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ArtifactKind(enum.StrEnum):
    REQUIREMENTS = "REQUIREMENTS"
    PLAN = "PLAN"
    WBS = "WBS"
    DIAGRAM = "DIAGRAM"
    PROTOTYPE_FILES = "PROTOTYPE_FILES"
    SUMMARY = "SUMMARY"


@dataclass
class Artifact:
    """A structured output produced by a stage.

    `data` holds the validated JSON the LLM produced against that stage's schema.
    `text` holds raw text output where that is the natural form (Mermaid source,
    generated file contents).
    """

    kind: ArtifactKind
    name: str
    version: int = 1
    data: dict | None = None
    text: str | None = None
    id: uuid.UUID = field(default_factory=_uuid)
    created_at: datetime = field(default_factory=_now)


@dataclass
class AuditRow:
    """One model call or external API call, kept for the run's lifetime."""

    kind: str  # "llm" | "api"
    target: str
    ok: bool = True
    duration_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    detail: dict | None = None
    error: str | None = None
    id: uuid.UUID = field(default_factory=_uuid)
    created_at: datetime = field(default_factory=_now)


@dataclass
class Stage:
    """One step of the pipeline within a run."""

    kind: StageKind
    position: int
    status: StageStatus = StageStatus.PENDING
    attempt: int = 0
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    id: uuid.UUID = field(default_factory=_uuid)

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class SlackMessage:
    """One captured Slack message, held in memory for the process's lifetime."""

    channel_id: str
    ts: str
    thread_ts: str | None = None
    user_id: str | None = None
    user_name: str | None = None
    text: str = ""
    is_bot: bool = False


@dataclass
class Run:
    """One end-to-end pass from a Slack conversation to a deployed prototype."""

    title: str = "Untitled project"
    status: RunStatus = RunStatus.PENDING
    current_stage: StageKind | None = None
    error: str | None = None

    # Where the conversation lives. thread_ts is None for whole-channel runs.
    slack_channel_id: str | None = None
    slack_thread_ts: str | None = None
    started_by: str | None = None

    # External artifacts produced by later stages.
    asana_project_gid: str | None = None
    asana_project_url: str | None = None
    github_repo_url: str | None = None
    vercel_url: str | None = None

    id: uuid.UUID = field(default_factory=_uuid)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    stages: list[Stage] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    audit: list[AuditRow] = field(default_factory=list)
