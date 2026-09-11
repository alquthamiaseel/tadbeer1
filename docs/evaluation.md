# Evaluation

What the system does, what it measurably costs, and where it falls short. The
limitations section is the useful part.

## What is verified, and how

Being precise about this matters more than a green checklist: some of this has
run against live APIs and some has only been tested.

| Capability | Status |
|---|---|
| Slack capture, `/pm` commands, Socket Mode | **Verified live** — real workspace, real messages |
| `INGEST` → structured requirements | **Verified live** — real Gemini, real conversation |
| `PLAN` → reviewable plan | **Verified live** — real Gemini |
| Approval gate, Block Kit buttons, feedback modal | Tested; the button path has not been exercised end to end in a live workspace |
| `WBS` → Asana project with dependencies | Tested against recorded request shapes; **not run live** (needs a Premium workspace) |
| `DESIGN` → four Mermaid diagrams | **Verified live** — including the repair loop firing on a real syntax error |
| `PROTOTYPE` → GitHub + Vercel | Generation **verified live**; the GitHub and Vercel calls are tested against recorded shapes but **not run live** |
| Dashboard, artifact viewers, event stream | **Verified live** against real run data |
| Audit log | **Verified live** — five model calls recorded with token counts |

The three "not run live" rows all wait on credentials rather than on code.

## Measured behaviour

From a real run, "Student Exam Prep Organizer", on the Gemini free tier with
`gemini-3.6-flash`:

| Stage | Duration | Input tokens | Output tokens | Model calls |
|---|---|---|---|---|
| `INGEST` | 9.9s | 185 | 346 | 1 |
| `PLAN` | 42.5s | 449 | 1,236 | 1 |
| `DESIGN` | 53.0s | 3,746 | 2,703 | 2 (one repair) |
| `PROTOTYPE` | 99.7s | 4,150 | 15,000 approx. | 2 (one repair) |

A full run is five to seven model calls and roughly 25,000–30,000 tokens, in
three to five minutes plus however long the human takes to approve the plan. It
fits inside the free tier comfortably; the binding constraint is the per-minute
quota, not the daily one, which is why the client backs off rather than failing.

Prompt size grows down the pipeline, because each stage reads the artifacts
before it. `PROTOTYPE` has the largest input and by far the largest output — it
is generating whole HTML pages.

## What the repair loops caught

Both repair loops fired on the live run, on real defects rather than contrived
ones:

* `DESIGN` produced a sequence diagram containing `status="completed"` as an
  unquoted node label, which is a Mermaid parse error. The structural check
  caught it, the error was quoted back to the model, and the second attempt was
  valid.
* `PROTOTYPE` produced a screen list referring to four HTML files it had not
  generated. The file-map check caught it and named all four; the second attempt
  was consistent.

Neither would have been caught by schema validation, because both outputs were
schema-valid. They are the cases where "the model returned the right shape" and
"the model returned something usable" come apart, and they are the reason those
two stages check more than the schema.

## Bugs found by running it rather than testing it

Worth recording, because the pattern is consistent:

| Bug | How it was found |
|---|---|
| Retry logic never fired — the SDK raises from a private module whose errors are not the public `APIError` | Introspecting the installed SDK |
| Schema converter deleted any field named after a JSON Schema keyword, so `Feature.title` vanished while `required` still demanded it | First live `INGEST` |
| Slack failures were swallowed into the log, so `/pm start` did nothing visible | First live `/pm start` |
| `load_run` returned stale collections, so `PLAN` could not see the requirements `INGEST` had just written | Running the test suite after a commit |
| Connection errors were not retried, because the retry rule keyed on HTTP status and a dropped connection has none | Live run of `PLAN` |
| A failed stage reported zero tokens despite having made two model calls | Live run of `PROTOTYPE` |

Four of six were only visible by running the real thing. The test suite is worth
having — it caught the fifth and prevents regressions on all of them — but it did
not find most of these first.

## Limitations

**It cannot tell a good requirement from a plausible one.** Schema constraints
guarantee shape, not truth. The system will confidently produce a well-formed
plan from a misread conversation. This is the reason the approval gate exists,
and it is a mitigation rather than a solution.

**One project per channel.** A run claims the conversation in a channel; two
concurrent projects in one channel would interleave.

**The prototype is low fidelity by construction.** Static HTML with no state and
no backend. It shows layout, flow and content, and fakes everything else. Making
it real would be a different project.

**Asana dependencies need a paid tier.** Free-tier workspaces create the project
and the tasks, then fail at the link. Reported as such rather than as an HTTP
status, but not fixable from our side.

**Only the plan has an approval gate.** The WBS, design and prototype are
accepted without a human decision. The gate mechanism is general and adding
another is a one-line change to `APPROVAL_GATES`; whether more gates would help
or just add clicks is an open question.

**The event stream polls.** Once a second, against the database. Correct and
simple at this scale; it would not be at a larger one.

**No evaluation of output quality.** There is no rubric scoring the plans, no
comparison against a human-written baseline, and no inter-rater agreement on
whether the extracted requirements are right. Everything above measures whether
the system *works*, not whether what it produces is *good*. That is the most
significant gap in this evaluation.

## What I would do next

In the order I would actually do them:

1. **Measure output quality.** Take five real conversations, have the system and
   a person each produce requirements, and score both blind against a rubric.
   Without this the project can only claim to be a working system, not a useful
   one.
2. **Re-run a stage with feedback from the dashboard.** The engine already
   supports it and the endpoint exists; only the UI is missing.
3. **A cost and token analytics view.** The audit log holds the data already.
4. **Approval gates on the WBS and design**, then measure whether people use
   them or click through.
5. **Regenerate from prototype feedback** — a comment on the deployed prototype
   becoming a `PROTOTYPE` re-run. This is the loop the project gestures at and
   does not close.
