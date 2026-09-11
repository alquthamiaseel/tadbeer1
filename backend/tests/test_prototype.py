"""PROTOTYPE stage, plus the GitHub and Vercel calls it makes.

The integrations are exercised against their real request shapes with respx
rather than mocked out entirely: the shape of these two requests is the part
most likely to be wrong, and it is the part a unit test can actually pin down.
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest
import respx

from app.integrations.github import GitHubClient, slugify
from app.integrations.vercel import VercelClient
from app.llm.client import LLMResult
from app.models import Artifact, ArtifactKind, StageKind, StageStatus
from app.orchestrator import engine
from app.orchestrator.base import StageContext, StageFailed
from app.orchestrator.stages.prototype import PrototypeStage, readme
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
    """Generated paths are untrusted input: they are written to a real repo."""
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


# --- GitHub -----------------------------------------------------------------


@respx.mock
async def test_github_creates_one_commit_containing_every_file():
    respx.post("https://api.github.com/user/repos").mock(
        return_value=httpx.Response(
            201, json={"name": "campus-events", "html_url": "https://github.com/me/campus-events"}
        )
    )
    blobs = respx.post(url__regex=r".*/git/blobs").mock(
        return_value=httpx.Response(201, json={"sha": "blobsha"})
    )
    trees = respx.post(url__regex=r".*/git/trees").mock(
        return_value=httpx.Response(201, json={"sha": "treesha"})
    )
    commits = respx.post(url__regex=r".*/git/commits").mock(
        return_value=httpx.Response(201, json={"sha": "commitsha"})
    )
    refs = respx.post(url__regex=r".*/git/refs").mock(return_value=httpx.Response(201, json={}))

    name, url = await GitHubClient(token="t", owner="me").publish(
        repo_name="campus-events",
        description="Reserve a seat",
        files={"index.html": PAGE, "README.md": "# hi"},
        message="Generated prototype",
    )

    assert (name, url) == ("campus-events", "https://github.com/me/campus-events")
    assert blobs.call_count == 2, "one blob per file"
    assert trees.call_count == commits.call_count == refs.call_count == 1

    tree = json.loads(trees.calls[0].request.content)["tree"]
    assert {entry["path"] for entry in tree} == {"index.html", "README.md"}
    assert all(entry["mode"] == "100644" for entry in tree)

    commit = json.loads(commits.calls[0].request.content)
    assert commit["parents"] == [], "the first commit of an empty repo has no parent"
    assert json.loads(refs.calls[0].request.content)["ref"] == "refs/heads/main"


@respx.mock
async def test_github_retries_under_a_different_name_when_the_repo_exists():
    """Re-running PROTOTYPE asks for the same slug again; that must not fail."""
    respx.post("https://api.github.com/user/repos").mock(
        side_effect=[
            httpx.Response(422, json={"message": "name already exists on this account"}),
            httpx.Response(201, json={"name": "campus-events-ab12cd", "html_url": "https://x/y"}),
        ]
    )
    respx.post(url__regex=r".*/git/.*").mock(return_value=httpx.Response(201, json={"sha": "s"}))

    name, _ = await GitHubClient(token="t", owner="me").publish(
        repo_name="campus-events", description="d", files={"index.html": PAGE}, message="m"
    )
    assert name == "campus-events-ab12cd"


async def test_github_without_credentials_says_which_ones():
    with pytest.raises(StageFailed, match="GITHUB_TOKEN"):
        await GitHubClient(token="", owner="").publish(
            repo_name="x", description="d", files={}, message="m"
        )


def test_slugify_produces_a_name_github_accepts():
    assert slugify("Campus Event Booking!") == "campus-event-booking"
    assert slugify("   ") == "prototype"
    assert len(slugify("x" * 200)) <= 80


# --- Vercel -----------------------------------------------------------------


@respx.mock
async def test_vercel_uploads_files_inline_with_no_build_step():
    create = respx.post("https://api.vercel.com/v13/deployments").mock(
        return_value=httpx.Response(200, json={"id": "dpl_1", "url": "campus.vercel.app"})
    )
    respx.get(url__regex=r".*/v13/deployments/dpl_1.*").mock(
        return_value=httpx.Response(200, json={"readyState": "READY"})
    )

    url = await VercelClient(token="t").deploy(name="campus", files={"index.html": PAGE})

    assert url == "https://campus.vercel.app"
    body = json.loads(create.calls[0].request.content)
    assert body["target"] == "production"
    assert body["projectSettings"]["framework"] is None, "a static site must not trigger a build"
    assert body["projectSettings"]["buildCommand"] is None
    sent = body["files"][0]
    assert sent["file"] == "index.html"
    assert base64.b64decode(sent["data"]).decode() == PAGE


@respx.mock
async def test_a_failed_deployment_reports_where_the_log_is():
    respx.post("https://api.vercel.com/v13/deployments").mock(
        return_value=httpx.Response(200, json={"id": "dpl_1", "url": "campus.vercel.app"})
    )
    respx.get(url__regex=r".*/v13/deployments/dpl_1.*").mock(
        return_value=httpx.Response(200, json={"readyState": "ERROR"})
    )

    with pytest.raises(StageFailed, match="_logs"):
        await VercelClient(token="t").deploy(name="campus", files={"index.html": PAGE})


async def test_vercel_without_a_token_says_where_to_get_one():
    with pytest.raises(StageFailed, match="VERCEL_TOKEN"):
        await VercelClient(token="").deploy(name="x", files={})


# --- the stage itself -------------------------------------------------------


async def _ready_run(session):
    run = await engine.create_run(session, title="Campus Event Booking")
    for kind, artifact_kind, data, text in (
        (StageKind.INGEST, ArtifactKind.REQUIREMENTS, {"project_name": "Campus"}, None),
        (StageKind.PLAN, ArtifactKind.PLAN, {"executive_summary": "Book seats"}, None),
        (
            StageKind.DESIGN,
            ArtifactKind.DIAGRAM,
            {"kind": "ARCHITECTURE", "explanation": "How it fits together"},
            'flowchart LR\n    A["Web"] --> B["API"]\n',
        ),
    ):
        stage = next(s for s in run.stages if s.kind == kind)
        stage.status = StageStatus.COMPLETE
        session.add(
            Artifact(
                run_id=run.id,
                stage_id=stage.id,
                kind=artifact_kind,
                name="Architecture" if text else artifact_kind.value,
                version=1,
                data=data,
                text=text,
            )
        )
    await session.commit()
    return await engine.load_run(session, run.id)


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


def fake_publishers(monkeypatch):
    """Capture what would have been sent to GitHub and Vercel."""
    sent: dict = {}

    async def _publish(self, *, repo_name, description, files, message):
        sent["github"] = {"repo_name": repo_name, "files": files, "message": message}
        return repo_name, f"https://github.com/me/{repo_name}"

    async def _deploy(self, *, name, files):
        sent["vercel"] = {"name": name, "files": files}
        return f"https://{name}.vercel.app"

    monkeypatch.setattr(GitHubClient, "publish", _publish)
    monkeypatch.setattr(VercelClient, "deploy", _deploy)
    return sent


async def test_the_stage_commits_then_deploys_the_same_files(session, monkeypatch):
    fake_llm(monkeypatch, prototype())
    sent = fake_publishers(monkeypatch)
    run = await _ready_run(session)

    result = await PrototypeStage().run(StageContext(run=run, session=session))

    assert sent["github"]["files"].keys() == sent["vercel"]["files"].keys()
    assert result.run_updates["github_repo_url"] == "https://github.com/me/campus-event-booking"
    assert result.run_updates["vercel_url"] == "https://campus-event-booking.vercel.app"
    assert result.artifacts[0].kind == ArtifactKind.PROTOTYPE_FILES


async def test_the_committed_readme_embeds_the_design_diagrams(session, monkeypatch):
    fake_llm(monkeypatch, prototype())
    sent = fake_publishers(monkeypatch)
    run = await _ready_run(session)

    await PrototypeStage().run(StageContext(run=run, session=session))

    committed = sent["github"]["files"]["README.md"]
    assert "```mermaid" in committed, "GitHub renders Mermaid natively; use it"
    assert "flowchart LR" in committed


async def test_an_unsafe_file_set_is_regenerated_with_the_reason(session, monkeypatch):
    unsafe = prototype(
        files=[
            PrototypeFile(path="index.html", contents=PAGE),
            PrototypeFile(path="../escape.html", contents="x"),
        ]
    )
    calls = fake_llm(monkeypatch, unsafe, prototype())
    fake_publishers(monkeypatch)
    run = await _ready_run(session)

    result = await PrototypeStage().run(StageContext(run=run, session=session))

    assert len(calls) == 2
    assert "escape.html" in calls[1]
    assert result.input_tokens == 1000, "both attempts are billed to the stage"


async def test_a_prototype_that_stays_unsafe_fails_the_stage(session, monkeypatch):
    unsafe = prototype(files=[PrototypeFile(path="only.html", contents=PAGE)], screens=[])
    fake_llm(monkeypatch, unsafe, unsafe)
    fake_publishers(monkeypatch)
    run = await _ready_run(session)

    with pytest.raises(StageFailed, match="could not be made deployable"):
        await PrototypeStage().run(StageContext(run=run, session=session))


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
