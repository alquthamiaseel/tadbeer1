"""WBS — derive a dependency-aware task graph.

Not part of the Phase 1 demo (Slack → requirements → plan → dashboard); this
stage still runs if a plan is approved, but the Asana publishing step has been
removed from this build. The task graph itself is still produced and stored as
an artifact; only the push to an external Asana project is gone.
"""

from __future__ import annotations

import json
import logging

from app.llm.client import generate_structured
from app.orchestrator.base import (
    ProducedArtifact,
    StageContext,
    StageFailed,
    StageResult,
    artifact_data,
)
from app.orchestrator.state import ArtifactKind, StageKind
from app.schemas.wbs import WorkBreakdownStructure

log = logging.getLogger(__name__)

SYSTEM = """You are a delivery manager creating a work-breakdown structure from an approved plan.
Return a feasible flat task graph. Each task must have a unique stable id. Dependencies may only
refer to earlier task ids; never create cycles. Keep this FYP-sized and practical to deliver."""


class WbsStage:
    kind = StageKind.WBS

    async def run(self, ctx: StageContext) -> StageResult:
        plan = artifact_data(ctx.run, ArtifactKind.PLAN)
        requirements = artifact_data(ctx.run, ArtifactKind.REQUIREMENTS)
        result = await generate_structured(
            output_model=WorkBreakdownStructure,
            system=SYSTEM,
            user=(
                "Approved plan:\n"
                + json.dumps(plan, indent=2)
                + "\n\nValidated requirements:\n"
                + json.dumps(requirements, indent=2)
            ),
            max_output_tokens=16_000,
        )
        wbs = result.data
        self._validate_dependencies(wbs)

        dependencies = sum(len(task.depends_on) for task in wbs.tasks)
        summary = f"{len(wbs.tasks)} tasks with {dependencies} dependencies"

        return StageResult(
            artifacts=[
                ProducedArtifact(
                    kind=ArtifactKind.WBS,
                    name="Work breakdown structure",
                    data=wbs.model_dump(mode="json"),
                )
            ],
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            summary=summary,
        )

    @staticmethod
    def _validate_dependencies(wbs: WorkBreakdownStructure) -> None:
        seen: set[str] = set()
        for task in wbs.tasks:
            if task.id in seen:
                raise StageFailed(f"WBS contains duplicate task id {task.id}.", retryable=False)
            invalid = set(task.depends_on) - seen
            if invalid:
                raise StageFailed(
                    f"WBS task {task.id} has forward or unknown dependencies: {sorted(invalid)}.",
                    retryable=False,
                )
            seen.add(task.id)
