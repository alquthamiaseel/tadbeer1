from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import require_dashboard_auth
from app.orchestrator import store
from app.orchestrator.state import SlackMessage

router = APIRouter(prefix="/api/dev", tags=["dev"], dependencies=[Depends(require_dashboard_auth)])


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
