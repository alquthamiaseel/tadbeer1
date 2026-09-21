"""The in-memory run and conversation registry.

This is the whole point of the refactor: what used to be five database tables
(runs, stages, artifacts, slack_messages, audit_log) is now two plain dicts
living in the process. Runs disappear when the process restarts — this app
runs as a single process (the Slack listener is a background task inside the
same FastAPI app, see ``app.main``), so anything the Slack side creates is
immediately visible to the dashboard side without a database in between.

Safe without locks: everything here runs on one asyncio event loop, so a dict
mutation is never interleaved with another task's.
"""

from __future__ import annotations

import uuid

from app.orchestrator.state import Run, SlackMessage

_runs: dict[uuid.UUID, Run] = {}

#: channel_id -> messages, oldest first. Kept independent of any run because
#: messages are captured as they arrive and only claimed by a run afterwards.
_messages: dict[str, list[SlackMessage]] = {}
#: (channel_id, ts) pairs already captured, so a Slack redelivery is dropped.
_seen_messages: set[tuple[str, str]] = set()


def add(run: Run) -> Run:
    _runs[run.id] = run
    return run


def get(run_id: uuid.UUID) -> Run | None:
    return _runs.get(run_id)


def list_runs() -> list[Run]:
    return sorted(_runs.values(), key=lambda r: r.created_at, reverse=True)


def active_run(channel_id: str, thread_ts: str | None) -> Run | None:
    """The most recent run for this conversation, if any."""
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
    """Store a captured message. Returns False if it is a Slack redelivery."""
    key = (message.channel_id, message.ts)
    if key in _seen_messages:
        return False
    _seen_messages.add(key)
    _messages.setdefault(message.channel_id, []).append(message)
    return True


def messages_for(channel_id: str, thread_ts: str | None) -> list[SlackMessage]:
    """Captured messages for a conversation, oldest first (insertion order)."""
    channel_messages = _messages.get(channel_id, [])
    if thread_ts is None:
        return list(channel_messages)
    return [m for m in channel_messages if m.thread_ts == thread_ts]


def message_count(channel_id: str) -> int:
    return len(_messages.get(channel_id, []))


def reset_channel(channel_id: str) -> None:
    """Drop captured messages for one channel, e.g. before re-seeding a demo."""
    for message in _messages.pop(channel_id, []):
        _seen_messages.discard((message.channel_id, message.ts))


def reset() -> None:
    """Clear all runtime state. Used by tests, never by the running app."""
    _runs.clear()
    _messages.clear()
    _seen_messages.clear()
