"""The Mermaid structural check.

Every case here is a real Mermaid document or a real failure mode. False
positives matter as much as false negatives: each one costs a re-prompt against
a per-minute free-tier quota for a diagram that would have rendered.
"""

from __future__ import annotations

from app.mermaid import check, describe, header_of, strip_fences

FLOWCHART = """flowchart TD
    User(["Student"]) --> Browse["Browse events"]
    Browse --> Reserve["Reserve a seat"]
    Reserve --> Confirm["Confirmation email"]
"""

SEQUENCE = """sequenceDiagram
    participant S as Student
    participant API
    participant DB
    S->>API: POST /reservations
    API->>DB: insert reservation
    DB-->>API: ok
    API-->>S: 201 Created
"""

ERD = """erDiagram
    STUDENT ||--o{ RESERVATION : makes
    EVENT ||--o{ RESERVATION : has
    STUDENT {
        string id
        string email
    }
    EVENT {
        string id
        int capacity
    }
"""

CLASS_DIAGRAM = """classDiagram
    class Reservation {
        +String id
        +confirm() bool
    }
"""


def test_valid_diagrams_pass_cleanly():
    for source in (FLOWCHART, SEQUENCE, ERD, CLASS_DIAGRAM):
        assert check(source) == [], describe(check(source))


def test_er_cardinality_is_not_read_as_an_unclosed_brace():
    """`||--o{` is an operator. Counting its brace would fail every ER diagram."""
    assert check(ERD, expected_headers=("erDiagram",)) == []


def test_unquoted_punctuation_in_a_label_is_caught():
    problems = check('flowchart TD\n    A[Log in (SSO)] --> B["Home"]\n')
    assert problems and "quoted" in problems[0].message


def test_quoted_punctuation_is_accepted():
    assert check('flowchart TD\n    A["Log in (SSO)"] --> B["Home"]\n') == []


def test_wrong_diagram_type_for_the_requested_kind_is_caught():
    problems = check(SEQUENCE, expected_headers=("erDiagram",))
    assert problems and "should be one of erDiagram" in problems[0].message


def test_a_missing_diagram_header_is_caught():
    problems = check("A --> B\n")
    assert problems and "does not start with a Mermaid diagram type" in problems[0].message


def test_empty_source_is_caught():
    assert check("   \n") and "empty" in check("   \n")[0].message


def test_code_fences_are_stripped_not_rejected():
    fenced = "```mermaid\n" + FLOWCHART + "```"
    assert strip_fences(fenced).startswith("flowchart TD")
    assert check(fenced) == []


def test_header_detection_ignores_comments_and_frontmatter():
    assert header_of("%% a comment\nflowchart LR\n  A --> B") == "flowchart"
    assert header_of("---\ntitle: Something\n---\nerDiagram\n  A ||--|| B : x") == "erDiagram"


def test_unbalanced_brackets_are_caught():
    problems = check('flowchart TD\n    A["unclosed --> B\n')
    assert problems
