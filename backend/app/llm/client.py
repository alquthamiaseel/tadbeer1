"""Gemini client.

Every pipeline stage is a single call through :func:`generate_structured`: a
system prompt, a user prompt, and a Pydantic model describing the expected
output. Generation is constrained to that model's schema, so a stage receives a
validated object rather than prose it has to parse. This is the main reason the
pipeline is debuggable — a stage either produces a valid artifact or raises.

Two things here exist because of the free tier. Requests are retried with
exponential backoff on 429 and 5xx, because free-tier quota is per-minute and a
six-stage run can trip it. And the thinking level is configurable per call, so
cheap stages don't burn reasoning tokens that count against the same quota.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass

from google import genai
from pydantic import BaseModel, ValidationError

from app import audit
from app.config import settings
from app.llm.schema import to_response_format

log = logging.getLogger(__name__)

#: Effort names used across the app, mapped to Gemini thinking levels.
THINKING_LEVELS = {
    "low": "LOW",
    "medium": "MEDIUM",
    "high": "HIGH",
    "xhigh": "HIGH",
    "max": "HIGH",
    "minimal": "MINIMAL",
}

_RETRY_STATUSES = {429, 500, 502, 503, 504}


def _is_transient(exc: Exception) -> bool:
    """Whether this failure is worth trying again.

    An error with no HTTP status never reached the service — the connection
    dropped, or timed out. Those are the most retryable failures there are, and
    treating them as fatal is what made a run die on "Server disconnected
    without sending a response". Everything the API itself rejects arrives with
    a status: a bad key is 401, an exhausted quota is 429.
    """
    status = _status_of(exc)
    return status is None or status in _RETRY_STATUSES


def _api_error_types() -> tuple[type[Exception], ...]:
    """The exception classes the Interactions API actually raises.

    Deliberately defensive. The Interactions API raises from an internal module
    whose errors are *not* subclasses of the public ``google.genai.errors``
    hierarchy, so catching only the public one silently disables every retry
    below — quota failures would propagate raw on the first 429. Both are
    collected, and the private one is optional so an SDK reshuffle degrades to
    "no retries" rather than an ImportError at startup.
    """
    types: list[type[Exception]] = []
    try:
        from google.genai._gaos.lib.compat_errors import APIError as _InternalAPIError

        types.append(_InternalAPIError)
    except ImportError:  # pragma: no cover - depends on SDK internals
        log.warning("google-genai internal error types not found; retries may not fire")
    try:
        from google.genai.errors import APIError as _PublicAPIError

        types.append(_PublicAPIError)
    except ImportError:  # pragma: no cover
        pass
    return tuple(types) or (Exception,)


API_ERRORS = _api_error_types()


class LLMError(RuntimeError):
    """Base class for LLM failures."""


class LLMOutputError(LLMError):
    """The model returned output that does not satisfy the stage's schema."""


class LLMQuotaError(LLMError):
    """Free-tier quota is exhausted and retrying did not help."""


@dataclass
class LLMResult[TModel: BaseModel]:
    data: TModel
    raw_text: str
    model: str
    input_tokens: int
    output_tokens: int
    thought_tokens: int
    duration_ms: int


_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise LLMError(
                "GEMINI_API_KEY is not set. Get a free key at "
                "https://aistudio.google.com/apikey and put it in .env"
            )
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _thinking_level(effort: str) -> str:
    return THINKING_LEVELS.get(effort.lower(), "HIGH")


def _status_of(exc: Exception) -> int | None:
    """HTTP status from an SDK error, whichever hierarchy it came from."""
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


