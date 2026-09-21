from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import dataclass

from app.orchestrator import engine, store
from app.orchestrator.state import ArtifactKind, SlackMessage, StageKind, StageStatus
from scripts.seed import CONVERSATION

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str

    def render(self) -> str:
        mark = f"{GREEN}PASS{RESET}" if self.ok else f"{RED}FAIL{RESET}"
        return f"  [{mark}] {self.name}\n         {DIM}{self.detail}{RESET}"


def _seed_conversation(channel_id: str) -> None:
    for index, (name, text) in enumerate(CONVERSATION):
        store.capture_message(
            SlackMessage(
                channel_id=channel_id,
                ts=f"{1740000000 + index * 60}.000100",
                user_id=f"USEED{index:02d}",
                user_name=name,
                text=text,
                is_bot=False,
            )
        )


async def drive(channel_id: str) -> uuid.UUID:
    _seed_conversation(channel_id)
    run = await engine.create_run(
        title="Phase 1 acceptance", slack_channel_id=channel_id, started_by="e2e"
    )
    run_id = run.id
    print(f"{DIM}run {run_id}{RESET}")

    async def announce(_run, stage):
        print(f"  {stage.kind:<10} {stage.status:<18} {stage.duration_seconds or 0:.1f}s")

    await engine.advance(run_id, on_stage=announce)
    return run_id


def verify(run_id: uuid.UUID) -> list[Check]:
    run = store.get(run_id)
    if run is None:
        return [Check("Run exists", False, f"no run with id {run_id}")]

    checks = [_check_requirements(run), _check_plan(run)]
    return checks


def _check_requirements(run) -> Check:
    ingest = next((s for s in run.stages if s.kind == StageKind.INGEST), None)
    artifacts = [a for a in run.artifacts if a.kind == ArtifactKind.REQUIREMENTS]
    if ingest is None or ingest.status != StageStatus.COMPLETE or not artifacts:
        status = ingest.status if ingest else "missing"
        return Check("Requirements extracted by the LLM", False, f"INGEST is {status}")
    data = artifacts[-1].data or {}
    return Check(
        "Requirements extracted by the LLM",
        True,
        f"{data.get('project_name', '?')}: {len(data.get('features', []))} features, "
        f"{len(data.get('constraints', []))} constraints",
    )


def _check_plan(run) -> Check:
    plan_stage = next((s for s in run.stages if s.kind == StageKind.PLAN), None)
    artifacts = [a for a in run.artifacts if a.kind == ArtifactKind.PLAN]
    if plan_stage is None or plan_stage.status != StageStatus.AWAITING_APPROVAL or not artifacts:
        status = plan_stage.status if plan_stage else "missing"
        return Check("Plan produced from those requirements", False, f"PLAN is {status}")
    data = artifacts[-1].data or {}
    return Check(
        "Plan produced from those requirements",
        True,
        f"{len(data.get('phases', []))} phases, "
        f"{data.get('estimated_total_days', '?')} estimated days, awaiting approval",
    )


async def main_async(args) -> int:
    run_id = await drive(args.channel)

    print("\nAcceptance checks")
    checks = verify(run_id)
    for item in checks:
        print(item.render())

    passed = sum(1 for item in checks if item.ok)
    print(f"\n{passed}/{len(checks)} checks passed")
    if args.json:
        print(json.dumps([{"name": c.name, "ok": c.ok, "detail": c.detail} for c in checks]))
    return 0 if passed == len(checks) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel", required=True, help="a Slack channel id to tag this run with (any value)"
    )
    parser.add_argument("--json", action="store_true", help="also print the results as JSON")
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
