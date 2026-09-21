from __future__ import annotations

import pytest

from app.llm.client import LLMResult
from app.orchestrator import engine, store
from app.orchestrator.base import StageContext, StageFailed
from app.orchestrator.stages.ingest import IngestStage, format_conversation
from app.orchestrator.state import ArtifactKind, SlackMessage, StageKind
from app.schemas.requirements import Actor, Feature, Priority, Requirements

REQUIREMENTS = Requirements(
    project_name="Campus Event Booking",
    goal="Let students reserve seats at campus events and let organisers manage them.",
    actors=[
        Actor(name="Student", description="Browses events and reserves a seat"),
        Actor(name="Organiser", description="Creates events and reviews bookings"),
    ],
    features=[
        Feature(
            title="Browse events",
            description="Students see upcoming events",
            actor="Student",
            priority=Priority.MUST,
            source="Students should see what's on",
        ),
        Feature(
            title="Reserve a seat",
            description="Students reserve a seat at an event",
            actor="Student",
            priority=Priority.MUST,
            source="reserve a seat",
        ),
    ],
    non_functional=["Must work well on mobile browsers"],
    constraints=[],
    assumptions=["Students authenticate with their university account"],
    open_questions=["Is there a cap on seats per student?"],
    out_of_scope=["Payments"],
)


@pytest.fixture
def fake_llm(monkeypatch):
    captured = {}

    async def _generate(*, output_model, system, user, **kwargs):
        captured["system"] = system
        captured["user"] = user
        return LLMResult(
            data=REQUIREMENTS,
            raw_text="{}",
            model="fake",
            input_tokens=100,
            output_tokens=200,
            thought_tokens=10,
            duration_ms=5,
        )

    monkeypatch.setattr("app.orchestrator.stages.ingest.generate_structured", _generate)
    return captured


def test_transcript_keeps_speaker_names(conversation):
    text = format_conversation(conversation)
    assert text.startswith("priya: We need something for booking campus event seats")
    assert "omar: Students should see what's on" in text


def test_transcript_skips_empty_messages():
    messages = [
        SlackMessage(channel_id="C1", ts="1", user_name="a", text="real content"),
        SlackMessage(channel_id="C1", ts="2", user_name="b", text="   "),
    ]
    assert format_conversation(messages) == "a: real content"


async def test_extracts_requirements_and_names_the_run(conversation, fake_llm):
    run = await engine.create_run(title="Untitled project", slack_channel_id="C123")

    result = await IngestStage().run(StageContext(run=run))

    assert result.artifacts[0].kind == ArtifactKind.REQUIREMENTS
    assert result.artifacts[0].data["project_name"] == "Campus Event Booking"
    assert result.run_updates == {"title": "Campus Event Booking"}
    assert (result.input_tokens, result.output_tokens) == (100, 200)
    assert "2 features (2 must-have)" in result.summary


async def test_the_whole_conversation_reaches_the_prompt(conversation, fake_llm):
    run = await engine.create_run(slack_channel_id="C123")

    await IngestStage().run(StageContext(run=run))

    for _, text in [(m.user_name, m.text) for m in conversation]:
        assert text in fake_llm["user"]


async def test_bot_messages_are_excluded(conversation, fake_llm):
    store.capture_message(
        SlackMessage(
            channel_id="C123",
            ts="1700000999.000000",
            user_name="PM Agent",
            text="Here is the plan I generated earlier.",
            is_bot=True,
        )
    )

    run = await engine.create_run(slack_channel_id="C123")
    await IngestStage().run(StageContext(run=run))

    assert "Here is the plan I generated earlier" not in fake_llm["user"]


async def test_only_the_named_thread_is_used(fake_llm):
    store.capture_message(
        SlackMessage(
            channel_id="C123",
            ts="1",
            thread_ts="T1",
            user_name="a",
            text="In the thread: we want a booking system for campus events on mobile.",
        )
    )
    store.capture_message(
        SlackMessage(
            channel_id="C123",
            ts="2",
            thread_ts="T2",
            user_name="b",
            text="Different thread: lunch plans for Friday afternoon somewhere nearby.",
        )
    )

    run = await engine.create_run(slack_channel_id="C123", slack_thread_ts="T1")
    await IngestStage().run(StageContext(run=run))

    assert "In the thread" in fake_llm["user"]
    assert "Different thread" not in fake_llm["user"]


async def test_feedback_is_appended_to_the_prompt(conversation, fake_llm):
    run = await engine.create_run(slack_channel_id="C123")

    await IngestStage().run(
        StageContext(run=run, feedback="You missed the accessibility requirement")
    )

    assert "You missed the accessibility requirement" in fake_llm["user"]
    assert "asked for changes" in fake_llm["user"]


async def test_no_messages_gives_an_actionable_error(fake_llm):
    run = await engine.create_run(slack_channel_id="C-empty")

    with pytest.raises(StageFailed, match="Invite the bot"):
        await IngestStage().run(StageContext(run=run))


async def test_too_short_a_conversation_gives_an_actionable_error(fake_llm):
    store.capture_message(SlackMessage(channel_id="C123", ts="1", user_name="a", text="hi"))

    run = await engine.create_run(slack_channel_id="C123")

    with pytest.raises(StageFailed, match="barely any conversation"):
        await IngestStage().run(StageContext(run=run))


async def test_short_conversations_are_not_retried(fake_llm):
    store.capture_message(SlackMessage(channel_id="C123", ts="1", user_name="a", text="hi"))
    run = await engine.create_run(slack_channel_id="C123")

    with pytest.raises(StageFailed) as caught:
        await IngestStage().run(StageContext(run=run))

    assert caught.value.retryable is False


async def test_runs_end_to_end_through_the_engine(conversation, fake_llm, monkeypatch):
    monkeypatch.setattr(engine, "REGISTRY", {StageKind.INGEST: IngestStage()})

    run = await engine.create_run(slack_channel_id="C123")
    run = await engine.advance(run.id)

    ingest = next(s for s in run.stages if s.kind == StageKind.INGEST)
    assert ingest.status.value == "COMPLETE"
    assert run.title == "Campus Event Booking"
    assert len(run.artifacts) == 1
    assert run.artifacts[0].data["goal"].startswith("Let students reserve seats")
