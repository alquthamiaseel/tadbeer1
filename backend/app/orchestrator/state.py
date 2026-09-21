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
    INGEST = "INGEST"
    PLAN = "PLAN"


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


@dataclass
class Artifact:
    kind: ArtifactKind
    name: str
    version: int = 1
    data: dict | None = None
    text: str | None = None
    id: uuid.UUID = field(default_factory=_uuid)
    created_at: datetime = field(default_factory=_now)


@dataclass
class AuditRow:
    kind: str
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
    channel_id: str
    ts: str
    thread_ts: str | None = None
    user_id: str | None = None
    user_name: str | None = None
    text: str = ""
    is_bot: bool = False


@dataclass
class Run:
    title: str = "Untitled project"
    status: RunStatus = RunStatus.PENDING
    current_stage: StageKind | None = None
    error: str | None = None

    slack_channel_id: str | None = None
    slack_thread_ts: str | None = None
    started_by: str | None = None

    id: uuid.UUID = field(default_factory=_uuid)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    stages: list[Stage] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    audit: list[AuditRow] = field(default_factory=list)
