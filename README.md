# Tadbeer (pm-fyp) — Agentic AI Project Manager

**Phase 1.** An AI system that turns a stakeholder conversation in Slack into structured
requirements and a reviewable project plan, with a human in the loop.

It listens in **Slack**, extracts requirements with an LLM (**Requirements Agent**), then turns
those requirements into a delivery plan (**Planning Agent**). A React dashboard (`frontend/`)
shows both results.

This is Phase 1 only: `backend/app/orchestrator/stages/` currently holds just `ingest.py` and
`plan.py`. Later phases (WBS, system design, a prototype, monitoring/replanning) are not in this
codebase yet — they'll be added as new stage modules, wired into `STAGE_ORDER` in
`backend/app/orchestrator/state.py`, when that work starts.

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
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| LLM | OpenAI (default `gpt-4o-mini`, set `LLM_MODEL` to change) with strict JSON-schema output per stage |
| Slack | `slack-bolt` in Socket Mode, run as a background task inside the API process |
| Jobs | In-process asyncio worker with in-memory run state |
| Logins | `data/users.json` (PBKDF2-hashed passwords) — no database server |
| Frontend | React 19, Vite, Tailwind 4, React Router — talks to the API through Vite's `/api` proxy |

The Slack listener runs as a background `asyncio` task started in the FastAPI app's
`lifespan()` (`backend/app/main.py`), in the same process as the HTTP API, so a run created from
`/pm start` is immediately visible to `GET /api/runs/{id}` with no database in between.

Dashboard users live in `data/users.json`, read only by `POST /api/auth/login`. Pipeline state
(runs, requirements, plans) is in memory and is cleared when the backend restarts.

## Quick start

```bash
cp .env.example .env        # then fill in OPENAI_API_KEY, SLACK_BOT_TOKEN, SLACK_APP_TOKEN
make install                # pip install backend deps (run inside your venv) + npm install
make check                  # verify OpenAI, Slack, and the users file
make create-user u=alice p=yourpassword   # the dashboard login (username + password)
make dev                    # backend (with the Slack listener) on :8000 + dashboard on :3000
```

Without `make`, from an activated venv: `cd backend`, `pip install -r requirements.txt`,
`python -m scripts.create_user --username alice --password yourpassword`,
`python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`; then `cd frontend`, `npm install`,
`npm run dev`.

Open http://localhost:3000 and sign in. Then invite the bot to a Slack channel, discuss what you
want built, and run `/pm start`. The run appears on the dashboard, and its requirements and plan
fill in live as the two agents finish (also at `GET /api/runs/{run_id}`).

To rehearse without typing a conversation live:

```bash
make seed c=C0123456789     # load a canned stakeholder conversation into the running backend
make e2e  c=C0123456789     # run INGEST + PLAN for real against OpenAI and check the result
```

`make seed` needs the backend already running (`make api`) — captured messages live in that
process's memory, which a separate script can only reach over HTTP.

## Credentials required

`.env.example` documents each one. `make check` verifies OpenAI, Slack, and the users file before
you start.

| Service | Purpose |
|---|---|
| OpenAI | The LLM behind the Requirements and Planning agents (needs an API key with billing enabled) |
| Slack | Conversation capture and the plan-approval buttons (Socket Mode) |
| Users file | `data/users.json`, created by `create_user` |

## Layout

```
backend/app/orchestrator/            the pipeline engine and runtime state
backend/app/orchestrator/stages/     one module per stage (only INGEST + PLAN run in Phase 1)
backend/app/integrations/slack.py    the Slack integration
backend/app/schemas/                 Pydantic models — also the LLM output schemas
backend/app/llm/                     OpenAI client and the JSON-schema converter
backend/scripts/                     credential check, seed, end-to-end acceptance
frontend/                            React dashboard (login, run list, requirements + plan view)
```
