"""Slack message capture and reporting.

The capture rules decide what the pipeline treats as requirements, so getting
them wrong corrupts every downstream stage with join notices and the agent's own
posts. Deduplication matters because Slack redelivers events — without it a
redelivered message appears twice in the transcript and gets double weight.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.integrations import slack
from app.orchestrator import engine, store
from app.orchestrator.state import RunStatus, Stage, StageKind, StageStatus


class FakeClient:
    """Stands in for the Slack web client."""

    def __init__(self, names: dict[str, str] | None = None):
        self.names = names or {}
        self.posted: list[dict] = []
        self.users_info_calls = 0

    async def users_info(self, user: str):
        self.users_info_calls += 1
        if user not in self.names:
            from slack_sdk.errors import SlackApiError

            raise SlackApiError("user_not_found", SimpleNamespace(data={}))
        return {"user": {"profile": {"display_name": self.names[user]}}}

    async def chat_postMessage(self, channel: str, text: str, thread_ts=None, blocks=None):
        self.posted.append(
            {"channel": channel, "text": text, "thread_ts": thread_ts, "blocks": blocks}
        )
        return {"ok": True}


@pytest.fixture(autouse=True)
def _reset_name_cache(monkeypatch):
    monkeypatch.setattr(slack, "_NAME_CACHE", {})


def _event(**overrides) -> dict:
    return {
        "channel": "C123",
        "ts": "1700000001.000100",
        "user": "U1",
        "text": "We need a booking system for campus events.",
    } | overrides


async def test_captures_a_normal_message():
    client = FakeClient({"U1": "priya"})

    assert await slack.capture_message(_event(), client) is True

    stored = store.messages_for("C123", None)
    assert len(stored) == 1
    assert stored[0].user_name == "priya"
    assert stored[0].text.startswith("We need a booking system")


async def test_ignores_the_agents_own_posts():
    """Otherwise the agent's plans become requirements on the next run."""
    client = FakeClient()

    assert await slack.capture_message(_event(bot_id="B1"), client) is False
    assert await slack.capture_message(_event(subtype="bot_message"), client) is False

    assert store.messages_for("C123", None) == []


@pytest.mark.parametrize("subtype", ["channel_join", "message_changed", "message_deleted"])
async def test_ignores_non_conversation_subtypes(subtype):
    client = FakeClient()
    assert await slack.capture_message(_event(subtype=subtype), client) is False


async def test_ignores_empty_messages():
    client = FakeClient()
    assert await slack.capture_message(_event(text="   "), client) is False


async def test_redelivered_messages_are_not_stored_twice():
    """Slack redelivers events; the transcript must not double-count them."""
    client = FakeClient({"U1": "priya"})
    event = _event()

    assert await slack.capture_message(event, client) is True
    assert await slack.capture_message(event, client) is False

    assert len(store.messages_for("C123", None)) == 1


async def test_thread_messages_keep_their_thread():
    client = FakeClient({"U1": "priya"})

    await slack.capture_message(_event(thread_ts="1699999999.000000"), client)

    stored = store.messages_for("C123", None)[0]
    assert stored.thread_ts == "1699999999.000000"


async def test_user_names_are_resolved_once():
    """users.info is rate-limited and the same people speak throughout."""
    client = FakeClient({"U1": "priya"})

    await slack.capture_message(_event(ts="1.1"), client)
    await slack.capture_message(_event(ts="1.2"), client)

    assert client.users_info_calls == 1


async def test_an_unresolvable_user_still_captures_the_message():
    """A missing name must not lose the content."""
    client = FakeClient(names={})

    assert await slack.capture_message(_event(user="U-unknown"), client) is True

    stored = store.messages_for("C123", None)[0]
    assert stored.user_name == "U-unknown"


# --- reporting -------------------------------------------------------------


