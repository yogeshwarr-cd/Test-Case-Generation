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
    application_map_version: str | None = None
    requirement_version: str | None = None
    lifecycle_status: Literal[
        "Valid", "Needs Review", "Obsolete", "Regeneration Required"
    ] = "Valid"


class ScriptGenerationResponse(BaseModel):
    generation_id: str
    application_url: str
    reachable: bool
    page_title: str | None = None
    discovered_elements: list[DiscoveredElement] = Field(default_factory=list)
    application_map: dict[str, Any] = Field(default_factory=dict)
    application_map_version: str | None = None
    requirement_version: str | None = None
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
    intelligence: FailureIntelligence | None = None


class RequirementMapping(BaseModel):
    epic: list[dict[str, str]] = Field(default_factory=list)
    feature: list[dict[str, str]] = Field(default_factory=list)
    user_story: list[dict[str, str]] = Field(default_factory=list)
    acceptance_criteria: list[dict[str, str]] = Field(default_factory=list)
    scenario: list[dict[str, str]] = Field(default_factory=list)
    test_case: list[dict[str, str]] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class FailureEvidence(BaseModel):
    screenshot: str | None = None
    dom_snapshot: str | None = None
    playwright_trace: str | None = None
    failed_locator: str | None = None
    page_url: str | None = None
    console_findings: list[str] = Field(default_factory=list)
    network_findings: list[str] = Field(default_factory=list)
    evidence_summary: list[str] = Field(default_factory=list)


class DeveloperImplementationPlan(BaseModel):
    ticket_title: str
    feature_affected: str
    user_story_reference: list[str] = Field(default_factory=list)
    test_scenario_reference: str
    test_case_reference: str
    problem_summary: str
    missing_functionality: str = ""
    root_cause_analysis: str
    expected_behavior: str
    actual_behavior: str
    ui_changes_required: list[str] = Field(default_factory=list)
    backend_api_changes_required: list[str] = Field(default_factory=list)
    database_changes: list[str] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)
    acceptance_criteria_to_satisfy: list[str] = Field(default_factory=list)
    suggested_implementation_steps: list[str] = Field(default_factory=list)
    priority: Literal["Critical", "High", "Medium", "Low"]
    estimated_development_effort: str
    jira_description: str


class AutomationRecommendation(BaseModel):
    script_changes: list[str] = Field(default_factory=list)
    locator_strategy: list[str] = Field(default_factory=list)
    wait_strategy: list[str] = Field(default_factory=list)
    assertion_strategy: list[str] = Field(default_factory=list)
    navigation_strategy: list[str] = Field(default_factory=list)


class RetestStrategy(BaseModel):
    reuse_generation_id: bool = True
    original_script_id: str
    steps: list[str] = Field(default_factory=list)
    verification_scope: list[str] = Field(default_factory=list)
    acceptance_criteria_checklist: list[dict[str, Any]] = Field(default_factory=list)


class FailureIntelligence(BaseModel):
    classification: Literal[
        "APPLICATION_DEFECT",
        "MISSING_FEATURE",
        "REQUIREMENT_MISMATCH",
        "AUTOMATION_DEFECT",
        "ENVIRONMENT_FAILURE",
        "TEST_DATA_FAILURE",
        "INCONCLUSIVE",
    ] = "INCONCLUSIVE"
    root_cause_category: Literal[
        "Missing application functionality",
        "Incorrect business logic",
        "UI implementation issue",
        "Locator or automation issue",
        "Requirement mismatch",
        "Navigation problem",
        "Validation issue",
        "API/Backend failure",
        "Environment or configuration issue",
    ]
    confidence: float = Field(ge=0, le=1)
    confidence_gate: dict[str, Any] = Field(default_factory=dict)
    is_application_issue: bool
    deviation_step: dict[str, Any] = Field(default_factory=dict)
    requirement_mapping: RequirementMapping
    root_cause_analysis: str
    expected_behavior: str
    actual_behavior: str
    evidence: FailureEvidence
    developer_implementation_plan: DeveloperImplementationPlan | None = None
    automation_recommendation: AutomationRecommendation | None = None
    acceptance_criteria_checklist: list[dict[str, Any]] = Field(default_factory=list)
    recommended_fix: list[str] = Field(default_factory=list)
    retest_strategy: RetestStrategy


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
    requirement_coverage: dict[str, Any] = Field(default_factory=dict)
    failed_requirement_mapping: list[dict[str, Any]] = Field(default_factory=list)
    developer_ready_tickets: list[DeveloperImplementationPlan] = Field(default_factory=list)
    developer_execution_reports: list[dict[str, Any]] = Field(default_factory=list)
    qa_diagnostic_reports: list[dict[str, Any]] = Field(default_factory=list)
    traceability_chains: list[dict[str, Any]] = Field(default_factory=list)
    requirement_version: str | None = None
    script_lifecycle: list[dict[str, Any]] = Field(default_factory=list)
    retest_verification: list[dict[str, Any]] = Field(default_factory=list)


class AutomationHealth(BaseModel):
    status: Literal["healthy", "degraded", "disabled"]
    playwright_available: bool
    browser_available: bool
    skyvern_enabled: bool
    skyvern_api_reachable: bool | None = None
    skyvern_configuration_valid: bool
    details: dict[str, str] = Field(default_factory=dict)
