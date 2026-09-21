"""Replay a canned stakeholder conversation into the running backend.

A demo should not depend on typing six messages into Slack correctly while
someone watches. This posts the same conversation the pipeline would have
captured to the backend's dev-seed endpoint, so ``/pm start`` in that channel
has something to read — and so a rehearsal is repeatable rather than
improvised.

Messages now live in memory inside the running API process (see
``app.orchestrator.store``), so this has to talk to that process over HTTP
rather than writing to a database — the backend must already be running
(``make api``).

Usage:
    python -m scripts.seed --channel C0123456789
    python -m scripts.seed --channel C0123456789 --reset
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import httpx

from app.config import settings

#: A conversation with the properties the pipeline needs to show its work:
#: two stakeholders who disagree slightly, a real constraint, a deadline, and
#: one feature explicitly ruled out — so `out_of_scope` has something in it and
#: the extraction can be checked rather than admired.
CONVERSATION: list[tuple[str, str]] = [
    (
        "priya",
        "We need something for booking seats at campus events. Right now it's a "
        "spreadsheet and it keeps breaking.",
    ),
    (
        "omar",
        "Students should be able to see what's on and reserve a seat. Society "
        "organisers create the events.",
    ),
    (
        "priya",
        "Organisers need to see who has booked, so they can plan catering and know when to stop.",
    ),
    (
        "omar",
        "It has to work properly on phones. Almost every student will book from "
        "their phone between lectures.",
    ),
    (
        "priya",
        "Each event has a capacity and it must not be possible to over-book it. "
        "That's the bit the spreadsheet gets wrong.",
    ),
    (
        "omar",
        "Should students be able to cancel? I think yes, otherwise no-shows hold "
        "seats nobody can take.",
    ),
    ("priya", "Yes, cancellation up to 24 hours before. After that it stays booked."),
    (
        "omar",
        "We talked about charging for some events, but we're not taking payments "
        "this year, so leave that out.",
    ),
    (
        "priya",
        "Budget is zero — it has to run on free tiers. And we need it live before "
        "the spring fair in March.",
    ),
    ("omar", "Sign-in should use university accounts so we know who is actually a student."),
]


def _headers() -> dict[str, str]:
    if not settings.dashboard_auth:
        return {}
    print("DASHBOARD_AUTH is on; pass a session token via API_TOKEN to seed the backend.")
    import os

    token = os.environ.get("API_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


async def seed(channel_id: str, *, reset: bool, base_url: str) -> int:
    messages = [
        {
            "channel_id": channel_id,
            # Slack timestamps are "seconds.microseconds" strings and the
            # transcript is ordered by them, so they must ascend.
            "ts": f"{1740000000 + index * 60}.000100",
            "user_id": f"USEED{index:02d}",
            "user_name": name,
            "text": text,
        }
        for index, (name, text) in enumerate(CONVERSATION)
    ]

    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        response = await client.post(
            "/api/dev/seed-messages",
            json={"messages": messages, "reset": reset},
            headers=_headers(),
        )
        if response.status_code != 200:
            print(f"Could not seed the backend: {response.status_code} {response.text}")
            print("Is it running? Start it with `make api`.")
            return 1
        stored = response.json()["stored"]

    if stored == 0 and not reset:
        print(
            f"{channel_id} already has captured messages. "
            "Pass --reset to replace them, or use a different channel."
        )
        return 1

    print(f"Seeded {stored} message(s) into {channel_id}.")
    print("Now run `/pm start` in that channel, or `make e2e`.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", required=True, help="Slack channel id, e.g. C0123456789")
    parser.add_argument(
        "--reset", action="store_true", help="replace existing messages for this channel first"
    )
    parser.add_argument(
        "--api", default=f"http://{settings.api_host}:{settings.api_port}", help="backend base URL"
    )
    args = parser.parse_args()
    return asyncio.run(seed(args.channel, reset=args.reset, base_url=args.api))


if __name__ == "__main__":
    sys.exit(main())