async def test_describe_reports_a_failure_with_its_cause():
    run = await engine.create_run(title="Campus Booking")
    stage = next(s for s in run.stages if s.kind.value == "INGEST")
    stage.status = StageStatus.FAILED
    stage.error = "There is barely any conversation here (12 characters)."

    text = slack.describe(run)

    assert ":x:" in text
    assert "INGEST" in text
    assert "barely any conversation" in text


async def test_describe_asks_for_review_when_gated():
    run = await engine.create_run(title="Campus Booking")
    next(s for s in run.stages if s.kind.value == "INGEST").status = StageStatus.COMPLETE
    next(s for s in run.stages if s.kind.value == "PLAN").status = StageStatus.AWAITING_APPROVAL

    text = slack.describe(run)

    assert "PLAN" in text
    assert "ready for your review" in text
    assert "1 of 2 stages complete" in text


async def test_describe_lists_artifacts_when_finished():
    run = await engine.create_run(title="Campus Booking")
    run.status = RunStatus.COMPLETE
    run.asana_project_url = "https://app.asana.com/0/1/2"
    run.vercel_url = "https://demo.vercel.app"

    text = slack.describe(run)

    assert ":white_check_mark:" in text
    assert "https://app.asana.com/0/1/2" in text
    assert "https://demo.vercel.app" in text
    # GitHub was never produced, so it must not appear as an empty link.
    assert "GitHub" not in text


async def test_starting_a_second_run_in_the_same_channel_is_refused():
    """Two concurrent runs would both claim the same conversation."""
    run = await engine.create_run(slack_channel_id="C123")
    run.status = RunStatus.RUNNING

    client = FakeClient()
    await slack._start("C123", None, {"user_name": "priya"}, client)

    assert len(client.posted) == 1
    assert "already in progress" in client.posted[0]["text"]
    # No second run was created.
    assert len(store.list_runs()) == 1


async def test_status_with_no_run_says_so():
    client = FakeClient()
    await slack._status("C-empty", None, client)
    assert "No runs here yet" in client.posted[0]["text"]


# --- failure reporting -----------------------------------------------------


def test_a_dead_database_names_the_fix():
    """The failure a user actually hits, and the one Slack hides worst."""
    text = slack.explain_failure(ConnectionRefusedError(111, "Connect call failed"))
    assert "cannot reach my database" in text
    assert "make db" in text


def test_exhausted_quota_says_to_wait():
    text = slack.explain_failure(RuntimeError("Gemini free-tier quota exhausted"))
    assert "quota" in text
    assert "Wait a minute" in text


def test_an_unknown_failure_still_shows_the_error():
    text = slack.explain_failure(ValueError("something obscure"))
    assert "ValueError" in text
    assert "something obscure" in text


async def test_a_failing_command_reports_into_slack_instead_of_timing_out(monkeypatch):
    """Otherwise the user sees Slack's generic 'app did not respond' and nothing else."""
    registered = {}

    class _App:
        def command(self, name):
            def deco(fn):
                registered[name] = fn
                return fn

            return deco

        def event(self, name):
            def deco(fn):
                return fn

            return deco

        def action(self, name):
            return self.event(name)

        def view(self, name):
            return self.event(name)

    slack.register(_App())

    async def _boom(*args, **kwargs):
        raise ConnectionRefusedError(111, "Connect call failed")

    monkeypatch.setattr(slack, "_start", _boom)

    client = FakeClient()
    acked = []

    async def ack():
        acked.append(True)

    async def respond(text):
        pass

    await registered["/pm"](
        ack=ack,
        command={"text": "start", "channel_id": "C1"},
        client=client,
        respond=respond,
    )

    assert acked, "the command must still be acknowledged"
    assert "cannot reach my database" in client.posted[0]["text"]


# --- not in channel --------------------------------------------------------


class RefusingClient(FakeClient):
    """A workspace where the bot has not been invited to the channel."""

    async def chat_postMessage(self, channel: str, text: str, thread_ts=None, blocks=None):
        from slack_sdk.errors import SlackApiError

        raise SlackApiError("not_in_channel", {"ok": False, "error": "not_in_channel"})


