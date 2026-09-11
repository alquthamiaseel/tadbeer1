"""The Pydantic -> Gemini schema conversion.

These rules are not cosmetic: Gemini supports only a subset of JSON Schema and
warns that large or deeply nested schemas may be rejected outright. Every
pipeline stage goes through this conversion, so a regression here breaks the
whole pipeline rather than one stage.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field, ValidationError

from app.llm.schema import SchemaTooDeepError, to_output_schema, to_response_format


class Item(BaseModel):
    name: str = Field(description="Item name")
    quantity: int = Field(ge=1, le=99, default=1)


class Order(BaseModel):
    reference: str = Field(pattern=r"^ORD-\d+$")
    items: list[Item] = Field(min_length=1)
    note: str | None = Field(default=None, description="Optional note")


def _walk(node):
    """Yield every dict in the schema tree."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def test_references_are_inlined():
    """A schema with no $ref/$defs is the shape least likely to be rejected."""
    schema = to_output_schema(Order)
    assert "$defs" not in schema
    assert all("$ref" not in node for node in _walk(schema))
    # The nested model's own fields are present where it was referenced.
    assert schema["properties"]["items"]["items"]["properties"]["name"]["type"] == "string"


def test_unsupported_keywords_are_stripped():
    banned = {"additionalProperties", "default", "title", "$schema", "discriminator"}
    for node in _walk(to_output_schema(Order)):
        assert not banned & node.keys(), f"leaked unsupported keyword in {node}"


def test_property_ordering_is_pinned():
    """Google documents that generation order affects quality; don't leave it unspecified."""
    schema = to_output_schema(Order)
    assert schema["propertyOrdering"] == ["reference", "items", "note"]
    assert schema["properties"]["items"]["items"]["propertyOrdering"] == ["name", "quantity"]


def test_descriptions_survive():
    """Descriptions are how the schema tells the model what each field means."""
    schema = to_output_schema(Order)
    assert schema["properties"]["note"]["description"] == "Optional note"
    assert schema["properties"]["items"]["items"]["properties"]["name"]["description"] == (
        "Item name"
    )


def test_required_reflects_actual_optionality():
    """Unlike some APIs, Gemini honours `required`, so optional stays optional."""
    schema = to_output_schema(Order)
    assert set(schema["required"]) == {"reference", "items"}
    assert "note" not in schema["required"]


def test_response_format_envelope():
    fmt = to_response_format(Order)
    assert fmt == {
        "type": "text",
        "mime_type": "application/json",
        "schema": to_output_schema(Order),
    }


def test_recursive_models_are_rejected_with_a_useful_message():
    """Gemini cannot express recursion; fail here rather than at the API."""

    class Node(BaseModel):
        name: str
        children: list[Node] = []

    Node.model_rebuild()

    with pytest.raises(ValueError, match="recursive"):
        to_output_schema(Node)


def test_excessive_nesting_is_rejected():
    class L4(BaseModel):
        v: str

    class L3(BaseModel):
        v: L4

    class L2(BaseModel):
        v: L3

    class L1(BaseModel):
        v: L2

    # Four levels of nesting is comfortably inside the default limit.
    to_output_schema(L1)

    # Force the limit down to prove the guard fires rather than letting the API
    # reject an over-deep schema with a vaguer message.
    from app.llm import schema as schema_mod

    deep = to_output_schema(L1)
    with pytest.raises(SchemaTooDeepError):
        schema_mod._clean(deep, max_depth=3)


def test_constraints_are_still_enforced_client_side():
    """Stripping constraints from the wire schema must not weaken validation."""
    with pytest.raises(ValidationError):
        Order.model_validate({"reference": "nope", "items": []})


# --- field names that collide with schema keywords -------------------------


class Keywordy(BaseModel):
    """Every field here is named after a JSON Schema keyword.

    `title` is not hypothetical: the Requirements model has a Feature.title, and
    stripping it as a keyword is what made the first live run fail.
    """

    title: str = Field(description="A title")
    description: str
    type: str
    format: str
    default: str
    required: list[str]
    items: str
    properties: str
    enum: str
    examples: str


def _objects(node):
    """Every object schema in the tree, walked by structure rather than by key name.

    A plain search for dicts containing "properties" is wrong on exactly the
    models this file exists to test: a field *named* `properties` makes the
    properties map itself look like an object schema. The walk has to know which
    positions hold schemas, which is the same distinction the converter makes.
    """
    if isinstance(node, list):
        for item in node:
            yield from _objects(item)
        return
    if not isinstance(node, dict):
        return

    if "properties" in node:
        yield node
        for sub in node["properties"].values():
            yield from _objects(sub)
    for key in ("items", "not", "contains"):
        if key in node:
            yield from _objects(node[key])
    for key in ("anyOf", "allOf", "oneOf", "prefixItems"):
        if key in node:
            yield from _objects(node[key])


def test_fields_named_after_keywords_survive():
    schema = to_output_schema(Keywordy)
    assert set(schema["properties"]) == set(Keywordy.model_fields)


def test_required_never_names_a_field_that_was_stripped():
    """The exact failure the API reported: required a field not in properties."""
    for model in (Keywordy, Order):
        schema = to_output_schema(model)
        for obj in _objects(schema):
            missing = set(obj.get("required", [])) - set(obj["properties"])
            assert not missing, f"{model.__name__}: required but undefined: {missing}"


def test_the_real_pipeline_schemas_are_internally_consistent():
    """Guards every stage contract, not just the one that broke."""
    from app.schemas.requirements import Requirements

    for model in (Requirements,):
        schema = to_output_schema(model)
        for obj in _objects(schema):
            missing = set(obj.get("required", [])) - set(obj["properties"])
            assert not missing, f"{model.__name__}: required but undefined: {missing}"
            ordering = set(obj.get("propertyOrdering", []))
            assert ordering == set(obj["properties"]), "propertyOrdering must match properties"


def test_feature_title_specifically_survives():
    """The field that actually broke the first live run."""
    from app.schemas.requirements import Requirements

    schema = to_output_schema(Requirements)
    feature = schema["properties"]["features"]["items"]
    assert "title" in feature["properties"]
    assert "title" in feature["required"]
