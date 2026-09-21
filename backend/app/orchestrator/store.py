from __future__ import annotations

import uuid

from app.orchestrator.state import Run, SlackMessage

_runs: dict[uuid.UUID, Run] = {}

_messages: dict[str, list[SlackMessage]] = {}
_seen_messages: set[tuple[str, str]] = set()


def add(run: Run) -> Run:
    _runs[run.id] = run
    return run


def get(run_id: uuid.UUID) -> Run | None:
    return _runs.get(run_id)


def list_runs() -> list[Run]:
    return sorted(_runs.values(), key=lambda r: r.created_at, reverse=True)


def active_run(channel_id: str, thread_ts: str | None) -> Run | None:
    candidates = [
        run
        for run in _runs.values()
        if run.slack_channel_id == channel_id
        and (thread_ts is None or run.slack_thread_ts == thread_ts)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda r: r.created_at)


def capture_message(message: SlackMessage) -> bool:
    key = (message.channel_id, message.ts)
    if key in _seen_messages:
        return False
    _seen_messages.add(key)
    _messages.setdefault(message.channel_id, []).append(message)
    return True


def messages_for(channel_id: str, thread_ts: str | None) -> list[SlackMessage]:
    channel_messages = _messages.get(channel_id, [])
    if thread_ts is None:
        return list(channel_messages)
    return [m for m in channel_messages if m.thread_ts == thread_ts]


def message_count(channel_id: str) -> int:
    return len(_messages.get(channel_id, []))


def reset_channel(channel_id: str) -> None:
    for message in _messages.pop(channel_id, []):
        _seen_messages.discard((message.channel_id, message.ts))


def reset() -> None:
    _runs.clear()
    _messages.clear()
    _seen_messages.clear()