async def test_posting_without_membership_raises_rather_than_logging():
    """The user never reads the log, so this failure must not be swallowed."""
    with pytest.raises(slack.NotInChannel):
        await slack.post(RefusingClient(), "C1", "hello")


async def test_no_run_is_created_when_the_bot_cannot_post():
    """A junk failed run for a problem that is not the run's."""
    with pytest.raises(slack.NotInChannel):
        await slack._start("C1", None, {"user_name": "priya"}, RefusingClient())

    assert store.list_runs() == []


async def test_the_invite_instruction_reaches_the_user_privately():
    """chat.postMessage cannot work here, so the reply goes over response_url."""
    registered = {}

    class _App:
        def command(self, name):
            def deco(fn):
                registered[name] = fn
                return fn

            return deco

        def event(self, name):
            def deco(fn):
                return fn

            return deco

        def action(self, name):
            return self.event(name)

        def view(self, name):
            return self.event(name)

    slack.register(_App())

    responded = []

    async def ack():
        pass

    async def respond(text):
        responded.append(text)

    await registered["/pm"](
        ack=ack,
        command={"text": "start", "channel_id": "C1"},
        client=RefusingClient(),
        respond=respond,
    )

    assert responded, "the user must be told something"
    assert "/invite @PM Agent" in responded[0]


async def test_an_empty_channel_explains_itself_before_running():
    """Better than letting INGEST fail with the same diagnosis a minute later."""
    client = FakeClient()
    await slack._start("C-empty", None, {"user_name": "priya"}, client)

    assert "have not seen any conversation" in client.posted[0]["text"]
    assert store.list_runs() == []


# --- progress reporting through a long run ---------------------------------


async def test_each_completed_stage_is_narrated_into_the_channel(monkeypatch):
    """A full run takes minutes; silence in the channel looks like a crash."""
    posted: list[str] = []

    async def _post(client, channel, text, thread_ts=None):
        posted.append(text)

    monkeypatch.setattr(slack, "post", _post)

    run = await engine.create_run(title="Campus")
    reporter = slack._progress_reporter(client=None, channel="C1", thread_ts=None)

    stages = [
        next(s for s in run.stages if s.kind == kind)
        for kind in (StageKind.INGEST, StageKind.PLAN)
    ]
    # WBS is not part of a Phase 1 run's stages, but the narration code path for
    # it still exists for a later phase — exercise it with a synthetic stage.
    stages.append(Stage(kind=StageKind.WBS, position=99))

    for stage in stages:
        stage.status = StageStatus.COMPLETE
        await reporter(run, stage)

    assert len(posted) == 3
    assert "requirements" in posted[0]
    assert "Asana" in posted[2]


async def test_a_failed_stage_is_not_narrated_twice(monkeypatch):
    """The failure is reported once, by the caller, with the actual error."""
    posted: list[str] = []

    async def _post(client, channel, text, thread_ts=None):
        posted.append(text)

    monkeypatch.setattr(slack, "post", _post)

    run = await engine.create_run(title="Campus")
    stage = Stage(kind=StageKind.WBS, position=99, status=StageStatus.FAILED)

    await slack._progress_reporter(client=None, channel="C1", thread_ts=None)(run, stage)

    assert posted == []


async def test_a_broken_reporter_cannot_fail_the_run():
    """Reporting is a courtesy; it must never take a run down with it."""

    async def _explode(run, stage):
        raise RuntimeError("Slack is down")

    class _Fine:
        kind = StageKind.INGEST

        async def run(self, ctx):
            from app.orchestrator.base import StageResult

            return StageResult(summary="fine")

    original = engine.REGISTRY
    engine.REGISTRY = {StageKind.INGEST: _Fine()}
    try:
        run = await engine.create_run(title="Campus")
        run = await engine.advance(run.id, on_stage=_explode)
    finally:
        engine.REGISTRY = original

    assert next(s for s in run.stages if s.kind == StageKind.INGEST).status == StageStatus.COMPLETE
