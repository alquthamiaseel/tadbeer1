"""Convert Pydantic models into JSON Schemas the Gemini API accepts.

Gemini constrains generation to a schema, but only supports a subset of JSON
Schema, and its own docs warn that "very large or deeply nested schemas may be
rejected". Pydantic emits keywords outside that subset and, for nested models,
emits ``$ref`` pointers into a ``$defs`` block. Two transformations happen here:

* **References are inlined.** A schema with no ``$ref``/``$defs`` is the shape
  least likely to be rejected, and it removes any question of how deeply the
  API follows pointers.
* **Unsupported keywords are dropped**, then re-applied client-side by
  validating the response with the same Pydantic model. The model stays the
  single definition of the contract.

``propertyOrdering`` is added deliberately. Google documents that the order
properties are generated in affects output quality, and that without this the
order is unspecified — so we pin it to the field order the model declares.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel

#: Keywords Gemini does not accept. Constraints are still enforced — client
#: side, when the response is validated against the Pydantic model.
_UNSUPPORTED_KEYS = frozenset(
    {
        "additionalProperties",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "uniqueItems",
        "minProperties",
        "maxProperties",
        "patternProperties",
        "default",
        "examples",
        "title",
        "$comment",
        "$schema",
        "$id",
        "readOnly",
        "writeOnly",
        "deprecated",
        "discriminator",
    }
)


class SchemaTooDeepError(ValueError):
    """A model nests deeper than the API is willing to accept."""


def _resolve(ref: str, defs: dict[str, Any]) -> dict[str, Any]:
    name = ref.rsplit("/", 1)[-1]
    if name not in defs:
        raise ValueError(f"unresolvable schema reference: {ref}")
    return defs[name]


def _inline(node: Any, defs: dict[str, Any], seen: tuple[str, ...] = ()) -> Any:
    """Replace every ``$ref`` with the definition it points at."""
    if isinstance(node, list):
        return [_inline(item, defs, seen) for item in node]
    if not isinstance(node, dict):
        return node

    if "$ref" in node:
        ref = node["$ref"]
        if ref in seen:
            # Gemini has no way to express a recursive schema. Say so here
            # rather than let the API reject it with a vaguer message.
            raise ValueError(
                f"recursive schema reference {ref}; model a tree as a flat list "
                "with parent-id references instead"
            )
        target = _inline(_resolve(ref, defs), defs, (*seen, ref))
        # Keywords alongside a $ref (usually `description`) override the target's.
        extras = {k: _inline(v, defs, seen) for k, v in node.items() if k != "$ref"}
        return {**target, **extras}

    return {k: _inline(v, defs, seen) for k, v in node.items()}


#: Keys whose value is a mapping of *name* -> schema. The names are user data —
#: a field may legitimately be called "title" or "default" — so they must never
#: be filtered as if they were schema keywords.
_SCHEMA_MAPS = frozenset({"properties", "$defs", "definitions"})

#: Keys whose value is a list of schemas.
_SCHEMA_LISTS = frozenset({"anyOf", "allOf", "oneOf", "prefixItems"})

#: Keys whose value is a single schema.
_SCHEMA_VALUES = frozenset({"items", "not", "contains", "additionalItems"})

#: Keys whose value is plain data, not a schema — do not walk into it.
_OPAQUE = frozenset({"required", "enum", "const", "propertyOrdering"})


def _clean(node: Any, depth: int = 0, max_depth: int = 12) -> Any:
    """Strip unsupported keywords, without confusing keywords for field names.

    The distinction matters: under ``properties`` the keys are the model's own
    field names. Filtering those by keyword name silently deletes any field
    called ``title``, ``default``, ``format`` and so on, while ``required`` goes
    on demanding them — which the API rejects as a field that is required but
    not defined.
    """
    if depth > max_depth:
        raise SchemaTooDeepError(f"schema nests deeper than {max_depth} levels")
    if not isinstance(node, dict):
        return node

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _UNSUPPORTED_KEYS:
            continue
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            out[key] = {name: _clean(sub, depth + 1, max_depth) for name, sub in value.items()}
        elif key in _SCHEMA_LISTS and isinstance(value, list):
            out[key] = [_clean(item, depth + 1, max_depth) for item in value]
        elif key in _SCHEMA_VALUES:
            out[key] = _clean(value, depth + 1, max_depth)
        elif key in _OPAQUE:
            out[key] = value
        else:
            out[key] = value

    # Pin generation order to the order the model declares its fields.
    if "properties" in out:
        out.setdefault("type", "object")
        out["propertyOrdering"] = list(out["properties"].keys())

    return out


def to_output_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return a Gemini-acceptable JSON Schema for ``model``."""
    schema = deepcopy(model.model_json_schema(ref_template="#/$defs/{model}"))
    defs = schema.pop("$defs", {})
    return _clean(_inline(schema, defs))


def to_response_format(model: type[BaseModel]) -> dict[str, Any]:
    """Return the ``response_format`` value that constrains output to ``model``."""
    return {
        "type": "text",
        "mime_type": "application/json",
        "schema": to_output_schema(model),
    }
