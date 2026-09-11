"""Verify every external credential before anything else runs.

    make check              # fast: read-only probes against all five APIs
    make check ARGS=--deep  # also proves Asana can actually link dependencies

The deep check exists because of a specific trap: **Asana task dependencies
require a paid workspace tier**, and the free tier fails at the point of linking
rather than at authentication. A read-only probe cannot tell the difference, so
the deep check creates a throwaway project, links two tasks, and deletes it.
Run it once on day one — finding this out on the day you build the WBS stage is
a lost day.
"""

from __future__ import annotations

import asyncio
import sys

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
# Asana
# --------------------------------------------------------------------------
ASANA = "https://app.asana.com/api/1.0"


def _asana_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.asana_access_token}"}


async def check_asana(deep: bool) -> list[Result]:
    if not settings.asana_enabled:
        # A deliberate choice, not a missing credential. Reporting it as a
        # failure would train you to ignore a red line in this table.
        return [
            Result(
                "Asana",
                SKIP,
                "ASANA_ENABLED is false — the WBS is built and stored, but not published",
            )
        ]
    if not settings.asana_access_token:
        return [missing("Asana", "ASANA_ACCESS_TOKEN")]

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=_asana_headers()) as client:
            r = await client.get(f"{ASANA}/users/me", params={"opt_fields": "name,workspaces.name"})
            if r.status_code != 200:
                return [
                    Result(
                        "Asana",
                        FAIL,
                        f"HTTP {r.status_code}: {_body(r)}",
                        "Generate a personal access token at https://app.asana.com/0/my-apps",
                    )
                ]
            me = r.json()["data"]
    except Exception as exc:  # noqa: BLE001
        return [Result("Asana", FAIL, _short(exc))]

    workspaces = me.get("workspaces", [])
    results = [
        Result(
            "Asana",
            PASS,
            f"{me.get('name')} — {len(workspaces)} workspace(s)",
        )
    ]

    if not settings.asana_workspace_gid:
        listing = ", ".join(f"{w['name']}={w['gid']}" for w in workspaces) or "none found"
        results.append(
            Result(
                "Asana workspace",
                WARN,
                "ASANA_WORKSPACE_GID is not set",
                f"Pick one and add it to .env — {listing}",
            )
        )
        return results

    gids = {w["gid"] for w in workspaces}
    if settings.asana_workspace_gid not in gids:
        results.append(
            Result(
                "Asana workspace",
                FAIL,
                f"{settings.asana_workspace_gid} is not a workspace this token can see",
                ", ".join(f"{w['name']}={w['gid']}" for w in workspaces),
            )
        )
        return results

    name = next(w["name"] for w in workspaces if w["gid"] == settings.asana_workspace_gid)
    results.append(Result("Asana workspace", PASS, name))

    if deep:
        results.append(await _check_asana_dependencies())
    else:
        results.append(
            Result(
                "Asana dependencies",
                SKIP,
                "not verified",
                "Run `make check ARGS=--deep` once — dependencies need a paid tier "
                "and this is the only way to know before you build the WBS stage",
            )
        )
    return results


