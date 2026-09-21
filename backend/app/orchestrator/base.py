from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.orchestrator.state import ArtifactKind, Run, StageKind


@dataclass
class StageContext:
    run: Run
    feedback: str | None = None


@dataclass
class ProducedArtifact:
    kind: ArtifactKind
    name: str
    data: dict | None = None
    text: str | None = None


@dataclass
class StageResult:
    artifacts: list[ProducedArtifact] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    run_updates: dict[str, object] = field(default_factory=dict)
    needs_approval: bool = False
    summary: str = ""


class Stage(Protocol):
    kind: StageKind

    async def run(self, ctx: StageContext) -> StageResult: ...


class StageFailed(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


def artifact_data(run: Run, kind: ArtifactKind) -> dict:
    matching = [a for a in run.artifacts if a.kind == kind and a.data is not None]
    if not matching:
        raise StageFailed(
            f"expected a {kind.value} artifact from an earlier stage but none exists; "
            "re-run the earlier stage first",
            retryable=False,
        )
    latest = max(matching, key=lambda a: (a.version, a.created_at))
    return latest.data or {}


def run_id_of(ctx: StageContext) -> uuid.UUID:
    return ctx.run.id
