# Requirements

What the system must do, and how each requirement is verified. "Verified by"
names a specific test or command, not an intention.

## Actors

| Actor | Role |
|---|---|
| Stakeholder | Describes what they want built, in Slack. Never uses the system directly. |
| Project manager | Runs `/pm start`, approves or rejects the plan, reads the dashboard. |
| The agent | Reads the conversation and produces every artifact. |

## Functional requirements

### FR1 — Capture the conversation

| | |
|---|---|
| **Requirement** | Messages posted in a channel the bot has joined are captured with their author and timestamp. |
| **Priority** | Must |
| **Notes** | Capture is idempotent: Slack redelivers events, and a message must not appear twice in the transcript. Bot messages, joins, edits and deletions are excluded — they are not conversation. |
| **Verified by** | `tests/test_slack.py` — capture, deduplication on (channel, ts), subtype filtering |

### FR2 — Extract structured requirements

| | |
|---|---|
| **Requirement** | The captured conversation is turned into structured requirements: goal, actors, features with MoSCoW priorities, non-functional requirements, constraints, assumptions, open questions and explicit exclusions. |
| **Priority** | Must |
| **Notes** | Each feature records the phrase it came from, or "inferred". Assumptions and open questions are required output: without them the approval step has nothing to react to except prose that sounds confident either way. |
| **Verified by** | `tests/test_ingest.py`; live run producing `Requirements` for "Student Exam Prep Organizer" |

### FR3 — Produce a reviewable project plan

| | |
|---|---|
| **Requirement** | The requirements are turned into a plan with scope, phases, milestones, risks, assumptions, open questions and an estimate. |
| **Priority** | Must |
| **Verified by** | `tests/test_plan.py`; live run, 42.5s, 449 in / 1236 out tokens |

### FR4 — Pause for a human decision

| | |
|---|---|
| **Requirement** | The plan is posted to Slack with **Approve** and **Request changes** buttons. Approval continues the pipeline. Requesting changes opens a modal, captures the feedback, and re-runs `PLAN` with it. |
| **Priority** | Must |
| **Notes** | The decision is recorded with who made it. A revision is stored as a new artifact version, not an overwrite, so the change history survives. |
| **Verified by** | `tests/test_plan.py`, `tests/test_engine.py` — approval gate, feedback reaching the revision, artifact versioning |

### FR5 — Publish a work breakdown structure to Asana

| | |
|---|---|
| **Requirement** | The approved plan becomes a task graph with dependencies, constraints, estimates and owner roles, published as a real Asana project with sections per phase and dependency links between tasks. |
| **Priority** | Must |
| **Notes** | Dependencies may only refer to earlier tasks; forward references, unknown ids and duplicates are rejected before Asana is called. Dependency links require a paid Asana tier, and that failure is reported as what it is rather than as a bare HTTP 402. |
| **Verified by** | `tests/test_wbs.py` — dependency validation, Asana payload shape, free-tier diagnosis |

### FR6 — Generate system design diagrams

| | |
|---|---|
| **Requirement** | Four Mermaid diagrams — use case, architecture, ER, sequence — with an explanation of each. |
| **Priority** | Must |
| **Notes** | Generated Mermaid is checked structurally before it is stored, and the stage re-prompts once with the specific errors. A diagram that does not parse would otherwise stay invisible until the dashboard or the README, by which point the run is over. |
| **Verified by** | `tests/test_mermaid.py`, `tests/test_design.py`; live run where the check caught an unquoted label and the repair fixed it |

### FR7 — Generate, commit and deploy a prototype

| | |
|---|---|
| **Requirement** | A clickable low-fidelity prototype is generated, committed to a new GitHub repository together with a README embedding the design diagrams, and deployed to a live URL. |
| **Priority** | Must |
| **Notes** | Generated file paths are treated as untrusted input. A path escaping the repository root, a non-web file type, a missing entry point, or a screen pointing at a file that was not generated all send the stage back to the model with the reason. |
| **Verified by** | `tests/test_prototype.py` — path safety, GitHub commit shape, Vercel deployment shape; `scripts/e2e.py` fetches the committed files back and requests the live URL |

### FR8 — Show progress

| | |
|---|---|
| **Requirement** | Every stage transition is reported in Slack as it happens, and the dashboard shows the run's stages, durations, token usage, artifacts and links, updating live. |
| **Priority** | Must |
| **Verified by** | `tests/test_api.py` — event stream frames on change and termination; `tests/test_slack.py` — per-stage narration |

### FR9 — Survive failure

| | |
|---|---|
| **Requirement** | A crashed or interrupted run resumes from the first incomplete stage. A failed stage records the real error, and any stage can be re-run. |
| **Priority** | Must |
| **Verified by** | `tests/test_engine.py` — resume, failure recording, re-run resetting downstream stages; `POST /api/runs/{id}/rerun` |

### FR10 — Record what it did

| | |
|---|---|
| **Requirement** | Every model call and external API call is logged with its duration, token usage and outcome, and is visible per run. |
| **Priority** | Should |
| **Verified by** | `tests/test_audit.py`; `GET /api/runs/{id}/audit` |

## Non-functional requirements

| | Requirement | Verified by |
|---|---|---|
| NFR1 | No public URL, tunnel or inbound firewall rule is needed to run the system. | Slack Socket Mode; the whole system runs from a laptop |
| NFR2 | Every stage output is schema-valid before it is stored; the orchestrator never parses prose. | `tests/test_llm_schema.py`, and each stage's own tests |
| NFR3 | A free-tier quota exhaustion pauses a run rather than losing it. | Exponential backoff with full jitter in `app/llm/client.py`; resumability in the engine |
| NFR4 | A transient network failure is retried rather than failing the run. | `tests/test_http.py`; `_is_transient` in the LLM client |
| NFR5 | The whole system runs on free tiers, except Asana Premium for dependency links. | `docs/setup.md`; the Asana tier limitation is stated rather than hidden |
| NFR6 | No credential is ever sent to the browser. | The API client runs server-side only; the session cookie carries an HMAC, not the password |
| NFR7 | The generated prototype deploys with no build step, so it cannot fail to compile. | Static file map, `framework: null` in the Vercel deployment |

## Out of scope

Deliberately not built, and worth saying so explicitly:

* Multiple concurrent projects per Slack channel.
* Editing artifacts in the dashboard. Approvals belong in the conversation.
* Any authentication beyond one shared password.
* Real-time collaboration or multi-user roles.
* Regenerating the prototype from user interaction with the deployed site.
