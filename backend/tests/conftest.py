from __future__ import annotations

import pytest

from app.orchestrator import store
from app.orchestrator.state import SlackMessage


@pytest.fixture(autouse=True)
def _reset_store():
    store.reset()
    yield
    store.reset()


CONVERSATION = [
    ("priya", "We need something for booking campus event seats. Right now it's a spreadsheet."),
    ("omar", "Students should see what's on and reserve a seat. Organisers create the events."),
    ("priya", "Organisers need to see who has booked so they can plan catering."),
    ("omar", "It has to work on phones — most students will book from their phone."),
    ("priya", "Budget is nil, so nothing paid. And we want it before the spring fair in March."),
    ("omar", "We talked about payments earlier but we're not charging for events, so skip that."),
]


@pytest.fixture
def conversation() -> list[SlackMessage]:
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
    for message in messages:
        store.capture_message(message)
    return messages
