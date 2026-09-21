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


async def check_llm() -> Result:
    if not settings.openai_api_key:
        return missing("OpenAI", "OPENAI_API_KEY")._with_hint(
            "Create a key at https://platform.openai.com/api-keys"
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
            max_output_tokens=200,
            repair_attempts=0,
        )
        return Result(
            "OpenAI",
            PASS,
            f"{settings.llm_model} responded "
            f"({result.input_tokens} in / {result.output_tokens} out tokens)",
        )
    except Exception as exc:
        return Result(
            "OpenAI",
            FAIL,
            _short(exc),
            f"Check OPENAI_API_KEY, your billing, and that LLM_MODEL={settings.llm_model} "
            "is a model your account can use",
        )


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
        except Exception as exc:
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
        except Exception as exc:
            results.append(Result("Slack app", FAIL, _short(exc)))

    return results


async def check_users_file() -> Result:
    try:
        from app import users_store

        path = users_store.users_path()
        if not path.exists():
            return Result(
                "Users file",
                WARN,
                f"{path} does not exist yet",
                "Run `python -m scripts.create_user --username alice --password ...`",
            )
        count = len(users_store._read())
        return Result("Users file", PASS, f"{path} ({count} user(s))")
    except Exception as exc:
        return Result("Users file", FAIL, _short(exc), "Check that the file is valid JSON")


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
    print("\n  pm-fyp credential check (Phase 1: OpenAI, Slack, users file)")

    llm_result, slack_results, db_result = await asyncio.gather(
        check_llm(),
        check_slack(),
        check_users_file(),
    )

    results = [llm_result, *slack_results, db_result]
    render(results)
    return 1 if any(r.status == FAIL for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
