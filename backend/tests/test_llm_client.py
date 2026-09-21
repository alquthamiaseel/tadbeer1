from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from app.llm import client as llm


class Answer(BaseModel):
    value: int


def _ok(text: str, *, finish_reason: str = "stop", refusal: str | None = None) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {"content": text, "refusal": refusal},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 22,
                "completion_tokens_details": {"reasoning_tokens": 3},
            },
        },
    )


def _fail(status: int, message: str = "boom") -> httpx.Response:
    return httpx.Response(status, json={"error": {"message": message, "code": status}})


class _FakeHttp:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.last_path = None
        self.last_json = None

    async def post(self, path, json=None):
        self.calls += 1
        self.last_path = path
        self.last_json = json
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def patch_client(monkeypatch):
    def install(outcomes):
        fake = _FakeHttp(outcomes)
        monkeypatch.setattr(llm, "get_client", lambda: fake)
        monkeypatch.setattr(llm.asyncio, "sleep", _noop_sleep)
        return fake

    return install


async def _noop_sleep(_seconds):
    return None


async def _generate(**overrides):
    return await llm.generate_structured(
        output_model=Answer, system="s", user="u", repair_attempts=0, **overrides
    )


async def test_retries_then_succeeds(patch_client):
    fake = patch_client([_fail(429), _fail(503), _ok('{"value": 7}')])

    result = await _generate()

    assert result.data.value == 7
    assert fake.calls == 3
    assert (result.input_tokens, result.output_tokens, result.thought_tokens) == (11, 22, 3)


async def test_network_errors_are_retried(patch_client):
    fake = patch_client([httpx.ConnectError("no route"), _ok('{"value": 1}')])

    result = await _generate()

    assert result.data.value == 1
    assert fake.calls == 2


async def test_a_persistent_rate_limit_raises_a_named_error(patch_client, monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_max_retries", 2)
    fake = patch_client([_fail(429), _fail(429), _fail(429)])

    with pytest.raises(llm.LLMQuotaError, match="rate limit"):
        await _generate()
    assert fake.calls == 3


async def test_no_quota_is_not_retried(patch_client):
    response = httpx.Response(
        429, json={"error": {"message": "You exceeded your quota", "code": "insufficient_quota"}}
    )
    fake = patch_client([response])

    with pytest.raises(llm.LLMQuotaError, match="no quota or credit"):
        await _generate()
    assert fake.calls == 1


async def test_a_bad_key_is_reported_clearly(patch_client):
    fake = patch_client([_fail(401, "No auth credentials found")])

    with pytest.raises(llm.LLMError, match="OPENAI_API_KEY"):
        await _generate()
    assert fake.calls == 1


async def test_an_unknown_model_points_at_llm_model(patch_client):
    patch_client([_fail(404, "The model does not exist")])

    with pytest.raises(llm.LLMError, match="LLM_MODEL"):
        await _generate()


async def test_other_client_errors_are_not_retried(patch_client):
    fake = patch_client([_fail(400, "bad request")])

    with pytest.raises(llm.LLMError, match="bad request"):
        await _generate()
    assert fake.calls == 1


async def test_invalid_output_is_repaired(patch_client):
    fake = patch_client([_ok("not json at all"), _ok('{"value": 3}')])

    result = await llm.generate_structured(
        output_model=Answer, system="s", user="u", repair_attempts=1
    )

    assert result.data.value == 3
    assert fake.calls == 2
    assert "did not satisfy the required schema" in fake.last_json["messages"][1]["content"]


async def test_unrepairable_output_raises(patch_client):
    patch_client([_ok("nope"), _ok("still nope")])

    with pytest.raises(llm.LLMOutputError, match="failed validation"):
        await llm.generate_structured(output_model=Answer, system="s", user="u", repair_attempts=1)


async def test_empty_output_is_reported_clearly(patch_client):
    patch_client([_ok("   ", finish_reason="length")])

    with pytest.raises(llm.LLMOutputError, match="max_output_tokens"):
        await _generate()


async def test_a_refusal_is_reported(patch_client):
    patch_client([_ok("x", refusal="I can't help with that")])

    with pytest.raises(llm.LLMOutputError, match="refused"):
        await _generate()


async def test_an_error_body_without_choices_is_reported(patch_client):
    patch_client([httpx.Response(200, json={"error": {"message": "provider down"}})])

    with pytest.raises(llm.LLMError, match="provider down"):
        await _generate()


async def test_request_shape(patch_client):
    fake = patch_client([_ok('{"value": 1}')])

    await llm.generate_structured(
        output_model=Answer,
        system="be helpful",
        user="do the thing",
        max_output_tokens=1234,
        model="gpt-4.1-mini",
        repair_attempts=0,
    )

    body = fake.last_json
    assert fake.last_path == "/chat/completions"
    assert body["model"] == "gpt-4.1-mini"
    assert body["messages"] == [
        {"role": "system", "content": "be helpful"},
        {"role": "user", "content": "do the thing"},
    ]
    assert body["max_completion_tokens"] == 1234
    assert "provider" not in body
    fmt = body["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["name"] == "Answer"
    schema = fmt["json_schema"]["schema"]
    assert schema["properties"]["value"]["type"] == "integer"
    assert schema["additionalProperties"] is False


async def test_the_default_model_comes_from_settings(patch_client, monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_model", "gpt-4o-mini")
    fake = patch_client([_ok('{"value": 1}')])

    result = await _generate()

    assert fake.last_json["model"] == "gpt-4o-mini"
    assert result.model == "gpt-4o-mini"


def test_a_missing_key_says_where_to_get_one(monkeypatch):
    monkeypatch.setattr(llm.settings, "openai_api_key", "")
    monkeypatch.setattr(llm, "_client", None)

    with pytest.raises(llm.LLMError, match="platform.openai.com/api-keys"):
        llm.get_client()


def test_the_client_uses_the_configured_key_and_base_url(monkeypatch):
    monkeypatch.setattr(llm.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(llm, "_client", None)

    client = llm.get_client()

    assert str(client.base_url).startswith("https://api.openai.com/v1")
    assert client.headers["Authorization"] == "Bearer sk-test"
    llm._client = None
