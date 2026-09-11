"""Asana — publish an approved work-breakdown structure as a real project.

Dependencies are the reason this integration exists rather than a CSV export:
the project statement calls for a WBS "with all dependencies and constraints",
and Asana is where a project manager would actually look at one.

Note that ``addDependencies`` requires a Premium or Advanced workspace. On the
free tier the project, sections and tasks are all created and only the
dependency links fail — so the failure arrives late, with most of the work
already done. :meth:`publish` reports that specific case for what it is.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from app.config import settings
from app.integrations.http import request_json
from app.orchestrator.base import StageFailed
from app.schemas.wbs import WbsTask, WorkBreakdownStructure

BASE_URL = "https://app.asana.com/api/1.0"


class AsanaClient:
    """Creates an Asana project, sections, tasks, then dependency links."""

    def __init__(self, *, token: str | None = None, workspace_gid: str | None = None) -> None:
        self.token = token if token is not None else settings.asana_access_token
        self.workspace_gid = (
            workspace_gid if workspace_gid is not None else settings.asana_workspace_gid
        )

    def _headers(self) -> dict[str, str]:
        if not self.token or not self.workspace_gid:
            raise StageFailed(
                "Asana is not configured. Set ASANA_ACCESS_TOKEN and "
                "ASANA_WORKSPACE_GID, then re-run WBS.",
                retryable=False,
            )
        return {"Authorization": f"Bearer {self.token}"}

    async def publish(self, project_name: str, wbs: WorkBreakdownStructure) -> tuple[str, str]:
        async with httpx.AsyncClient(
            base_url=BASE_URL, headers=self._headers(), timeout=30
        ) as client:
            project = await self._post(
                client,
                "/projects",
                {
                    "name": project_name,
                    "workspace": self.workspace_gid,
                    "notes": wbs.project_summary,
                },
            )
            project_gid = project["gid"]
            phases = list(dict.fromkeys(task.phase for task in wbs.tasks))
            sections = {
                phase: await self._post(
                    client, f"/projects/{project_gid}/sections", {"name": phase}
                )
                for phase in phases
            }
            gids: dict[str, str] = {}
            start = datetime.now(UTC).date()
            for task in wbs.tasks:
                created = await self._post(
                    client,
                    "/tasks",
                    self._task_payload(task, project_gid, sections[task.phase]["gid"], start),
                )
                gids[task.id] = created["gid"]
            await self._link_dependencies(client, wbs, gids, project_gid)
        return project_gid, f"https://app.asana.com/0/{project_gid}/list"

    async def _link_dependencies(
        self,
        client: httpx.AsyncClient,
        wbs: WorkBreakdownStructure,
        gids: dict[str, str],
        project_gid: str,
    ) -> None:
        """Link every dependency, or explain why the workspace cannot.

        By this point the project and every task already exist, so a bare
        "Asana returned 402" would leave the user staring at a project that
        looks fine and a run that failed for no visible reason.
        """
        for task in wbs.tasks:
            for dependency in task.depends_on:
                try:
                    await self._post(
                        client,
                        f"/tasks/{gids[task.id]}/addDependencies",
                        {"dependencies": [gids[dependency]]},
                    )
                except StageFailed as exc:
                    if not _is_tier_limit(exc):
                        raise
                    raise StageFailed(
                        "Asana created the project and all its tasks, but linking task "
                        "dependencies requires a Premium or Advanced workspace and this "
                        "one is on the free tier. Start the 30-day trial at "
                        "https://app.asana.com/0/organization-admin, then re-run WBS. "
                        f"The tasks created so far are at "
                        f"https://app.asana.com/0/{project_gid}/list",
                        retryable=False,
                    ) from exc

    async def _post(self, client: httpx.AsyncClient, path: str, data: dict) -> dict:
        """One Asana write, retried on rate limits by the shared HTTP layer."""
        body = await request_json(client, "POST", path, service="Asana", json={"data": data})
        return body.get("data", {})

    @staticmethod
    def _task_payload(task: WbsTask, project_gid: str, section_gid: str, start) -> dict:
        constraints = ", ".join(task.constraints) if task.constraints else "None"
        payload = {
            "name": task.name,
            "notes": (
                f"{task.description}\n\nOwner role: {task.owner_role}\n"
                f"Estimate: {task.estimate_days} working day(s)\nConstraints: {constraints}"
            ),
            "projects": [project_gid],
            "memberships": [{"project": project_gid, "section": section_gid}],
        }
        if task.due_offset_days is not None:
            payload["due_on"] = (start + timedelta(days=task.due_offset_days)).isoformat()
        return payload


#: Asana signals "your plan does not include this" with a payment-required
#: status or a message naming the tier, depending on the endpoint.
_TIER_MARKERS = ("402", "premium", "upgrade", "not available on your plan", "payment")


def _is_tier_limit(exc: StageFailed) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _TIER_MARKERS)
