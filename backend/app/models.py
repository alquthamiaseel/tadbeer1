"""Database models.

The pipeline is a resumable state machine, so the database — not memory — is the
source of truth for where a run is and what it has produced. Every stage writes
its output as an Artifact before the next stage starts, which is what makes a run
resumable after a crash and re-runnable stage by stage.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# JSONB on Postgres, plain JSON elsewhere (tests run on SQLite).
JSONType = sa.JSON().with_variant(JSONB, "postgresql")


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)


def _now_col(**kw) -> Mapped[datetime]:
    return mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), **kw)


class StageKind(enum.StrEnum):
    """The six pipeline stages, in execution order."""

    INGEST = "INGEST"
    PLAN = "PLAN"
    WBS = "WBS"
    DESIGN = "DESIGN"
    PROTOTYPE = "PROTOTYPE"
    DONE = "DONE"


#: Execution order. The orchestrator walks this list; there is no other ordering.
STAGE_ORDER: list[StageKind] = [
    StageKind.INGEST,
    StageKind.PLAN,
    StageKind.WBS,
    StageKind.DESIGN,
    StageKind.PROTOTYPE,
    StageKind.DONE,
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


class ApprovalDecision(enum.StrEnum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


class Run(Base):
    """One end-to-end pass from a Slack conversation to a deployed prototype."""

    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(sa.String(300), default="Untitled project")
    status: Mapped[RunStatus] = mapped_column(
        sa.Enum(RunStatus, native_enum=False, length=32), default=RunStatus.PENDING
    )
    current_stage: Mapped[StageKind | None] = mapped_column(
        sa.Enum(StageKind, native_enum=False, length=32), nullable=True
    )
    error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    # Where the conversation lives. thread_ts is null for whole-channel runs.
    slack_channel_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    slack_thread_ts: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    started_by: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)

    # External artifacts produced by later stages.
    asana_project_gid: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    asana_project_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    github_repo_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    vercel_url: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)

    created_at: Mapped[datetime] = _now_col()
    updated_at: Mapped[datetime] = _now_col(onupdate=sa.func.now())

    stages: Mapped[list[Stage]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Stage.position"
    )
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    approvals: Mapped[list[Approval]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Stage(Base):
    """One step of the pipeline within a run."""

    __tablename__ = "stages"
    __table_args__ = (sa.UniqueConstraint("run_id", "kind", name="uq_stage_run_kind"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[StageKind] = mapped_column(sa.Enum(StageKind, native_enum=False, length=32))
    position: Mapped[int] = mapped_column(sa.Integer)
    status: Mapped[StageStatus] = mapped_column(
        sa.Enum(StageStatus, native_enum=False, length=32), default=StageStatus.PENDING
    )

    attempt: Mapped[int] = mapped_column(sa.Integer, default=0)
    error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    # Token accounting, surfaced in the dashboard and useful as report evidence.
    input_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)

    created_at: Mapped[datetime] = _now_col()

    run: Mapped[Run] = relationship(back_populates="stages")
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="stage")

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class Artifact(Base):
    """A structured output produced by a stage.

    `data` holds the validated JSON the LLM produced against that stage's schema.
    `text` holds raw text output where that is the natural form (Mermaid source,
    generated file contents).
    """

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("stages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[ArtifactKind] = mapped_column(sa.Enum(ArtifactKind, native_enum=False, length=32))
    name: Mapped[str] = mapped_column(sa.String(200))
    version: Mapped[int] = mapped_column(sa.Integer, default=1)

    data: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    text: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    created_at: Mapped[datetime] = _now_col()

    run: Mapped[Run] = relationship(back_populates="artifacts")
    stage: Mapped[Stage | None] = relationship(back_populates="artifacts")


class Approval(Base):
    """A human decision on a stage, captured from Slack."""

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("stages.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[ApprovalDecision] = mapped_column(
        sa.Enum(ApprovalDecision, native_enum=False, length=32)
    )
    feedback: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    slack_message_ts: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)

    created_at: Mapped[datetime] = _now_col()

    run: Mapped[Run] = relationship(back_populates="approvals")


class SlackMessage(Base):
    """A captured Slack message.

    Stored independently of runs because messages are captured as they arrive —
    a run is created later and claims the conversation it was started from.
    """

    __tablename__ = "slack_messages"
    __table_args__ = (sa.UniqueConstraint("channel_id", "ts", name="uq_slack_channel_ts"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel_id: Mapped[str] = mapped_column(sa.String(64), index=True)
    thread_ts: Mapped[str | None] = mapped_column(sa.String(64), nullable=True, index=True)
    ts: Mapped[str] = mapped_column(sa.String(64))
    user_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    user_name: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    text: Mapped[str] = mapped_column(sa.Text, default="")
    is_bot: Mapped[bool] = mapped_column(sa.Boolean, default=False)

    created_at: Mapped[datetime] = _now_col()


class AuditLog(Base):
    """Every LLM call and external API call, for debugging and report evidence."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _uuid_pk()
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("stages.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(sa.String(32))  # "llm" | "api"
    target: Mapped[str] = mapped_column(sa.String(200))  # model id or "asana:create_task"
    ok: Mapped[bool] = mapped_column(sa.Boolean, default=True)
    duration_ms: Mapped[int] = mapped_column(sa.Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    detail: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    error: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    created_at: Mapped[datetime] = _now_col()
