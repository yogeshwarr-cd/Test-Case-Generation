"""Deterministic, explainable semantic mapping for automation generation."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Iterable

_STOP = {"the", "a", "an", "and", "or", "to", "with", "field", "element", "verify", "enter", "click", "press", "check", "select"}
MAPPING_CONFIDENCE_THRESHOLD = 0.70

def _tokens(value: Any) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]+", str(value or "").casefold()) if len(x) > 1 and x not in _STOP}

@dataclass(frozen=True)
class MappingCandidate:
    element: dict[str, Any]
    confidence: float
    reason: str

    @property
    def needs_review(self) -> bool:
        """Low-confidence matches are review/fallback candidates, never silently trusted."""
        return self.confidence < MAPPING_CONFIDENCE_THRESHOLD

def map_element(instruction: str, elements: Iterable[dict[str, Any]]) -> MappingCandidate | None:
    query = _tokens(instruction)
    if not query:
        return None
    # Attribute order deliberately mirrors the supported locator contract.
    fields = (("test_id", 1.0), ("id", .95), ("element_id", .95),
              ("aria_label", .90), ("label", .86), ("role", .78),
              ("name", .74), ("html_name", .74), ("placeholder", .70),
              ("visible_text", .55), ("text", .50))
    candidates: list[MappingCandidate] = []
    for element in elements:
        score = 0.0
        matched: set[str] = set()
        for field, weight in fields:
            overlap = query & _tokens(element.get(field))
            candidate_score = weight * len(overlap) / len(query) if overlap else 0
            if candidate_score > score:
                score, matched = candidate_score, overlap
        if score:
            candidates.append(MappingCandidate(element, round(min(score, 1), 4), f"matched {', '.join(sorted(matched))}"))
    # Stable tie-breaking prevents run-to-run locator drift.
    return max(candidates, key=lambda item: (item.confidence, _locator_rank(item.element), str(item.element.get("page_url", "")), str(item.element.get("id", "")))) if candidates else None

def _locator_rank(element: dict[str, Any]) -> int:
    for index, field in enumerate(("test_id", "id", "element_id", "aria_label", "label", "role", "name", "html_name", "placeholder", "visible_text", "text")):
        if element.get(field):
            return 100 - index
    return 0

def build_intent(test_case: dict[str, Any], elements: list[dict[str, Any]]) -> dict[str, Any]:
    steps = []
    intent_id = str(test_case.get("automation_intent_id") or f"intent-{test_case.get('test_case_id', 'unknown')}")
    for step in test_case.get("steps", []):
        match = map_element(str(step.get("action", "")), elements)
        steps.append({"step_number": step.get("step_number"), "action": step.get("action", ""),
                      "expected_result": step.get("expected_result", ""),
                      "match": ({"confidence": match.confidence, "needs_review": match.needs_review, "reason": match.reason, "element": match.element} if match else None)})
    return {"automation_intent_id": intent_id, "test_case_id": str(test_case.get("test_case_id", "")),
            "scenario_id": str(test_case.get("scenario_id", "")),
            "requirement_ids": list(test_case.get("requirement_ids", []) or []),
            "user_story_ids": list(test_case.get("user_story_ids", []) or []), "steps": steps}
