from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel

_UNSUPPORTED_KEYS = frozenset(
    {
        "default",
        "examples",
        "title",
        "$comment",
        "$schema",
        "$id",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minProperties",
        "maxProperties",
        "patternProperties",
        "readOnly",
        "writeOnly",
        "deprecated",
        "discriminator",
    }
)


class SchemaTooDeepError(ValueError):
    pass


def _resolve(ref: str, defs: dict[str, Any]) -> dict[str, Any]:
    name = ref.rsplit("/", 1)[-1]
    if name not in defs:
        raise ValueError(f"unresolvable schema reference: {ref}")
    return defs[name]


def _inline(node: Any, defs: dict[str, Any], seen: tuple[str, ...] = ()) -> Any:
    if isinstance(node, list):
        return [_inline(item, defs, seen) for item in node]
    if not isinstance(node, dict):
        return node

    if "$ref" in node:
        ref = node["$ref"]
        if ref in seen:
            raise ValueError(
                f"recursive schema reference {ref}; model a tree as a flat list "
                "with parent-id references instead"
            )
        target = _inline(_resolve(ref, defs), defs, (*seen, ref))
        extras = {k: _inline(v, defs, seen) for k, v in node.items() if k != "$ref"}
        return {**target, **extras}

    return {k: _inline(v, defs, seen) for k, v in node.items()}


_SCHEMA_MAPS = frozenset({"properties", "$defs", "definitions"})

_SCHEMA_LISTS = frozenset({"anyOf", "allOf", "oneOf", "prefixItems"})

_SCHEMA_VALUES = frozenset({"items", "not", "contains", "additionalItems"})


def _clean(node: Any, depth: int = 0, max_depth: int = 12) -> Any:
    if depth > max_depth:
        raise SchemaTooDeepError(f"schema nests deeper than {max_depth} levels")
    if not isinstance(node, dict):
        return node

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _UNSUPPORTED_KEYS or key == "additionalProperties":
            continue
        if key in _SCHEMA_MAPS and isinstance(value, dict):
            out[key] = {name: _clean(sub, depth + 1, max_depth) for name, sub in value.items()}
        elif key in _SCHEMA_LISTS and isinstance(value, list):
            out[key] = [_clean(item, depth + 1, max_depth) for item in value]
        elif key in _SCHEMA_VALUES:
            out[key] = _clean(value, depth + 1, max_depth)
        else:
            out[key] = value

    if "properties" in out:
        out.setdefault("type", "object")
        out["required"] = list(out["properties"].keys())
        out["additionalProperties"] = False

    return out


def to_output_schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = deepcopy(model.model_json_schema(ref_template="#/$defs/{model}"))
    defs = schema.pop("$defs", {})
    return _clean(_inline(schema, defs))


def to_response_format(model: type[BaseModel]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": model.__name__,
            "strict": True,
            "schema": to_output_schema(model),
        },
    }
