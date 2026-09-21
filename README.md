# Tadbeer (pm-fyp) — Agentic AI Project Manager

**Phase 1.** An AI system that turns a stakeholder conversation in Slack into structured
requirements and a reviewable project plan, with a human in the loop.

It listens in **Slack**, extracts requirements with an LLM (**Requirements Agent**), then turns
those requirements into a delivery plan (**Planning Agent**). A dashboard (not yet built — see
below) will show both results.

Later phases add WBS, system design, a prototype, and monitoring/replanning. That code already
exists in `backend/app/orchestrator/stages/` and is not deleted — it is simply not run yet (see
`STAGE_ORDER` in `backend/app/orchestrator/state.py`).

## Pipeline (Phase 1)

```
Slack conversation
      │
      ▼
  1. INGEST   → structured requirements   (Requirements Agent)
      │
      ▼
  2. PLAN     → project plan              (Planning Agent, awaits approval in Slack)
```

Each stage is a single LLM call with a forced JSON schema, held as runtime state on the run
object in memory. A run lives for as long as the backend process that created it. The database
holds only dashboard logins — see [Architecture](#architecture) below.

## Architecture

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| LLM | Gemini (`gemini-3.6-flash`, free tier) with schema-constrained output per stage |
| Slack | `slack-bolt` in Socket Mode, run as a background task inside the API process |
| Jobs | In-process asyncio worker with in-memory run state |
| Database | Postgres 16 (Docker Compose) — dashboard logins only |
| Frontend | Not built yet for Phase 1 — the API (`/api/runs/...`) is ready for one |

The Slack listener runs as a background `asyncio` task started in the FastAPI app's
`lifespan()` (`backend/app/main.py`), in the same process as the HTTP API, so a run created from
`/pm start` is immediately visible to `GET /api/runs/{id}` with no database in between.

Postgres holds exactly one table, `users`, consulted only by `POST /api/auth/login`.

## Quick start

```bash
cp .env.example .env        # then fill in GEMINI_API_KEY, SLACK_BOT_TOKEN, SLACK_APP_TOKEN
make install                # install backend dependencies
make db                     # start Postgres
make check                  # verify Gemini, Slack, and the database
make migrate                # create the users table
make create-user u=alice p=yourpassword   # only needed if DASHBOARD_AUTH=true
make api                    # run the backend (includes the Slack listener)
```

Invite the bot to a Slack channel, discuss what you want built, and run `/pm start`. The run's
requirements and plan are then available at `GET /api/runs/{run_id}`.

To rehearse without typing a conversation live:

```bash
make seed c=C0123456789     # load a canned stakeholder conversation into the running backend
make e2e  c=C0123456789     # run INGEST + PLAN for real against Gemini and check the result
```

`make seed` needs the backend already running (`make api`) — captured messages live in that
process's memory, not in a database a separate script can write to.

## Credentials required

`.env.example` documents each one. `make check` verifies Gemini, Slack, and the database before
you start.

| Service | Purpose |
|---|---|
| Gemini | The LLM behind the Requirements and Planning agents (free tier, no card required) |
| Slack | Conversation capture and the plan-approval buttons (Socket Mode) |
| Postgres | Dashboard logins only |

## Layout

```
backend/app/orchestrator/            the pipeline engine and runtime state
backend/app/orchestrator/stages/     one module per stage (only INGEST + PLAN run in Phase 1)
backend/app/integrations/slack.py    the Slack integration
backend/app/schemas/                 Pydantic models — also the LLM output schemas
backend/app/llm/                     Gemini client and the schema converter
backend/scripts/                     credential check, seed, end-to-end acceptance
```
