# Demonstration script

Roughly twelve minutes, of which about five are the pipeline running. Rehearse it
twice before the day.

## Before you start

```bash
make check ARGS=--deep      # all green, including the Asana tier
make db && make dev         # Postgres, backend, Slack listener, dashboard
```

Have open: the Slack channel, the dashboard at <http://localhost:3000>, and empty
tabs for Asana, GitHub and Vercel.

Check the bot is in the channel (`/invite @PM Agent` if not) and that the Gemini
per-minute quota has not just been used by a rehearsal — wait a minute if it has.

## 1. The problem (1 minute)

Say what this replaces: a project manager reads a conversation, writes a plan,
builds a work breakdown, draws the design, and mocks up a prototype. Every one of
those is a translation of the same information into a different form, and every
one of them is done by hand.

## 2. The conversation (1 minute)

Either post a short stakeholder conversation live, or point at one already in the
channel. If you seeded it, say so — a canned conversation is honest and it makes
the demo repeatable.

```bash
make seed c=C0123456789
```

## 3. Start the run (30 seconds)

```
/pm start
```

The bot replies immediately. Switch to the dashboard: the run appears with six
stages, the first one running.

Point out that the dashboard is live — no refreshing — and that the timeline is
reading pipeline state out of the database rather than being told by the agent.

## 4. Requirements (1 minute)

`INGEST` finishes in about ten seconds. Open the artifact in the dashboard.

The thing to point at is not the feature list — it is **open questions** and
**assumptions**. The system reports what it could not determine, and each feature
carries the phrase it came from or the word "inferred". That is what makes the
next step a real decision rather than a rubber stamp.

## 5. The plan, and the human (2 minutes)

`PLAN` posts to Slack with **Approve** and **Request changes**.

Click **Request changes** and type something specific — "add a pilot phase before
delivery". The plan is regenerated with that feedback, and the dashboard shows
the new plan as **revision 2**: the original is still there, so the change
history survives.

Then approve it. This is the heart of the project: the human decides, in the
place the conversation is already happening, and the decision is recorded with
who made it.

## 6. Everything downstream (4 minutes)

The remaining four stages run without further input, narrating into Slack as
each finishes. While they run:

* **Asana** — open the project. Sections per phase, tasks with owners and
  estimates, and dependency arrows between them.
* **Diagrams** — four in the dashboard, rendered from Mermaid source. Mention
  that the source is stored, not an image, which is why the same diagrams render
  in the GitHub README.
* **GitHub** — the repository, one commit, the README with the diagrams
  rendering inline.
* **Vercel** — the live prototype. Click through its screens.

## 7. Close (2 minutes)

Back to the dashboard: six stages complete, durations, token usage per stage, and
the call log showing every model and API call the run made.

Say the honest version of what this is: a documented six-stage pipeline where
each stage is one schema-constrained model call, not an autonomous agent. That
constraint is why it can be demonstrated at all.

## If something fails

Do not restart the run. Failures are part of the design and recovering from one
in front of the audience is a better demonstration than a clean run.

| What happened | What to do |
|---|---|
| Quota error from Gemini | Say it: free tier, per-minute window. Wait, then re-run the stage. The run resumes where it stopped. |
| A stage failed | The dashboard shows the real error. Re-run it. |
| Asana rejects dependencies | The trial expired. The tasks are still there; say what the tier limitation is. |
| Vercel is slow | The deployment polls for up to three minutes. The GitHub commit already exists — show that. |
| Slack does not respond | The listener or Postgres is down. `make db`, `make slack`. Meanwhile the dashboard still works. |

## What to have ready for questions

* **"Is this an agent?"** It is a pipeline, deliberately. Say why: determinism,
  debuggability, and being able to describe it precisely.
* **"What stops it hallucinating?"** Schema-constrained generation plus
  validation against the same model, structural checking of generated Mermaid,
  and path validation of generated files. Nothing stops it inventing a plausible
  requirement, which is exactly why there is an approval gate.
* **"What does it cost?"** See `docs/evaluation.md` — a full run is five to seven
  model calls on the free tier.
* **"What would you do next?"** Also in `docs/evaluation.md`, honestly.
