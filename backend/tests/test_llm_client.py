"""Retry and error handling in the Gemini client.

The retry path matters more than usual here: the project runs on Gemini's free
tier, where quota is enforced per minute and a six-stage run can trip it. These
tests exist because the Interactions API raises from an internal module whose
errors are not subclasses of the public `google.genai.errors` hierarchy — so
catching the obvious public class silently disables every retry, and the failure
only shows up as a dead run under quota pressure.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.llm import client as llm


class Answer(BaseModel):
    value: int


def _interaction(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        output_text=text,
        errors=None,
        status="OK",
        usage=SimpleNamespace(
            total_input_tokens=11,
            total_output_tokens=22,
            total_thought_tokens=3,
        ),
    )


def _raise(status: int) -> Exception:
    """An error shaped like the ones the Interactions API really raises."""
    exc = llm.API_ERRORS[0].__new__(llm.API_ERRORS[0])
    Exception.__init__(exc, f"HTTP {status}")
    exc.status_code = status
    return exc


class _FakeInteractions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def patch_client(monkeypatch):
    def install(outcomes):
        fake = _FakeInteractions(outcomes)
        monkeypatch.setattr(
            llm,
            "get_client",
            lambda: SimpleNamespace(aio=SimpleNamespace(interactions=fake)),
        )
        # Don't actually sleep through the backoff.
        monkeypatch.setattr(llm.asyncio, "sleep", _noop_sleep)
        return fake

    return install


async def _noop_sleep(_seconds):
    return None


async def test_the_internal_error_hierarchy_is_the_one_we_catch():
    """If this fails, every retry below is dead code."""
    from google.genai._gaos.lib.compat_errors import RateLimitError

    assert issubclass(RateLimitError, llm.API_ERRORS)


async def test_retries_then_succeeds(patch_client):
    fake = patch_client([_raise(429), _raise(503), _interaction('{"value": 7}')])

    result = await llm.generate_structured(
        output_model=Answer, system="s", user="u", repair_attempts=0
    )

    assert result.data.value == 7
    assert fake.calls == 3
    assert (result.input_tokens, result.output_tokens) == (11, 22)


async def test_exhausted_quota_raises_a_named_error(patch_client, monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_max_retries", 2)
    patch_client([_raise(429), _raise(429), _raise(429)])

    with pytest.raises(llm.LLMQuotaError, match="quota"):
        await llm.generate_structured(output_model=Answer, system="s", user="u", repair_attempts=0)


async def test_client_errors_are_not_retried(patch_client):
    """A 400 is a bug in the request; retrying it just wastes quota."""
    fake = patch_client([_raise(400)])

    with pytest.raises(Exception):  # noqa: B017 - the SDK's own error type
        await llm.generate_structured(output_model=Answer, system="s", user="u", repair_attempts=0)
    assert fake.calls == 1


async def test_invalid_output_is_repaired(patch_client):
    fake = patch_client([_interaction("not json at all"), _interaction('{"value": 3}')])

    result = await llm.generate_structured(
        output_model=Answer, system="s", user="u", repair_attempts=1
    )

    assert result.data.value == 3
    assert fake.calls == 2
    # The repair prompt must show the model what it got wrong.
    assert "did not satisfy the required schema" in fake.last_kwargs["input"]


async def test_unrepairable_output_raises(patch_client):
    patch_client([_interaction("nope"), _interaction("still nope")])

    with pytest.raises(llm.LLMOutputError, match="failed validation"):
        await llm.generate_structured(output_model=Answer, system="s", user="u", repair_attempts=1)


async def test_empty_output_is_reported_clearly(patch_client):
    """Silent truncation is the confusing failure; name it instead."""
    patch_client([_interaction("   ")])

    with pytest.raises(llm.LLMOutputError, match="max_output_tokens"):
        await llm.generate_structured(output_model=Answer, system="s", user="u", repair_attempts=0)


async def test_request_shape(patch_client):
    fake = patch_client([_interaction('{"value": 1}')])

    await llm.generate_structured(
        output_model=Answer,
        system="be helpful",
        user="do the thing",
        effort="low",
        max_output_tokens=1234,
        repair_attempts=0,
    )

    kwargs = fake.last_kwargs
    assert kwargs["system_instruction"] == "be helpful"
    assert kwargs["input"] == "do the thing"
    assert kwargs["generation_config"]["max_output_tokens"] == 1234
    assert kwargs["generation_config"]["thinking_config"]["thinking_level"] == "LOW"
    assert kwargs["response_format"]["mime_type"] == "application/json"
    assert kwargs["response_format"]["schema"]["properties"]["value"]["type"] == "integer"