async def _check_asana_dependencies() -> Result:
    """Create a throwaway project, link two tasks, delete it.

    Anything short of actually calling addDependencies can't distinguish a free
    workspace from a paid one.
    """
    project_gid: str | None = None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=_asana_headers()) as client:
            r = await client.post(
                f"{ASANA}/projects",
                json={
                    "data": {
                        "name": "pm-fyp credential check (safe to delete)",
                        "workspace": settings.asana_workspace_gid,
                    }
                },
            )
            if r.status_code >= 300:
                return Result(
                    "Asana dependencies",
                    FAIL,
                    f"could not create a test project: {_body(r)}",
                    "The token needs permission to create projects in this workspace",
                )
            project_gid = r.json()["data"]["gid"]

            task_gids = []
            for label in ("A", "B"):
                tr = await client.post(
                    f"{ASANA}/tasks",
                    json={
                        "data": {
                            "name": f"check task {label}",
                            "projects": [project_gid],
                            "workspace": settings.asana_workspace_gid,
                        }
                    },
                )
                if tr.status_code >= 300:
                    return Result("Asana dependencies", FAIL, f"task create failed: {_body(tr)}")
                task_gids.append(tr.json()["data"]["gid"])

            dr = await client.post(
                f"{ASANA}/tasks/{task_gids[1]}/addDependencies",
                json={"data": {"dependencies": [task_gids[0]]}},
            )
            if dr.status_code < 300:
                return Result(
                    "Asana dependencies", PASS, "task dependencies work in this workspace"
                )

            return Result(
                "Asana dependencies",
                FAIL,
                f"HTTP {dr.status_code}: {_body(dr)}",
                "Task dependencies need Asana Premium/Advanced. Start the 30-day trial "
                "now so it covers your submission, or fall back to rendering the "
                "dependency graph only in the dashboard.",
            )
    except Exception as exc:  # noqa: BLE001
        return Result("Asana dependencies", FAIL, _short(exc))
    finally:
        if project_gid:
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT, headers=_asana_headers()) as client:
                    await client.delete(f"{ASANA}/projects/{project_gid}")
            except Exception:  # noqa: BLE001 - cleanup is best effort
                pass


# --------------------------------------------------------------------------
# GitHub
# --------------------------------------------------------------------------
async def check_github() -> list[Result]:
    if not settings.github_token:
        return [missing("GitHub", "GITHUB_TOKEN")]
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {settings.github_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        if r.status_code != 200:
            return [
                Result(
                    "GitHub",
                    FAIL,
                    f"HTTP {r.status_code}: {_body(r)}",
                    "Create a fine-grained PAT with Administration and Contents "
                    "read/write at https://github.com/settings/personal-access-tokens",
                )
            ]
        login = r.json().get("login")
        results = [Result("GitHub", PASS, f"authenticated as {login}")]
        owner = settings.github_owner or login
        if not settings.github_owner:
            results.append(
                Result(
                    "GitHub owner",
                    WARN,
                    "GITHUB_OWNER is not set",
                    f"Generated repos will default to {login}; set it explicitly to be sure",
                )
            )
        else:
            results.append(Result("GitHub owner", PASS, f"repos will be created under {owner}"))
        return results
    except Exception as exc:  # noqa: BLE001
        return [Result("GitHub", FAIL, _short(exc))]


# --------------------------------------------------------------------------
# Vercel
# --------------------------------------------------------------------------
async def check_vercel() -> Result:
    if not settings.vercel_token:
        return missing("Vercel", "VERCEL_TOKEN")
    try:
        params = {"teamId": settings.vercel_team_id} if settings.vercel_team_id else None
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                "https://api.vercel.com/v2/user",
                headers={"Authorization": f"Bearer {settings.vercel_token}"},
                params=params,
            )
        if r.status_code != 200:
            return Result(
                "Vercel",
                FAIL,
                f"HTTP {r.status_code}: {_body(r)}",
                "Create a token at https://vercel.com/account/tokens",
            )
        user = r.json().get("user", {})
        return Result(
            "Vercel", PASS, f"authenticated as {user.get('username') or user.get('email')}"
        )
    except Exception as exc:  # noqa: BLE001
        return Result("Vercel", FAIL, _short(exc))


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
    deep = "--deep" in sys.argv

    print("\n  pm-fyp credential check" + ("  (deep)" if deep else ""))

    (
        gemini_result,
        slack_results,
        asana_results,
        github_results,
        vercel_result,
        db_result,
    ) = await asyncio.gather(
        check_gemini(),
        check_slack(),
        check_asana(deep),
        check_github(),
        check_vercel(),
        check_database(),
    )

    results = [
        gemini_result,
        *slack_results,
        *asana_results,
        *github_results,
        vercel_result,
        db_result,
    ]
    render(results)
    return 1 if any(r.status == FAIL for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
