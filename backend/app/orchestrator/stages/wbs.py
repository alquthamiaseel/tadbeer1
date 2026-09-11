"""WBS — derive a dependency-aware task graph and publish it to Asana.

Publishing can be turned off with ``ASANA_ENABLED=false``. The work breakdown
is the artifact; Asana is where it gets *shown*. Losing access to the second —
a workspace that has not arrived yet, or a free tier that cannot link
dependencies — should not cost the first, and the dashboard renders the task
graph with its dependencies either way.

Opt-out rather than automatic: a missing token with publishing still enabled is
almost always a misconfiguration, and silently skipping it would hide that until
the demo.
"""

from __future__ import annotations

import json
import logging

from app.config import settings
from app.integrations.asana import AsanaClient
from app.llm.client import generate_structured
from app.models import ArtifactKind, StageKind
from app.orchestrator.base import (
    ProducedArtifact,
    StageContext,
    StageFailed,
    StageResult,
    artifact_data,
)
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
        run_updates: dict[str, object] = {}

        if settings.asana_enabled:
            project_gid, project_url = await AsanaClient().publish(ctx.run.title, wbs)
            run_updates = {"asana_project_gid": project_gid, "asana_project_url": project_url}
            summary = f"Published {len(wbs.tasks)} tasks to Asana"
        else:
            # The work breakdown is the artifact; Asana is where it gets shown.
            # Losing the second must not cost the first.
            log.info("ASANA_ENABLED is false; keeping the WBS without publishing it")
            summary = (
                f"{len(wbs.tasks)} tasks with {dependencies} dependencies "
                "(Asana publishing is turned off)"
            )

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
            run_updates=run_updates,
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
