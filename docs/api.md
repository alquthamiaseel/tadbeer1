# API reference

Base URL `http://127.0.0.1:8000`. Everything under `/api` is consumed by the
dashboard; `/health` is unauthenticated so a process check does not need a
credential.

When `DASHBOARD_AUTH=true`, every `/api` route requires
`Authorization: Bearer <DASHBOARD_PASSWORD>`.

## Runs

### `GET /api/runs`

The 100 most recent runs, newest first.

```json
[
  {
    "id": "940b9ecb-d5f9-4608-aadd-c607b3b6fae3",
    "title": "Student Exam Prep Organizer",
    "status": "RUNNING",
    "current_stage": "PLAN",
    "created_at": "2026-08-14T21:22:17.099348+00:00",
    "asana_project_url": null,
    "github_repo_url": null,
    "vercel_url": null
  }
]
```

`status` is one of `PENDING`, `RUNNING`, `AWAITING_APPROVAL`, `COMPLETE`,
`FAILED`, `CANCELLED`.

### `GET /api/runs/{run_id}`

One run with its stages and artifacts. Adds `error`, `slack_channel_id`,
`slack_thread_ts`, `stages` and `artifacts` to the summary above.

A stage:

```json
{
  "id": "…",
  "kind": "DESIGN",
  "position": 3,
  "status": "COMPLETE",
  "attempt": 1,
  "error": null,
  "duration_seconds": 53.0,
  "input_tokens": 3746,
  "output_tokens": 2703
}
```

An artifact. `data` holds the validated JSON the stage produced; `text` holds
raw text where that is the natural form, which today means Mermaid source.

```json
{
  "id": "…",
  "kind": "DIAGRAM",
  "name": "Database Entity Relationship Diagram",
  "version": 1,
  "data": { "kind": "ERD", "explanation": "…" },
  "text": "erDiagram\n    STUDENT ||--o{ EXAM : sits\n",
  "created_at": "2026-08-14T21:31:02.881190+00:00"
}
```

`kind` is one of `REQUIREMENTS`, `PLAN`, `WBS`, `DIAGRAM`, `PROTOTYPE_FILES`,
`SUMMARY`. Re-running a stage adds a version rather than replacing one, so a
client wanting current state should take the highest `version` for each
`(kind, name)`.

### `GET /api/runs/{run_id}/artifacts/{artifact_id}`

One artifact, in the shape above.

### `GET /api/runs/{run_id}/audit`

Every model and external API call this run made, oldest first.

```json
[
  {
    "id": "…",
    "kind": "llm",
    "target": "gemini-3.6-flash",
    "ok": true,
    "duration_ms": 42500,
    "input_tokens": 449,
    "output_tokens": 1236,
    "detail": { "schema": "ProjectPlan", "thought_tokens": 0 },
    "error": null,
    "created_at": "…"
  }
]
```

`kind` is `llm` or `api`. For an API call, `target` reads like
`GitHub POST /repos/me/campus/git/trees` and `detail` carries the HTTP status
and how many attempts it took.

### `GET /api/stages/{stage_id}`

One stage, in the shape above.

### `POST /api/runs/{run_id}/rerun`

Reset a stage and everything after it, then run forward from there in the
background. Returns the reset run immediately — a run takes minutes, and holding
the request open would invite a proxy to time it out.

```json
{ "stage": "PLAN", "feedback": "Add a pilot phase before delivery" }
```

`feedback` is optional and is passed to the stage being re-run. Later stages are
reset too, because they were derived from output that is about to change.

`400` if the run has no such stage; `422` if `stage` is not a stage name.

### `GET /api/runs/{run_id}/events`

Server-sent events. One `data:` frame per actual change, each carrying the whole
run in the `GET /api/runs/{run_id}` shape — a run is small, and a stream of
deltas would need reconnection logic to work out what it had missed.

```
data: {"id": "…", "status": "RUNNING", "stages": [...], ...}

: heartbeat

event: end
data: {}
```

The stream sends the current state immediately, a frame whenever the run
changes, a comment heartbeat every 15 seconds so intermediaries do not close an
idle connection, and `event: end` when the run reaches a terminal state, at which
point the client should stop reconnecting.

The dashboard does not connect to this directly. It relays the stream through
`/api/stream/{id}` on the Next.js server so that the browser never needs the
dashboard password.

## Errors

| Status | Meaning |
|---|---|
| `401` | `DASHBOARD_AUTH` is on and the bearer token was missing or wrong |
| `404` | No run, stage or artifact with that id |
| `422` | The request body did not validate |
| `500` | `DASHBOARD_AUTH` is on but `DASHBOARD_PASSWORD` is still `changeme` |