async def _create(
    *,
    model: str,
    system: str,
    user: str,
    max_output_tokens: int,
    effort: str,
    response_format: dict | None,
) -> tuple[object, int]:
    """One API call, with backoff on quota and transient server errors."""
    generation_config: dict = {
        "max_output_tokens": max_output_tokens,
        "thinking_config": {"thinking_level": _thinking_level(effort)},
    }

    kwargs: dict = {
        "model": model,
        "system_instruction": system,
        "input": user,
        "generation_config": generation_config,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format

    started = time.perf_counter()
    last_exc: Exception | None = None

    for attempt in range(settings.llm_max_retries + 1):
        try:
            interaction = await get_client().aio.interactions.create(**kwargs)
            break
        except API_ERRORS as exc:
            status = _status_of(exc)
            if not _is_transient(exc) or attempt == settings.llm_max_retries:
                if status == 429:
                    raise LLMQuotaError(
                        "Gemini free-tier quota exhausted. Wait for the per-minute "
                        "window to reset, or set LLM_MODEL to a lighter model."
                    ) from exc
                raise
            last_exc = exc
            # Full jitter: spreads retries out instead of synchronising them.
            delay = random.uniform(0, min(2**attempt, 30))
            log.warning(
                "Gemini call failed (%s), retrying in %.1fs (attempt %d/%d)",
                status or type(exc).__name__,
                delay,
                attempt + 1,
                settings.llm_max_retries,
            )
            await asyncio.sleep(delay)
    else:  # pragma: no cover - the loop always breaks or raises
        raise LLMError(f"Gemini call failed after retries: {last_exc}")

    duration_ms = int((time.perf_counter() - started) * 1000)

    if getattr(interaction, "errors", None):
        detail = "; ".join(str(e) for e in interaction.errors)
        raise LLMError(f"Gemini reported errors on the interaction: {detail}")

    text = interaction.output_text or ""
    if not text.strip():
        raise LLMOutputError(
            f"Gemini returned no text (status={getattr(interaction, 'status', None)}). "
            "This usually means max_output_tokens was too small for the thinking "
            "budget plus the answer."
        )

    return interaction, duration_ms


def _usage(interaction) -> tuple[int, int, int]:
    usage = getattr(interaction, "usage", None)
    if usage is None:
        return 0, 0, 0
    return (
        usage.total_input_tokens or 0,
        usage.total_output_tokens or 0,
        usage.total_thought_tokens or 0,
    )


async def generate_structured[TModel: BaseModel](
    *,
    output_model: type[TModel],
    system: str,
    user: str,
    max_output_tokens: int = 16_000,
    model: str | None = None,
    effort: str | None = None,
    repair_attempts: int = 1,
) -> LLMResult[TModel]:
    """Run one schema-constrained generation and return the validated object.

    ``output_model`` doubles as the contract and the validator: it is converted
    to a schema generation is constrained to, then used to validate what comes
    back. If validation still fails — on a constraint the API cannot enforce,
    such as a value range — the model is asked to repair its own output.
    """
    model = model or settings.llm_model
    effort = effort or settings.llm_effort
    response_format = to_response_format(output_model)

    prompt = user
    last_error: Exception | None = None

    for attempt in range(repair_attempts + 1):
        interaction, duration_ms = await _create(
            model=model,
            system=system,
            user=prompt,
            max_output_tokens=max_output_tokens,
            effort=effort,
            response_format=response_format,
        )
        text = interaction.output_text or ""

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

        input_tokens, output_tokens, thought_tokens = _usage(interaction)
        audit.record_llm(
            model=model,
            ok=True,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thought_tokens=thought_tokens,
            output_model=output_model.__name__,
        )
        return LLMResult(
            data=data,
            raw_text=text,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thought_tokens=thought_tokens,
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


async def generate_text(
    *,
    system: str,
    user: str,
    max_output_tokens: int = 4_000,
    model: str | None = None,
    effort: str | None = None,
) -> LLMResult[BaseModel]:
    """Unconstrained generation, for prose destined straight for a human."""

    class _Text(BaseModel):
        text: str

    interaction, duration_ms = await _create(
        model=model or settings.llm_model,
        system=system,
        user=user,
        max_output_tokens=max_output_tokens,
        effort=effort or settings.llm_effort,
        response_format=None,
    )
    text = interaction.output_text or ""
    input_tokens, output_tokens, thought_tokens = _usage(interaction)
    return LLMResult(
        data=_Text(text=text),
        raw_text=text,
        model=model or settings.llm_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        thought_tokens=thought_tokens,
        duration_ms=duration_ms,
    )


def pretty(data: BaseModel) -> str:
    """Compact JSON of a model, for embedding one stage's output in the next prompt."""
    return json.dumps(data.model_dump(mode="json"), indent=2, ensure_ascii=False)
