from __future__ import annotations

import httpx
import pytest

from app.main import app
from app.orchestrator import store


@pytest.fixture
async def api():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_seeding_stores_messages_the_pipeline_can_read(api):
    response = await api.post(
        "/api/dev/seed-messages",
        json={
            "messages": [
                {"channel_id": "C1", "ts": "1", "user_name": "priya", "text": "hello"},
                {"channel_id": "C1", "ts": "2", "user_name": "omar", "text": "hi there"},
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {"stored": 2}
    assert len(store.messages_for("C1", None)) == 2


async def test_reseeding_the_same_channel_replaces_it(api):
    await api.post(
        "/api/dev/seed-messages",
        json={"messages": [{"channel_id": "C1", "ts": "1", "text": "old"}]},
    )

    response = await api.post(
        "/api/dev/seed-messages",
        json={
            "messages": [{"channel_id": "C1", "ts": "2", "text": "new"}],
            "reset": True,
        },
    )

    assert response.status_code == 200
    stored = store.messages_for("C1", None)
    assert len(stored) == 1
    assert stored[0].text == "new"


async def test_redelivered_seed_messages_are_not_double_counted(api):
    payload = {"messages": [{"channel_id": "C1", "ts": "1", "text": "hi"}]}

    first = await api.post("/api/dev/seed-messages", json=payload)
    second = await api.post("/api/dev/seed-messages", json=payload)

    assert first.json() == {"stored": 1}
    assert second.json() == {"stored": 0}
    assert len(store.messages_for("C1", None)) == 1
