"""DESIGN stage: four diagrams out, one per required kind, or a loud failure.

There is no Mermaid syntax validator in this build (see
``app.orchestrator.stages.design``); the stage still strips code fences and
still repairs a response that is missing one of the four required diagram
kinds.
"""

from __future__ import annotations

import pytest
from app.schemas.design import Diagram, DiagramKind, SystemDesign

from app.llm.client import LLMResult
from app.orchestrator.base import StageContext, StageFailed
from app.orchestrator.stages.design import DesignStage, diagram_markdown
from app.orchestrator.state import ArtifactKind

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


async def _ready_run():
    from app.orchestrator import engine
    from app.orchestrator.state import Artifact, StageKind, StageStatus

    run = await engine.create_run(title="Campus Event Booking")
    for kind, artifact_kind, data in (
        (StageKind.INGEST, ArtifactKind.REQUIREMENTS, {"project_name": "Campus Event Booking"}),
        (StageKind.PLAN, ArtifactKind.PLAN, {"executive_summary": "Book seats at campus events"}),
    ):
        stage = next(s for s in run.stages if s.kind == kind)
        stage.status = StageStatus.COMPLETE
        run.artifacts.append(
            Artifact(kind=artifact_kind, name=artifact_kind.value, version=1, data=data)
        )
    return run


async def test_one_artifact_per_diagram_carrying_its_source(monkeypatch):
    fake_llm(monkeypatch, design())
    run = await _ready_run()

    result = await DesignStage().run(StageContext(run=run))

    assert len(result.artifacts) == 4
    assert {a.kind for a in result.artifacts} == {ArtifactKind.DIAGRAM}
    kinds = {a.data["kind"] for a in result.artifacts}
    assert kinds == {k.value for k in DiagramKind}
    erd = next(a for a in result.artifacts if a.data["kind"] == "ERD")
    assert erd.text.startswith("erDiagram")


async def test_code_fences_are_stripped_rather_than_stored(monkeypatch):
    fenced = design(USE_CASE='```mermaid\nflowchart TD\n    A["x"] --> B["y"]\n```')
    fake_llm(monkeypatch, fenced)
    run = await _ready_run()

    result = await DesignStage().run(StageContext(run=run))

    use_case = next(a for a in result.artifacts if a.data["kind"] == "USE_CASE")
    assert use_case.text.startswith("flowchart TD")
    assert "```" not in use_case.text


async def test_a_missing_diagram_kind_is_treated_as_a_defect(monkeypatch):
    only_two = design(diagrams=design().diagrams[:2])
    calls = fake_llm(monkeypatch, only_two, design())
    run = await _ready_run()

    result = await DesignStage().run(StageContext(run=run))

    assert "missing required diagram kinds" in calls[1]
    assert len(result.artifacts) == 4


async def test_a_diagram_set_that_stays_missing_a_kind_fails_the_stage(monkeypatch):
    only_two = design(diagrams=design().diagrams[:2])
    fake_llm(monkeypatch, only_two, only_two)
    run = await _ready_run()

    with pytest.raises(StageFailed, match="could not be repaired"):
        await DesignStage().run(StageContext(run=run))


async def test_design_requires_a_plan(monkeypatch):
    from app.orchestrator import engine

    fake_llm(monkeypatch, design())
    run = await engine.create_run(title="No plan yet")

    with pytest.raises(StageFailed, match="PLAN artifact"):
        await DesignStage().run(StageContext(run=run))


def test_readme_markdown_wraps_each_diagram_in_a_mermaid_fence():
    markdown = diagram_markdown(design().diagrams)
    assert markdown.count("```mermaid") == 4
    assert "erDiagram" in markdown
