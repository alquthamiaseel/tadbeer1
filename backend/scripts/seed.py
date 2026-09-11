"""Replay a canned stakeholder conversation into the database.

A demo should not depend on typing six messages into Slack correctly while
someone watches. This writes the same conversation the pipeline would have
captured, so ``/pm start`` in that channel has something to read — and so a
rehearsal is repeatable rather than improvised.

Usage:
    python -m scripts.seed --channel C0123456789
    python -m scripts.seed --channel C0123456789 --reset
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import SlackMessage

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


async def seed(channel_id: str, *, reset: bool) -> int:
    async with SessionLocal() as session:
        if reset:
            await session.execute(delete(SlackMessage).where(SlackMessage.channel_id == channel_id))
            await session.commit()

        existing = await session.execute(
            select(SlackMessage).where(SlackMessage.channel_id == channel_id)
        )
        if existing.scalars().first() is not None:
            print(
                f"{channel_id} already has captured messages. "
                "Pass --reset to replace them, or use a different channel."
            )
            return 1

        for index, (name, text) in enumerate(CONVERSATION):
            session.add(
                SlackMessage(
                    channel_id=channel_id,
                    # Slack timestamps are "seconds.microseconds" strings and
                    # the transcript is ordered by them, so they must ascend.
                    ts=f"{1740000000 + index * 60}.000100",
                    user_id=f"USEED{index:02d}",
                    user_name=name,
                    text=text,
                    is_bot=False,
                )
            )
        await session.commit()

    print(f"Seeded {len(CONVERSATION)} messages into {channel_id}.")
    print("Now run `/pm start` in that channel, or `make e2e`.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", required=True, help="Slack channel id, e.g. C0123456789")
    parser.add_argument(
        "--reset", action="store_true", help="delete existing messages for this channel first"
    )
    args = parser.parse_args()
    return asyncio.run(seed(args.channel, reset=args.reset))


if __name__ == "__main__":
    sys.exit(main())
