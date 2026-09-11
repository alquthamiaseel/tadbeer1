# Setup

Everything below has to be green before the pipeline will run end to end.
`make check` verifies all of it and tells you what is missing, so run it after
each step rather than at the end.

## 1. Prerequisites

* Python 3.12 and [uv](https://docs.astral.sh/uv/)
* Node 20+ and npm
* Docker (for Postgres)

```bash
git clone <this repository> && cd pm-fyp
cp .env.example .env
make install
make db
make migrate
```

## 2. Gemini

Free, no card required.

1. Go to <https://aistudio.google.com/apikey> and create a key.
2. Put it in `.env` as `GEMINI_API_KEY`.

Free-tier quota is enforced **per minute** as well as per day. Check the live
limits for your model at <https://aistudio.google.com/rate-limit>. If a run stops
with a quota error, that is the per-minute window, not a bug — the client backs
off and retries, and the run resumes from the stage it stopped at.

## 3. Slack

You need to be an admin of the workspace, so create your own free one rather than
using a university or company workspace.

1. Go to <https://api.slack.com/apps> → **Create New App** → **From a manifest**.
2. Pick your workspace, choose the **JSON** tab, and paste
   [`slack-app-manifest.json`](slack-app-manifest.json) — the file is JSON, so
   pasting it into the YAML tab will fail on line 1.
3. **Install to Workspace**.
4. **OAuth & Permissions** → copy the **Bot User OAuth Token** (`xoxb-…`) into
   `SLACK_BOT_TOKEN`.
5. **Basic Information** → **App-Level Tokens** → **Generate Token and Scopes**,
   add the `connections:write` scope, and copy the token (`xapp-…`) into
   `SLACK_APP_TOKEN`.
6. In Slack, invite the bot to the channel you will use: `/invite @PM Agent`.

The bot only ever sees messages sent **after** it joined the channel, so invite
it before the conversation you want it to read.

## 4. Asana

**Start the Premium trial before you need it.** Task dependencies — which are
part of what this project sets out to demonstrate — require a Premium or Advanced
workspace. On the free tier the project, sections and tasks are all created and
only the dependency links fail, so the problem surfaces late, with most of the
work already done.

1. Start the 30-day trial at <https://app.asana.com/0/organization-admin>.
2. Create a personal access token at <https://app.asana.com/0/my-apps> and put it
   in `ASANA_ACCESS_TOKEN`.
3. Leave `ASANA_WORKSPACE_GID` blank and run `make check` — it lists your
   workspaces with their ids. Paste the right one back into `.env`.
4. Run `make check ARGS=--deep`. This creates two throwaway tasks, links them, and
   deletes them, which is the only way to know your tier really allows
   dependencies before the WBS stage depends on it.

### If Asana is not available yet

Set `ASANA_ENABLED=false` in `.env`. The `WBS` stage still runs: it builds the
task graph with dependencies, constraints, estimates and owner roles, stores it
as an artifact, and the dashboard renders it as a dependency-aware table. Only
the push to Asana is skipped, and both Slack and the run summary say so.

Everything downstream — `DESIGN`, `PROTOTYPE`, GitHub, Vercel — is unaffected,
because no later stage reads from Asana. `make e2e` reports the Asana check as
**SKIP** rather than pass or fail, which is the honest answer: that part was not
demonstrated.

Turn it back on when the workspace arrives, then `make check ARGS=--deep` and
re-run the `WBS` stage from the dashboard or with `/pm` — the run resumes rather
than starting over.

## 5. GitHub

1. Create a **fine-grained** personal access token at
   <https://github.com/settings/personal-access-tokens>.
2. Give it **Administration: Read and write** (to create repositories) and
   **Contents: Read and write** (to commit files) on your own account.
3. Put it in `GITHUB_TOKEN`, and your username in `GITHUB_OWNER`.

## 6. Vercel

1. Create a token at <https://vercel.com/account/tokens>.
2. Put it in `VERCEL_TOKEN`.
3. `VERCEL_TEAM_ID` is only needed if the token belongs to a team rather than
   your personal account.

## 7. Verify and run

```bash
make check ARGS=--deep      # every credential, including the Asana tier
make dev                    # backend + Slack listener + dashboard
```

Then in Slack: discuss what you want built in a channel the bot is in, and run
`/pm start`.

To rehearse without typing a conversation:

```bash
make seed c=C0123456789     # the channel id, from Slack's channel details
make e2e  c=C0123456789
```

## Putting the dashboard on a domain

Running on a laptop, the API listens on `127.0.0.1` and nothing else can reach
it. If you publish the dashboard, that stops being true and the API would expose
every stakeholder conversation the agent has read.

Set in `.env`:

```
DASHBOARD_AUTH=true
DASHBOARD_PASSWORD=<something that is not "changeme">
API_URL=<where the backend is reachable from the dashboard server>
```

The dashboard then asks for the password once and keeps it server-side; the
browser only ever holds a session cookie. With auth on and the password left at
its default, the API refuses to serve rather than accepting it.

Note that the Slack listener holds a persistent WebSocket and therefore cannot
run on a serverless platform. Hosting the whole system publicly means the
dashboard on Vercel, the backend and listener on a platform that runs long-lived
processes, and a managed Postgres.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `/pm` says the app did not respond | The listener is not running, or Postgres is down. `make db`, then `make slack`. |
| `/pm start` replies asking to be invited | The bot is not in the channel. `/invite @PM Agent`. |
| `/pm start` says it has seen no conversation | The bot joined after the messages were sent. Talk again, or `make seed`. |
| A stage fails with a quota error | Free-tier per-minute window. Wait, then re-run the stage. |
| WBS fails mentioning Premium | The Asana workspace cannot link dependencies. Start the trial. |
| The dashboard says it cannot reach the backend | `make api`, and check `API_URL`. |
