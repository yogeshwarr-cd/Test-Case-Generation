"""Deterministic execution-failure classification and diagnostics.

This service is deliberately independent of LLMs and keeps the existing
FailureAnalysis schema/API compatible.  It provides a single, testable place
for execution code to classify exceptions and recommend the next safe action.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FailureDiagnostic:
    category: str
    recommended_action: str
    reason: str


class FailureAnalysisService:
    """Classify Playwright/runtime failures using deterministic signals."""

    def classify(
        self,
        error: BaseException,
        *,
        network_errors: list[str] | None = None,
        page_url: str | None = None,
    ) -> FailureDiagnostic:
        message = str(error).lower()
        error_name = type(error).__name__.lower()
        network = bool(network_errors)
        if network or any(token in message for token in ("net::", "dns", "connection", "network")):
            return FailureDiagnostic("Environment Issue", "Check network connectivity and target availability.", str(error))
        if any(token in message for token in ("timeout", "timed out", "exceeded")) or "timeout" in error_name:
            return FailureDiagnostic("Page Load Timeout", "Wait for the page state or retry navigation once.", str(error))
        if any(token in message for token in ("assert", "expected", "to be visible", "to have text", "not equal")):
            return FailureDiagnostic("Assertion Failure", "Compare the observed UI state with the expected result.", str(error))
        if any(token in message for token in ("locator", "strict mode", "detached", "element is not attached", "no node found", "not found")):
            return FailureDiagnostic("Locator Failure", "Re-discover the element and retry using the next stable locator.", str(error))
        if any(token in message for token in ("goto", "navigation", "navigation failed", "page closed", "target closed")):
            return FailureDiagnostic("Navigation Failure", "Synchronize navigation and verify the target URL before retrying.", str(error))
        if any(token in message for token in ("fixture", "precondition", "not authenticated", "login required")):
            return FailureDiagnostic("Environment Issue", "Prepare the required fixture or authenticated storage state.", str(error))
        if any(token in message for token in ("permission", "executable", "browser", "playwright")):
            return FailureDiagnostic("Environment Issue", "Verify browser installation and process permissions.", str(error))
        return FailureDiagnostic("Automation Error", "Inspect the captured trace and retry only the failed automation action.", str(error))

    def as_report_fields(self, diagnostic: FailureDiagnostic) -> dict[str, Any]:
        """Return additive diagnostic fields for logs/UI consumers."""
        return {
            "failure_category": diagnostic.category,
            "recommended_action": diagnostic.recommended_action,
            "failure_reason": diagnostic.reason,
        }

