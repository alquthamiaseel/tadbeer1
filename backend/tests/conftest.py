"""Test fixtures.

Tests run against a real SQLite database rather than mocked sessions. The
engine's whole job is persisting state correctly — resumability, versioned
artifacts, status transitions — and a mocked session would verify none of it.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import Base
from app.models import SlackMessage


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s

    await engine.dispose()


CONVERSATION = [
    ("priya", "We need something for booking campus event seats. Right now it's a spreadsheet."),
    ("omar", "Students should see what's on and reserve a seat. Organisers create the events."),
    ("priya", "Organisers need to see who has booked so they can plan catering."),
    ("omar", "It has to work on phones — most students will book from their phone."),
    ("priya", "Budget is nil, so nothing paid. And we want it before the spring fair in March."),
    ("omar", "We talked about payments earlier but we're not charging for events, so skip that."),
]


@pytest.fixture
async def conversation(session: AsyncSession) -> list[SlackMessage]:
    """A realistic stakeholder conversation captured in a channel."""
    messages = [
        SlackMessage(
            channel_id="C123",
            ts=f"1700000{index:03d}.000000",
            user_id=f"U{index}",
            user_name=name,
            text=text,
            is_bot=False,
        )
        for index, (name, text) in enumerate(CONVERSATION)
    ]
    session.add_all(messages)
    await session.commit()
    return messages
