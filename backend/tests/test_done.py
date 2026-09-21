"""DONE stage: an accurate recap, composed from the run's own runtime state."""

from __future__ import annotations

from app.orchestrator import engine
from app.orchestrator.base import StageContext
from app.orchestrator.stages.done import DoneStage
from app.orchestrator.state import Artifact, ArtifactKind, StageKind


async def _finished_run():
    run = await engine.create_run(title="Campus Event Booking")
    run.asana_project_url = "https://app.asana.com/0/1/list"
    run.github_repo_url = "https://github.com/me/campus"
    run.vercel_url = "https://campus.vercel.app"

    payloads = [
        (
            ArtifactKind.REQUIREMENTS,
            "Requirements",
            1,
            {"goal": "Book seats", "features": [1, 2, 3]},
        ),
        (ArtifactKind.PLAN, "Plan", 1, {"executive_summary": "old", "phases": [1]}),
        (ArtifactKind.PLAN, "Plan", 2, {"executive_summary": "new", "phases": [1, 2]}),
        (
            ArtifactKind.WBS,
            "WBS",
            1,
            {"tasks": [{"depends_on": []}, {"depends_on": ["a"]}, {"depends_on": ["a", "b"]}]},
        ),
        (ArtifactKind.DIAGRAM, "Use case", 1, {"kind": "USE_CASE"}),
        (ArtifactKind.DIAGRAM, "Architecture", 1, {"kind": "ARCHITECTURE"}),
        (ArtifactKind.PROTOTYPE_FILES, "Campus", 1, {"screens": [1, 2, 3, 4]}),
    ]
    for kind, name, version, data in payloads:
        run.artifacts.append(Artifact(kind=kind, name=name, version=version, data=data))

    ingest = next(s for s in run.stages if s.kind == StageKind.INGEST)
    ingest.input_tokens, ingest.output_tokens = 1000, 2000
    return run


async def test_the_recap_counts_what_the_run_actually_produced():
    run = await _finished_run()

    result = await DoneStage().run(StageContext(run=run))

    summary = result.artifacts[0].data
    assert result.artifacts[0].kind == ArtifactKind.SUMMARY
    assert summary["counts"] == {
        "features": 3,
        "phases": 2,
        "tasks": 3,
        "dependencies": 3,
        "diagrams": 2,
        "screens": 4,
    }
    assert summary["tokens"] == {"input": 1000, "output": 2000}


async def test_the_recap_reads_the_latest_version_of_a_re_run_stage():
    """A plan revised after feedback must not be summarised from the old version."""
    run = await _finished_run()

    result = await DoneStage().run(StageContext(run=run))

    assert result.artifacts[0].data["executive_summary"] == "new"


async def test_the_recap_carries_every_external_link():
    run = await _finished_run()

    result = await DoneStage().run(StageContext(run=run))

    assert result.artifacts[0].data["links"] == {
        "asana": "https://app.asana.com/0/1/list",
        "github": "https://github.com/me/campus",
        "prototype": "https://campus.vercel.app",
    }


async def test_done_needs_no_model_call_so_a_run_finishes_on_an_exhausted_quota():
    """DoneStage must never import or call the LLM client."""
    import inspect

    from app.orchestrator.stages import done

    assert "generate_structured" not in inspect.getsource(done)


async def test_a_run_with_nothing_but_a_title_still_completes():
    run = await engine.create_run(title="Abandoned")

    result = await DoneStage().run(StageContext(run=run))

    assert result.artifacts[0].data["counts"]["tasks"] == 0
    assert result.artifacts[0].data["links"] == {"asana": None, "github": None, "prototype": None}
