"""DESIGN stage: four valid diagrams out, or a loud failure.

The point of the stage is that invalid Mermaid never reaches an artifact — a
diagram that does not parse is invisible until the dashboard or the README, by
which time the run is over.
"""

from __future__ import annotations

import pytest

from app.llm.client import LLMResult
from app.models import ArtifactKind
from app.orchestrator.base import StageContext, StageFailed
from app.orchestrator.stages.design import DesignStage, diagram_markdown
from app.schemas.design import Diagram, DiagramKind, SystemDesign

GOOD = {
    DiagramKind.USE_CASE: 'flowchart TD\n    S(["Student"]) --> B["Browse events"]\n',
    DiagramKind.ARCHITECTURE: 'flowchart LR\n    W["Web app"] --> A["API"]\n',
    DiagramKind.ERD: "erDiagram\n    STUDENT ||--o{ RESERVATION : makes\n",
    DiagramKind.SEQUENCE: "sequenceDiagram\n    S->>API: reserve\n    API-->>S: ok\n",
}


def design(**overrides) -> SystemDesign:
    diagrams = [
        Diagram(
            kind=kind,
            title=kind.value.title(),
            explanation="What it shows.",
            mermaid=overrides.get(kind.value, source),
        )
        for kind, source in GOOD.items()
    ]
    if "diagrams" in overrides:
        diagrams = overrides["diagrams"]
    return SystemDesign(
        overview="A small web application.",
        technology_choices=["Next.js — the team knows it"],
        diagrams=diagrams,
    )


def fake_llm(monkeypatch, *designs: SystemDesign):
    """Return successive designs on successive calls, recording the prompts."""
    calls: list[str] = []
    queue = list(designs)

    async def _generate(*, output_model, system, user, **kwargs):
        calls.append(user)
        data = queue.pop(0) if queue else designs[-1]
        return LLMResult(
            data=data,
            raw_text="{}",
            model="fake",
            input_tokens=100,
            output_tokens=200,
            thought_tokens=0,
            duration_ms=1,
        )

    monkeypatch.setattr("app.orchestrator.stages.design.generate_structured", _generate)
    return calls


async def _ready_run(session):
    from app.models import Artifact, StageKind, StageStatus
    from app.orchestrator import engine

    run = await engine.create_run(session, title="Campus Event Booking")
    for kind, artifact_kind, data in (
        (StageKind.INGEST, ArtifactKind.REQUIREMENTS, {"project_name": "Campus Event Booking"}),
        (StageKind.PLAN, ArtifactKind.PLAN, {"executive_summary": "Book seats at campus events"}),
    ):
        stage = next(s for s in run.stages if s.kind == kind)
        stage.status = StageStatus.COMPLETE
        session.add(
            Artifact(
                run_id=run.id,
                stage_id=stage.id,
                kind=artifact_kind,
                name=artifact_kind.value,
                version=1,
                data=data,
            )
        )
    await session.commit()
    return await engine.load_run(session, run.id)


async def test_one_artifact_per_diagram_carrying_its_source(session, monkeypatch):
    fake_llm(monkeypatch, design())
    run = await _ready_run(session)

    result = await DesignStage().run(StageContext(run=run, session=session))

    assert len(result.artifacts) == 4
    assert {a.kind for a in result.artifacts} == {ArtifactKind.DIAGRAM}
    kinds = {a.data["kind"] for a in result.artifacts}
    assert kinds == {k.value for k in DiagramKind}
    erd = next(a for a in result.artifacts if a.data["kind"] == "ERD")
    assert erd.text.startswith("erDiagram")


async def test_code_fences_are_stripped_rather_than_stored(session, monkeypatch):
    fenced = design(USE_CASE='```mermaid\nflowchart TD\n    A["x"] --> B["y"]\n```')
    fake_llm(monkeypatch, fenced)
    run = await _ready_run(session)

    result = await DesignStage().run(StageContext(run=run, session=session))

    use_case = next(a for a in result.artifacts if a.data["kind"] == "USE_CASE")
    assert use_case.text.startswith("flowchart TD")
    assert "```" not in use_case.text


async def test_invalid_mermaid_is_repaired_and_the_errors_are_quoted_back(session, monkeypatch):
    broken = design(USE_CASE="flowchart TD\n    A[Log in (SSO)] --> B[Home]\n")
    calls = fake_llm(monkeypatch, broken, design())
    run = await _ready_run(session)

    result = await DesignStage().run(StageContext(run=run, session=session))

    assert len(calls) == 2, "the stage must retry once on invalid Mermaid"
    assert "syntax errors" in calls[1]
    assert "quoted" in calls[1], "the repair prompt must name the actual problem"
    assert len(result.artifacts) == 4
    assert result.input_tokens == 200, "both attempts must be billed to the stage"


async def test_a_diagram_that_stays_broken_fails_the_stage(session, monkeypatch):
    broken = design(ERD="sequenceDiagram\n    A->>B: not an ER diagram\n")
    fake_llm(monkeypatch, broken, broken)
    run = await _ready_run(session)

    with pytest.raises(StageFailed, match="Mermaid syntax errors"):
        await DesignStage().run(StageContext(run=run, session=session))


async def test_a_missing_diagram_kind_is_treated_as_a_defect(session, monkeypatch):
    only_two = design(diagrams=design().diagrams[:2])
    calls = fake_llm(monkeypatch, only_two, design())
    run = await _ready_run(session)

    result = await DesignStage().run(StageContext(run=run, session=session))

    assert "missing required diagram kinds" in calls[1]
    assert len(result.artifacts) == 4


async def test_design_requires_a_plan(session, monkeypatch):
    from app.orchestrator import engine

    fake_llm(monkeypatch, design())
    run = await engine.create_run(session, title="No plan yet")

    with pytest.raises(StageFailed, match="PLAN artifact"):
        await DesignStage().run(StageContext(run=run, session=session))


def test_readme_markdown_wraps_each_diagram_in_a_mermaid_fence():
    markdown = diagram_markdown(design().diagrams)
    assert markdown.count("```mermaid") == 4
    assert "erDiagram" in markdown
