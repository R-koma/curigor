import copy
import json
from collections.abc import Iterator
from typing import Any, NamedTuple


class AspectRef(NamedTuple):
    id: str
    name: str
    depth: int


def parse_aspect_map(value: object) -> dict[str, Any] | None:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    if not isinstance(value, dict) or not isinstance(value.get("aspects"), list):
        return None
    return value


def _walk(nodes: list[dict[str, Any]], prefix: str, depth: int) -> Iterator[tuple[str, dict[str, Any], int]]:
    for index, node in enumerate(nodes, start=1):
        aspect_id = f"{prefix}-{index}" if prefix else f"a{index}"
        yield aspect_id, node, depth
        yield from _walk(node.get("children") or [], aspect_id, depth + 1)


def with_aspect_ids(aspect_map: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(aspect_map)
    for aspect_id, node, _ in _walk(result.get("aspects") or [], "", 0):
        node["id"] = aspect_id
    return result


def iter_aspects(aspect_map: dict[str, Any]) -> Iterator[AspectRef]:
    for aspect_id, node, depth in _walk(aspect_map.get("aspects") or [], "", 0):
        yield AspectRef(aspect_id, str(node.get("name", "")), depth)


def aspect_names_by_id(aspect_map: dict[str, Any] | None) -> dict[str, str]:
    if aspect_map is None:
        return {}
    return {ref.id: ref.name for ref in iter_aspects(aspect_map)}
