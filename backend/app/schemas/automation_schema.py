from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class GenerateScriptsRequest(BaseModel):
    workflow_id: UUID
    application_url: HttpUrl


class DiscoveredElement(BaseModel):
    role: str | None = None
    name: str | None = None
    label: str | None = None
    test_id: str | None = None
    tag: str
    input_type: str | None = None
    placeholder: str | None = None
    visible_text: str | None = None
    href: str | None = None
    page_url: str | None = None
    options: list[dict[str, str]] = Field(default_factory=list)
    checked: bool | None = None


class GeneratedScript(BaseModel):
    script_id: str
    workflow_id: UUID
    test_case_id: str
    scenario_id: str
    name: str
    application_url: str
    language: Literal["python"] = "python"
    source: str
    download_path: str
    requirement_ids: list[str] = Field(default_factory=list)
    user_story_ids: list[str] = Field(default_factory=list)


class ScriptGenerationResponse(BaseModel):
    generation_id: str
    application_url: str
    reachable: bool
    page_title: str | None = None
    discovered_elements: list[DiscoveredElement] = Field(default_factory=list)
    scripts: list[GeneratedScript]


class ExecuteScriptsRequest(BaseModel):
    generation_id: str
    mode: Literal["automated", "manual"] = "automated"


class FailureAnalysis(BaseModel):
    test_case_id: str
    failed_step: int | None = None
    expected_result: str | None = None
    actual_result: str | None = None
    failure_reason: str
    # Precise failure categories (legacy short labels kept for backwards compat
    # so that existing stored reports and mock-mode paths still deserialise).
    failure_category: Literal[
        # Precise categories (requirements 10)
        "Locator Failure",
        "Navigation Failure",
        "Application Feature Missing",
        "Page Load Timeout",
        "Assertion Failure",
        "Environment Issue",
        # Legacy labels
        "Script Generation",
        "Locator",
        "Navigation",
        "Application",
    ] = "Application"
    page_url: str | None = None
    ui_element: str | None = None
    screenshot: str | None = None
    dom_snapshot: str | None = None   # path to saved DOM HTML snapshot
    trace_path: str | None = None     # path to saved Playwright trace zip
    console_logs: list[str] = Field(default_factory=list)
    network_errors: list[str] = Field(default_factory=list)
    stack_trace: str | None = None
    skyvern_attempted: bool = False
    skyvern_succeeded: bool = False


class ScriptExecutionResult(BaseModel):
    script_id: str
    script_name: str
    test_case_id: str
    scenario_id: str
    status: Literal["passed", "failed", "skipped"]
    duration_seconds: float
    error_message: str | None = None
    failure: FailureAnalysis | None = None
    traceability: dict[str, Any] = Field(default_factory=dict)


class ExecutionReport(BaseModel):
    execution_id: str
    generation_id: str
    mode: Literal["automated", "manual"]
    total_scripts: int
    passed_scripts: int
    failed_scripts: int
    skipped_scripts: int
    rejected_scripts: int = 0
    execution_time_seconds: float
    success_percentage: float
    results: list[ScriptExecutionResult]
    rejected_results: list[dict[str, Any]] = Field(default_factory=list)
    overall_summary: dict[str, Any] = Field(default_factory=dict)


class CompareExecutionRequest(BaseModel):
    workflow_id: UUID


class TraceabilityItem(BaseModel):
    artifact_type: Literal["scenario", "test_case"]
    artifact_id: str
    title: str
    status: Literal["covered", "partial", "missing"]
    coverage_percentage: float
    matched_script_ids: list[str] = Field(default_factory=list)
    matched_evidence: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class TraceabilityReport(BaseModel):
    comparison_id: str
    execution_id: str
    generation_id: str
    workflow_id: UUID
    total_scenarios: int
    total_test_cases: int
    covered: int
    partial: int
    missing: int
    overall_coverage_percentage: float
    items: list[TraceabilityItem] = Field(default_factory=list)
    uncovered_ui_scripts: list[dict[str, Any]] = Field(default_factory=list)
    summary: str


class AutomationHealth(BaseModel):
    status: Literal["healthy", "degraded", "disabled"]
    playwright_available: bool
    browser_available: bool
    skyvern_enabled: bool
    skyvern_api_reachable: bool | None = None
    skyvern_configuration_valid: bool
    details: dict[str, str] = Field(default_factory=dict)
