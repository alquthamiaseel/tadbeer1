"""PROTOTYPE stage: file-map safety checks and the generated artifact.

GitHub-commit and Vercel-deploy have been removed from this build (see
``app.orchestrator.stages.prototype``); this stage now only generates and
validates the static file set.
"""

from __future__ import annotations

import pytest

from app.llm.client import LLMResult
from app.orchestrator import engine
from app.orchestrator.base import StageContext, StageFailed
from app.orchestrator.stages.prototype import PrototypeStage, readme
from app.orchestrator.state import Artifact, ArtifactKind, StageStatus
from app.schemas.design import Diagram, DiagramKind
from app.schemas.prototype import Prototype, PrototypeFile, Screen, problems

PAGE = "<!doctype html><html><body><h1>Events</h1></body></html>"


def prototype(**overrides) -> Prototype:
    defaults = dict(
        app_name="Campus Events",
        tagline="Reserve a seat at campus events",
        screens=[
            Screen(name="Home", path="index.html", purpose="Browse what is on"),
            Screen(name="Event", path="event.html", purpose="Reserve a seat"),
        ],
        files=[
            PrototypeFile(path="index.html", contents=PAGE),
            PrototypeFile(path="event.html", contents=PAGE),
        ],
        notes=["Reservations are not persisted"],
    )
    return Prototype(**{**defaults, **overrides})


# --- the file-map safety checks --------------------------------------------


def test_a_prototype_without_an_entry_point_is_rejected():
    broken = prototype(
        files=[PrototypeFile(path="home.html", contents=PAGE)],
        screens=[Screen(name="Home", path="home.html", purpose="x")],
    )
    assert any("index.html" in problem for problem in problems(broken))


@pytest.mark.parametrize(
    "path",
    ["/etc/passwd", "../outside.html", "a/../../b.html", "~/x.html", "deep/a/b/c/d.html"],
)
def test_paths_that_escape_the_repository_are_rejected(path):
    """Generated paths are untrusted input: they would be written to a real repo."""
    broken = prototype(
        files=[
            PrototypeFile(path="index.html", contents=PAGE),
            PrototypeFile(path=path, contents="x"),
        ]
    )
    assert any(repr(path) in problem for problem in problems(broken))


def test_non_web_file_types_are_rejected():
    broken = prototype(
        files=[
            PrototypeFile(path="index.html", contents=PAGE),
            PrototypeFile(path="run.sh", contents="rm -rf /"),
        ]
    )
    assert any("run.sh" in problem for problem in problems(broken))


def test_a_screen_pointing_at_a_file_that_was_not_generated_is_rejected():
    broken = prototype(screens=[Screen(name="Ghost", path="ghost.html", purpose="x")])
    assert any("ghost.html" in problem for problem in problems(broken))


def test_a_well_formed_prototype_has_no_problems():
    assert problems(prototype()) == []


# --- the stage itself -------------------------------------------------------


async def _ready_run():
    run = await engine.create_run(title="Campus Event Booking")
    for stage in run.stages:
        stage.status = StageStatus.COMPLETE
    run.artifacts.append(
        Artifact(
            kind=ArtifactKind.REQUIREMENTS, name="Requirements", version=1,
            data={"project_name": "Campus"},
        )
    )
    run.artifacts.append(
        Artifact(
            kind=ArtifactKind.PLAN, name="Plan", version=1,
            data={"executive_summary": "Book seats"},
        )
    )
    # DESIGN is not part of a Phase 1 run's stages, but PrototypeStage still
    # reads a DIAGRAM artifact if one is present — exercise that with a
    # synthetic artifact, as DESIGN would have produced for a later phase.
    run.artifacts.append(
        Artifact(
            kind=ArtifactKind.DIAGRAM,
            name="Architecture",
            version=1,
            data={"kind": "ARCHITECTURE", "explanation": "How it fits together"},
            text='flowchart LR\n    A["Web"] --> B["API"]\n',
        )
    )
    return run


def fake_llm(monkeypatch, *prototypes):
    calls: list[str] = []
    queue = list(prototypes)

    async def _generate(*, output_model, system, user, **kwargs):
        calls.append(user)
        return LLMResult(
            data=queue.pop(0) if queue else prototypes[-1],
            raw_text="{}",
            model="fake",
            input_tokens=500,
            output_tokens=4000,
            thought_tokens=0,
            duration_ms=1,
        )

    monkeypatch.setattr("app.orchestrator.stages.prototype.generate_structured", _generate)
    return calls


async def test_the_stage_produces_the_file_set_as_an_artifact(monkeypatch):
    fake_llm(monkeypatch, prototype())
    run = await _ready_run()

    result = await PrototypeStage().run(StageContext(run=run))

    assert result.artifacts[0].kind == ArtifactKind.PROTOTYPE_FILES
    files = result.artifacts[0].data["files"]
    assert "index.html" in files
    assert "README.md" in files


async def test_the_readme_embeds_the_design_diagrams(monkeypatch):
    fake_llm(monkeypatch, prototype())
    run = await _ready_run()

    result = await PrototypeStage().run(StageContext(run=run))

    committed = result.artifacts[0].data["files"]["README.md"]
    assert "```mermaid" in committed, "the README should still embed the design diagrams"
    assert "flowchart LR" in committed


async def test_an_unsafe_file_set_is_regenerated_with_the_reason(monkeypatch):
    unsafe = prototype(
        files=[
            PrototypeFile(path="index.html", contents=PAGE),
            PrototypeFile(path="../escape.html", contents="x"),
        ]
    )
    calls = fake_llm(monkeypatch, unsafe, prototype())
    run = await _ready_run()

    result = await PrototypeStage().run(StageContext(run=run))

    assert len(calls) == 2
    assert "escape.html" in calls[1]
    assert result.input_tokens == 1000, "both attempts are billed to the stage"


async def test_a_prototype_that_stays_unsafe_fails_the_stage(monkeypatch):
    unsafe = prototype(files=[PrototypeFile(path="only.html", contents=PAGE)], screens=[])
    fake_llm(monkeypatch, unsafe, unsafe)
    run = await _ready_run()

    with pytest.raises(StageFailed, match="could not be made deployable"):
        await PrototypeStage().run(StageContext(run=run))


def test_readme_survives_a_run_with_no_diagrams():
    text = readme("Campus", prototype(), [])
    assert "Campus Events" in text
    assert "```mermaid" not in text


def test_readme_lists_every_screen():
    diagram = Diagram(
        kind=DiagramKind.ERD,
        title="Data",
        explanation="Entities",
        mermaid="erDiagram\n  A ||--|| B : x",
    )
    text = readme("Campus", prototype(), [diagram])
    assert "[Home](index.html)" in text
    assert "[Event](event.html)" in text
    assert "erDiagram" in text
