"""Verify every credential Phase 1 needs before anything else runs.

    make check

Phase 1 runs only INGEST and PLAN (see STAGE_ORDER in app.orchestrator.state),
so this checks only what those need: Gemini, Slack, and the dashboard-login
database. Asana/GitHub/Vercel publishing has been removed from this build —
those stages still exist in the codebase for a later phase, but nothing here
checks credentials for services this build does not call.
"""

from __future__ import annotations

import asyncio

import httpx

from app.config import settings

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"

_COLOUR = {
    PASS: "\033[32m",
    FAIL: "\033[31m",
    WARN: "\033[33m",
    SKIP: "\033[90m",
}
_RESET = "\033[0m"

TIMEOUT = httpx.Timeout(20.0)


class Result:
    def __init__(self, service: str, status: str, detail: str, hint: str = "") -> None:
        self.service = service
        self.status = status
        self.detail = detail
        self.hint = hint

    def _with_hint(self, hint: str) -> Result:
        self.hint = hint
        return self


def missing(service: str, var: str) -> Result:
    return Result(service, FAIL, f"{var} is not set", f"Add {var} to .env (see .env.example)")


# --------------------------------------------------------------------------
# Gemini
#
# A real generation, not just an auth ping: on the free tier the failure that
# actually bites is a quota rejection, and only a generation surfaces that.
# --------------------------------------------------------------------------
async def check_gemini() -> Result:
    if not settings.gemini_api_key:
        return missing("Gemini", "GEMINI_API_KEY")._with_hint(
            "Get a free key at https://aistudio.google.com/apikey"
        )
    try:
        from pydantic import BaseModel

        from app.llm.client import generate_structured

        class Ping(BaseModel):
            ok: bool

        result = await generate_structured(
            output_model=Ping,
            system="You verify connectivity. Answer exactly as instructed.",
            user="Set ok to true.",
            max_output_tokens=2_000,
            effort="low",
            repair_attempts=0,
        )
        return Result(
            "Gemini",
            PASS,
            f"{settings.llm_model} responded "
            f"({result.input_tokens} in / {result.output_tokens} out tokens)",
        )
    except Exception as exc:  # noqa: BLE001 - the point is to report any failure
        return Result(
            "Gemini",
            FAIL,
            _short(exc),
            f"Check GEMINI_API_KEY and that LLM_MODEL={settings.llm_model} exists on the "
            "free tier — see https://aistudio.google.com/rate-limit",
        )


# --------------------------------------------------------------------------
# Slack — both tokens matter: the bot token posts, the app token opens the
# Socket Mode connection. A run fails at startup if either is wrong.
# --------------------------------------------------------------------------
async def check_slack() -> list[Result]:
    results: list[Result] = []

    if not settings.slack_bot_token:
        results.append(missing("Slack bot", "SLACK_BOT_TOKEN"))
    else:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.post(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
                )
                body = r.json()
            if body.get("ok"):
                results.append(
                    Result(
                        "Slack bot",
                        PASS,
                        f"{body.get('user')} in workspace {body.get('team')}",
                    )
                )
            else:
                results.append(
                    Result(
                        "Slack bot",
                        FAIL,
                        body.get("error", "unknown error"),
                        "SLACK_BOT_TOKEN should start with xoxb- "
                        "(OAuth & Permissions -> Bot User OAuth Token)",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            results.append(Result("Slack bot", FAIL, _short(exc)))

    if not settings.slack_app_token:
        results.append(missing("Slack app", "SLACK_APP_TOKEN"))
    else:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.post(
                    "https://slack.com/api/apps.connections.open",
                    headers={"Authorization": f"Bearer {settings.slack_app_token}"},
                )
                body = r.json()
            if body.get("ok"):
                results.append(Result("Slack app", PASS, "Socket Mode connection available"))
            else:
                results.append(
                    Result(
                        "Slack app",
                        FAIL,
                        body.get("error", "unknown error"),
                        "SLACK_APP_TOKEN should start with xapp- and have the "
                        "connections:write scope (Basic Information -> App-Level Tokens)",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            results.append(Result("Slack app", FAIL, _short(exc)))

    return results


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
async def check_database() -> Result:
    try:
        from sqlalchemy import text

        from app.db import engine

        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        return Result("Database", PASS, settings.database_url.split("@")[-1])
    except Exception as exc:  # noqa: BLE001
        return Result(
            "Database",
            FAIL,
            _short(exc),
            "Run `make db` to start Postgres",
        )


# --------------------------------------------------------------------------
# Presentation
# --------------------------------------------------------------------------
def _short(exc: Exception, limit: int = 120) -> str:
    text = " ".join(str(exc).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _body(response: httpx.Response, limit: int = 120) -> str:
    text = " ".join(response.text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render(results: list[Result]) -> None:
    width = max(len(r.service) for r in results)
    print()
    for r in results:
        colour = _COLOUR[r.status]
        print(f"  {colour}{r.status:<4}{_RESET}  {r.service:<{width}}  {r.detail}")
        if r.hint:
            print(f"        {' ' * width}  \033[90m{r.hint}{_RESET}")
    print()

    failures = [r for r in results if r.status == FAIL]
    warnings = [r for r in results if r.status == WARN]
    if failures:
        print(f"  \033[31m{len(failures)} check(s) failed.\033[0m Fix these before continuing.\n")
    elif warnings:
        print(f"  \033[33mAll required checks passed, {len(warnings)} warning(s).\033[0m\n")
    else:
        print("  \033[32mAll checks passed.\033[0m\n")


async def main() -> int:
    print("\n  pm-fyp credential check (Phase 1: Gemini, Slack, database)")

    gemini_result, slack_results, db_result = await asyncio.gather(
        check_gemini(),
        check_slack(),
        check_database(),
    )

    results = [gemini_result, *slack_results, db_result]
    render(results)
    return 1 if any(r.status == FAIL for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
