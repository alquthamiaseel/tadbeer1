"""Shared HTTP retry behaviour for the external integrations."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations.http import error_message, request_json
from app.orchestrator.base import StageFailed


@pytest.fixture(autouse=True)
def no_real_sleeping(monkeypatch):
    async def _sleep(_seconds):
        return None

    monkeypatch.setattr("app.integrations.http.asyncio.sleep", _sleep)


@respx.mock
async def test_a_rate_limit_is_retried_and_then_succeeds():
    route = respx.get("https://api.test/thing").mock(
        side_effect=[
            httpx.Response(429, headers={"retry-after": "1"}, json={"message": "slow down"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    async with httpx.AsyncClient() as client:
        body = await request_json(client, "GET", "https://api.test/thing", service="Test")

    assert body == {"ok": True}
    assert route.call_count == 2


@respx.mock
async def test_a_github_secondary_rate_limit_403_is_retried():
    """GitHub reports secondary rate limits as 403, not 429."""
    route = respx.get("https://api.test/thing").mock(
        side_effect=[
            httpx.Response(403, json={"message": "You have exceeded a secondary rate limit"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    async with httpx.AsyncClient() as client:
        await request_json(client, "GET", "https://api.test/thing", service="Test")
    assert route.call_count == 2


@respx.mock
async def test_a_permissions_403_is_not_retried():
    """A token missing a scope will never succeed; retrying just wastes the run."""
    route = respx.get("https://api.test/thing").mock(
        return_value=httpx.Response(403, json={"message": "Resource not accessible by token"})
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(StageFailed, match="not accessible"):
            await request_json(client, "GET", "https://api.test/thing", service="Test")
    assert route.call_count == 1


@respx.mock
async def test_a_client_error_fails_immediately_with_the_provider_message():
    respx.post("https://api.test/thing").mock(
        return_value=httpx.Response(402, json={"message": "premium workspace required"})
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(StageFailed, match="premium workspace required"):
            await request_json(client, "POST", "https://api.test/thing", service="Asana")


@respx.mock
async def test_persistent_server_errors_give_up_but_stay_retryable():
    respx.get("https://api.test/thing").mock(return_value=httpx.Response(503, text="unavailable"))
    async with httpx.AsyncClient() as client:
        with pytest.raises(StageFailed) as caught:
            await request_json(client, "GET", "https://api.test/thing", service="Test")
    assert caught.value.retryable is True


def test_error_message_digs_the_explanation_out_of_each_provider_shape():
    def response(payload):
        return httpx.Response(400, json=payload)

    assert "no workspace" in error_message(
        "Asana", response({"errors": [{"message": "no workspace"}]})
    )
    assert "bad ref" in error_message("GitHub", response({"message": "bad ref"}))
    assert "invalid" in error_message("Vercel", response({"error": {"message": "invalid"}}))
    assert "500" in error_message("Test", httpx.Response(500, text="boom"))
