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
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _objects(node):
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


def test_references_are_inlined():
    schema = to_output_schema(Order)
    assert "$defs" not in schema
    assert all("$ref" not in node for node in _walk(schema))
    assert schema["properties"]["items"]["items"]["properties"]["name"]["type"] == "string"


def test_unsupported_keywords_are_stripped():
    banned = {"default", "title", "$schema", "minimum", "maximum", "pattern", "minItems"}
    for node in _objects(to_output_schema(Order)):
        for name, sub in node["properties"].items():
            assert not banned & sub.keys(), f"leaked unsupported keyword in {name}: {sub}"
    assert not banned & to_output_schema(Order).keys()


def test_every_object_is_closed_and_fully_required():
    schema = to_output_schema(Order)
    for obj in _objects(schema):
        assert obj["additionalProperties"] is False
        assert obj["required"] == list(obj["properties"])


def test_optional_fields_are_still_listed_as_required():
    schema = to_output_schema(Order)
    assert set(schema["required"]) == {"reference", "items", "note"}
    assert {"type": "null"} in schema["properties"]["note"]["anyOf"]


def test_descriptions_survive():
    schema = to_output_schema(Order)
    assert schema["properties"]["note"]["description"] == "Optional note"
    assert schema["properties"]["items"]["items"]["properties"]["name"]["description"] == (
        "Item name"
    )


def test_response_format_envelope():
    fmt = to_response_format(Order)
    assert fmt == {
        "type": "json_schema",
        "json_schema": {
            "name": "Order",
            "strict": True,
            "schema": to_output_schema(Order),
        },
    }


def test_recursive_models_are_rejected_with_a_useful_message():

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

    to_output_schema(L1)

    from app.llm import schema as schema_mod

    deep = to_output_schema(L1)
    with pytest.raises(SchemaTooDeepError):
        schema_mod._clean(deep, max_depth=3)


def test_constraints_are_still_enforced_client_side():
    with pytest.raises(ValidationError):
        Order.model_validate({"reference": "nope", "items": []})


class Keywordy(BaseModel):
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


def test_fields_named_after_keywords_survive():
    schema = to_output_schema(Keywordy)
    assert set(schema["properties"]) == set(Keywordy.model_fields)
    assert set(schema["required"]) == set(Keywordy.model_fields)


def test_the_real_pipeline_schemas_are_strict_compatible():
    from app.schemas.plan import ProjectPlan
    from app.schemas.requirements import Requirements

    for model in (Requirements, ProjectPlan):
        schema = to_output_schema(model)
        for obj in _objects(schema):
            assert obj["additionalProperties"] is False, model.__name__
            assert set(obj["required"]) == set(obj["properties"]), model.__name__


def test_feature_title_specifically_survives():
    from app.schemas.requirements import Requirements

    schema = to_output_schema(Requirements)
    feature = schema["properties"]["features"]["items"]
    assert "title" in feature["properties"]
    assert "title" in feature["required"]
