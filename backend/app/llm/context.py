from __future__ import annotations

from collections.abc import Iterable
from typing import Any


_RELATED_COLLECTIONS = (
    "functional_requirements",
    "non_functional_requirements",
    "epics",
    "features",
    "acceptance_criteria",
    "business_rules",
    "dependencies",
    "constraints",
)
_NOISE_KEYS = {
    "metadata",
    "created_at",
    "updated_at",
    "timestamp",
    "timestamps",
    "generation_metadata",
    "previous_outputs",
}


def batches(items: list[Any], size: int) -> Iterable[list[Any]]:
    size = max(1, size)
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _clean(item)
            for key, item in value.items()
            if key not in _NOISE_KEYS and item not in (None, "", [], {})
        }
    if isinstance(value, list):
        cleaned = [_clean(item) for item in value]
        return list(dict.fromkeys(map(str, cleaned))) if all(
            isinstance(item, str) for item in cleaned
        ) else cleaned
    return value


def _references(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "id" or key.endswith("_id") or key.endswith("_ids") or key.endswith("references"):
                found.update(_references(item))
            elif isinstance(item, (dict, list)):
                found.update(_references(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_references(item))
    elif value is not None:
        found.add(str(value))
    return found


def _item_id(item: Any) -> str | None:
    if isinstance(item, dict):
        for key in ("id", "requirement_id", "acceptance_criteria_id", "feature_id", "epic_id"):
            if item.get(key):
                return str(item[key])
    return None


def scoped_context(context: dict[str, Any], selected: list[Any]) -> dict[str, Any]:
    """Return prompt-safe context linked to the current story or scenario batch."""
    selected_clean = _clean(selected)
    references = _references(selected_clean)
    traceability = []
    for entry in context.get("traceability_map", []):
        source_id = str(entry.get("source_id", ""))
        targets = {str(item) for item in entry.get("target_ids", [])}
        if source_id in references or references.intersection(targets):
            traceability.append(_clean(entry))
            references.add(source_id)
            references.update(targets)

    result: dict[str, Any] = {
        "project_id": context.get("project_id"),
        "tech_stack": _clean(context.get("tech_stack", {})),
        "current_items": selected_clean,
    }
    related_stories = []
    for story in context.get("user_stories", []):
        identifier = _item_id(story)
        if story in selected or (identifier and identifier in references):
            related_stories.append(_clean(story))
    if related_stories:
        result["user_stories"] = related_stories
    for name in _RELATED_COLLECTIONS:
        related = []
        for item in context.get(name, []):
            identifier = _item_id(item)
            if identifier and identifier in references:
                related.append(_clean(item))
        if related:
            result[name] = related
    if traceability:
        result["traceability_map"] = traceability
    return {key: value for key, value in result.items() if value not in (None, "", [], {})}
