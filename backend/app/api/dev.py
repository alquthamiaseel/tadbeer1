"""Dev-only convenience: pre-load a canned conversation into the running process.

Slack messages now live in memory inside this process (see
``app.orchestrator.store``), so a separate script can no longer seed them by
writing to a database the API will later read. This endpoint lets
``scripts/seed.py`` inject a conversation into the *running* backend instead,
so a live Slack demo can still be rehearsed without retyping messages.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import require_dashboard_auth
from app.orchestrator import store
from app.orchestrator.state import SlackMessage

router = APIRouter(
    prefix="/api/dev", tags=["dev"], dependencies=[Depends(require_dashboard_auth)]
)


class SeedMessageIn(BaseModel):
    channel_id: str
    ts: str
    user_id: str | None = None
    user_name: str | None = None
    text: str


class SeedIn(BaseModel):
    messages: list[SeedMessageIn]
    reset: bool = False


class SeedOut(BaseModel):
    stored: int


@router.post("/seed-messages", response_model=SeedOut)
async def seed_messages(body: SeedIn) -> SeedOut:
    if body.reset and body.messages:
        channel_id = body.messages[0].channel_id
        store.reset_channel(channel_id)

    stored = 0
    for message in body.messages:
        added = store.capture_message(
            SlackMessage(
                channel_id=message.channel_id,
                ts=message.ts,
                user_id=message.user_id,
                user_name=message.user_name,
                text=message.text,
                is_bot=False,
            )
        )
        stored += 1 if added else 0
    return SeedOut(stored=stored)
