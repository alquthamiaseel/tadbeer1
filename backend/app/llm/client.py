from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ValidationError

from app import audit
from app.config import settings
from app.llm.schema import to_response_format

log = logging.getLogger(__name__)

_RETRY_STATUSES = {408, 429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    pass


class LLMOutputError(LLMError):
    pass


class LLMQuotaError(LLMError):
    pass


@dataclass
class LLMResult[TModel: BaseModel]:
    data: TModel
    raw_text: str
    model: str
    input_tokens: int
    output_tokens: int
    thought_tokens: int
    duration_ms: int


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    thought_tokens: int


_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        if not settings.openai_api_key:
            raise LLMError(
                "OPENAI_API_KEY is not set. Create a key at "
                "https://platform.openai.com/api-keys and put it in .env"
            )
        _client = httpx.AsyncClient(
            base_url=settings.openai_base_url,
            timeout=httpx.Timeout(180.0, connect=15.0),
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
        )
    return _client


def _error_info(response: httpx.Response) -> tuple[str, str | None]:
    try:
        error = response.json().get("error")
    except ValueError:
        error = None
    if isinstance(error, dict):
        return str(error.get("message") or error)[:300], error.get("code")
    if error:
        return str(error)[:300], None
    return response.text[:300] or f"HTTP {response.status_code}", None


async def _create(
    *,
    model: str,
    system: str,
    user: str,
    max_output_tokens: int,
    response_format: dict | None,
) -> tuple[Completion, int]:
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_completion_tokens": max_output_tokens,
    }
    if response_format is not None:
        payload["response_format"] = response_format

    started = time.perf_counter()
    body: dict | None = None

    for attempt in range(settings.llm_max_retries + 1):
        status: int | None = None
        code: str | None = None
        try:
            response = await get_client().post("/chat/completions", json=payload)
            status = response.status_code
            if status < 400:
                try:
                    body = response.json()
                except ValueError as exc:
                    raise LLMError(f"OpenAI returned a non-JSON response: {exc}") from exc
                break
            detail, code = _error_info(response)
        except httpx.TransportError as exc:
            detail = f"{type(exc).__name__}: {exc}"

        if status in (401, 403):
            raise LLMError(f"OpenAI rejected the API key ({detail}). Check OPENAI_API_KEY.")
        if status == 402 or code == "insufficient_quota":
            raise LLMQuotaError(
                f"OpenAI reports no quota or credit left ({detail}). "
                "Add billing at https://platform.openai.com/settings/organization/billing."
            )
        if status == 404:
            raise LLMError(f"OpenAI cannot serve model {model!r} ({detail}). Check LLM_MODEL.")

        transient = status is None or status in _RETRY_STATUSES
        if not transient or attempt == settings.llm_max_retries:
            if status == 429:
                raise LLMQuotaError(
                    f"OpenAI rate limit reached and retries did not help ({detail}). "
                    "Wait a minute, or set LLM_MODEL to a different model."
                )
            raise LLMError(f"OpenAI call failed ({status or 'network'}): {detail}")

        delay = random.uniform(0, min(2**attempt, 30))
        log.warning(
            "OpenAI call failed (%s), retrying in %.1fs (attempt %d/%d)",
            status or "network",
            delay,
            attempt + 1,
            settings.llm_max_retries,
        )
        await asyncio.sleep(delay)

    if body is None:
        raise LLMError("OpenAI call failed after retries")

    duration_ms = int((time.perf_counter() - started) * 1000)

    choices = body.get("choices") or []
    if not choices:
        raise LLMError(f"OpenAI returned no choices: {body.get('error') or body}")

    choice = choices[0]
    message = choice.get("message") or {}
    if message.get("refusal"):
        raise LLMOutputError(f"The model refused the request: {message['refusal']}")

    text = message.get("content") or ""
    if not text.strip():
        raise LLMOutputError(
            f"The model returned no text (finish_reason={choice.get('finish_reason')}). "
            "This usually means max_output_tokens was too small for the answer."
        )

    usage = body.get("usage") or {}
    details = usage.get("completion_tokens_details") or {}
    return (
        Completion(
            text=text,
            input_tokens=usage.get("prompt_tokens") or 0,
            output_tokens=usage.get("completion_tokens") or 0,
            thought_tokens=details.get("reasoning_tokens") or 0,
        ),
        duration_ms,
    )


async def generate_structured[TModel: BaseModel](
    *,
    output_model: type[TModel],
    system: str,
    user: str,
    max_output_tokens: int = 16_000,
    model: str | None = None,
    repair_attempts: int = 1,
) -> LLMResult[TModel]:
    model = model or settings.llm_model
    response_format = to_response_format(output_model)

    prompt = user
    last_error: Exception | None = None

    for attempt in range(repair_attempts + 1):
        completion, duration_ms = await _create(
            model=model,
            system=system,
            user=prompt,
            max_output_tokens=max_output_tokens,
            response_format=response_format,
        )
        text = completion.text

        try:
            data = output_model.model_validate_json(text)
        except ValidationError as exc:
            last_error = exc
            log.warning(
                "%s output failed validation (attempt %d/%d): %s",
                output_model.__name__,
                attempt + 1,
                repair_attempts + 1,
                exc,
            )
            prompt = (
                f"{user}\n\n"
                "Your previous response did not satisfy the required schema.\n"
                f"Response:\n{text}\n\n"
                f"Validation errors:\n{exc}\n\n"
                "Produce a corrected response that satisfies the schema exactly."
            )
            continue

        audit.record_llm(
            model=model,
            ok=True,
            duration_ms=duration_ms,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            thought_tokens=completion.thought_tokens,
            output_model=output_model.__name__,
        )
        return LLMResult(
            data=data,
            raw_text=text,
            model=model,
            input_tokens=completion.input_tokens,
            output_tokens=completion.output_tokens,
            thought_tokens=completion.thought_tokens,
            duration_ms=duration_ms,
        )

    audit.record_llm(
        model=model,
        ok=False,
        duration_ms=0,
        output_model=output_model.__name__,
        error=str(last_error)[:500],
    )
    raise LLMOutputError(
        f"{output_model.__name__} output failed validation after "
        f"{repair_attempts + 1} attempts: {last_error}"
    ) from last_error


def pretty(data: BaseModel) -> str:
    return json.dumps(data.model_dump(mode="json"), indent=2, ensure_ascii=False)
