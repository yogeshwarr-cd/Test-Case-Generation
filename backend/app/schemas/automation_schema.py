from __future__ import annotations

from typing import Any, Literal
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, SecretStr, model_validator


class GenerateScriptsRequest(BaseModel):
    workflow_id: UUID
    application_url: HttpUrl
    crawl_id: str


class CrawlApplicationRequest(BaseModel):
    workflow_id: UUID
    application_url: HttpUrl
    page_limit: int = Field(default=250, ge=1, le=500)
    depth_limit: int = Field(default=15, ge=1, le=20)
    max_execution_time_seconds: int = Field(default=300, ge=30, le=3600)
    repeated_state_limit: int = Field(default=5, ge=1, le=20)
    testing_scope: Literal["full_application", "specific_page"] = "full_application"
    authentication: PlaywrightAuthentication | None = None



class CrawlAnalysisResponse(BaseModel):
    crawl_id: str
    application_url: str
    crawl_status: Literal["crawl_completed", "crawl_incomplete", "crawl_blocked"]
    page_title: str | None = None
    pages_crawled: int
    elements_found: int
    crawl_report: dict[str, Any] = Field(default_factory=dict)
    application_map: dict[str, Any] = Field(default_factory=dict)
    discovered_elements: list[DiscoveredElement] = Field(default_factory=list)


class WorkflowCrawlJobResponse(BaseModel):
    """State and results for a cancellable workflow-backed crawl."""

    job_id: str
    status: Literal["queued", "running", "stopping", "completed", "failed"]
    stop_requested: bool = False
    progress: dict[str, Any] = Field(default_factory=dict)
    crawl: CrawlAnalysisResponse | None = None
    generation: ScriptGenerationResponse | None = None
    error: str | None = None


class DiscoveredElement(BaseModel):
    role: str | None = None
    name: str | None = None
    aria_label: str | None = None
    label: str | None = None
    test_id: str | None = None
    tag: str
    input_type: str | None = None
    placeholder: str | None = None
    visible_text: str | None = None
    href: str | None = None
    page_url: str | None = None
    page_title: str | None = None
    parent_page: str | None = None
    navigation_path: list[str] = Field(default_factory=list)
    dom_snapshot: str | None = None
    application_state: dict[str, Any] = Field(default_factory=dict)
    discovery_timestamp: datetime | None = None
    options: list[dict[str, str]] = Field(default_factory=list)
    checked: bool | None = None
    element_id: str | None = None
    css_selector: str | None = None
    navigation_candidate: bool = False
    locator_validated: bool = False


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
        "Valid", "Needs Review", "Obsolete", "Regeneration Required", "Blocked"
    ] = "Valid"
    page_url: str | None = None
    page_elements: list[dict[str, Any]] = Field(default_factory=list)
    executable_steps: list[dict[str, Any]] = Field(default_factory=list)


class ScriptGenerationResponse(BaseModel):
    generation_id: str
    application_url: str
    reachable: bool
    page_title: str | None = None
    discovered_elements: list[DiscoveredElement] = Field(default_factory=list)
    application_map: dict[str, Any] = Field(default_factory=dict)
    application_map_version: str | None = None
    requirement_version: str | None = None
    crawl_status: Literal[
        "crawl_started", "crawl_in_progress", "challenge_detected",
        "crawl_completed", "crawl_incomplete", "crawl_blocked",
        "script_generation_started", "script_generation_completed",
    ] = "script_generation_completed"
    crawl_report: dict[str, Any] = Field(default_factory=dict)
    scripts: list[GeneratedScript]


class PlaywrightAuthentication(BaseModel):
    auth_mode: Literal["no_auth", "credentials", "existing_session"] = "no_auth"
    identifier: str | None = None
    email: str | None = None
    username: str | None = None
    password: SecretStr | None = None
    session_state: dict[str, Any] | str | None = None

    @property
    def get_identifier(self) -> str | None:
        return self.identifier or self.email or self.username

    @model_validator(mode="after")
    def validate_pair(self) -> "PlaywrightAuthentication":
        ident = self.get_identifier
        pass_val = self.password.get_secret_value() if self.password else None
        if self.auth_mode == "credentials" or ident or pass_val:
            if not ident or not pass_val:
                raise ValueError("Both identifier (email/username/etc.) and password are required for credentials authentication.")
            self.auth_mode = "credentials"
        elif self.auth_mode == "existing_session" or self.session_state is not None:
            if self.session_state is None:
                raise ValueError("session_state is required for existing_session authentication.")
            self.auth_mode = "existing_session"
        return self


class ExecuteScriptsRequest(BaseModel):
    generation_id: str
    mode: Literal["automated", "manual"] = "automated"
    execution_profile: Literal["fast", "standard", "diagnostic"] = "standard"
    testing_scope: Literal["full_application", "specific_page"] = "full_application"
    authentication: PlaywrightAuthentication | None = None


class FailureAnalysis(BaseModel):
    test_case_id: str
    issue_title: str | None = None
    confidence_score: float = Field(default=0, ge=0, le=1)
    affected_feature: str | None = None
    mapped_user_stories: list[dict[str, str]] = Field(default_factory=list)
    mapped_acceptance_criteria: list[dict[str, str]] = Field(default_factory=list)
    test_scenario: dict[str, Any] = Field(default_factory=dict)
    test_case_title: str | None = None
    failed_step: int | None = None
    failed_action: str | None = None
    failure_stage: str | None = None
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
        "Page Failure",
        "Application Failure",
        "Generated Script Defect",
        "Invalid Test Step",
        "Test Data Failure",
        "API Failure",
        "Authentication Failure",
        "Application State Failure",
        "Blocked Page",
        "Dynamic Content Timeout",
        # Legacy labels
        "Script Generation",
        "Locator",
        "Navigation",
        "Application",
    ] = "Application"
    page_url: str | None = None
    expected_page_url: str | None = None
    page_title: str | None = None
    http_response_status: int | None = None
    execution_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    ui_element: str | None = None
    exact_locator: str | None = None
    locator_details: dict[str, Any] = Field(default_factory=dict)
    alternate_locators_attempted: list[dict[str, Any]] = Field(default_factory=list)
    locator_diagnosis: str | None = None
    input_details: dict[str, Any] = Field(default_factory=dict)
    navigation_details: dict[str, Any] = Field(default_factory=dict)
    assertion_details: dict[str, Any] = Field(default_factory=dict)
    api_details: dict[str, Any] = Field(default_factory=dict)
    application_state_details: dict[str, Any] = Field(default_factory=dict)
    captured_dom_text: str | None = None
    reproduction_steps: list[str] = Field(default_factory=list)
    severity: Literal["Critical", "High", "Medium", "Low"] = "Medium"
    priority: Literal["Critical", "High", "Medium", "Low"] = "Medium"
    developer_issue_recommended: bool = False
    mapping_explanation: str | None = None
    screenshot: str | None = None
    dom_snapshot: str | None = None   # path to saved DOM HTML snapshot
    trace_path: str | None = None     # path to saved Playwright trace zip
    console_logs: list[str] = Field(default_factory=list)
    network_errors: list[str] = Field(default_factory=list)
    stack_trace: str | None = None
    seacrawl_attempted: bool = False
    seacrawl_succeeded: bool = False
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
    status: Literal["passed", "failed", "skipped", "blocked"]
    duration_seconds: float
    error_message: str | None = None
    failure: FailureAnalysis | None = None
    traceability: dict[str, Any] = Field(default_factory=dict)


class ExecutionReport(BaseModel):
    execution_id: str
    generation_id: str
    execution_status: Literal["execution_started", "execution_completed"] = "execution_completed"
    mode: Literal["automated", "manual"]
    total_scripts: int
    passed_scripts: int
    failed_scripts: int
    skipped_scripts: int
    blocked_scripts: int = 0
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


class ExecutionJobResponse(BaseModel):
    """State of an execution owned by the backend rather than an HTTP request."""

    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    report: ExecutionReport | None = None
    error: str | None = None


class CompareExecutionRequest(BaseModel):
    execution_id: str


class TraceabilityComparisonReport(BaseModel):
    comparison_id: str
    execution_id: str
    generation_id: str
    summary: dict[str, Any]
    scenario_coverage: list[dict[str, Any]] = Field(default_factory=list)
    test_case_coverage: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    inconsistencies: list[dict[str, Any]] = Field(default_factory=list)


class AutomationHealth(BaseModel):
    status: Literal["healthy", "degraded", "disabled"]
    playwright_available: bool
    browser_available: bool
    seacrawl_enabled: bool
    seacrawl_api_reachable: bool | None = None
    seacrawl_configuration_valid: bool
    details: dict[str, str] = Field(default_factory=dict)


class CrawlAndGenerateRequest(BaseModel):
    """Standalone request: crawl a URL and generate Playwright scripts per page.

    No workflow or pre-existing test cases are required.
    """

    url: HttpUrl
    page_limit: int = Field(default=250, ge=1, le=500)
    depth_limit: int = Field(default=15, ge=1, le=20)
    max_execution_time_seconds: int = Field(default=300, ge=30, le=3600)
    repeated_state_limit: int = Field(default=5, ge=1, le=20)
    testing_scope: Literal["full_application", "specific_page"] = "full_application"
    authentication: PlaywrightAuthentication | None = None


class CrawlGenerationResponse(BaseModel):
    """Result of a standalone URL crawl + script generation."""

    crawl_id: str
    url: str
    page_title: str | None = None
    pages_crawled: int
    elements_found: int
    crawl_status: Literal[
        "crawl_completed", "crawl_incomplete", "crawl_blocked",
        "script_generation_completed",
    ] = "script_generation_completed"
    crawl_report: dict[str, Any] = Field(default_factory=dict)
    scripts: list[GeneratedScript]
    discovered_elements: list[DiscoveredElement] = Field(default_factory=list)
    application_map: dict[str, Any] = Field(default_factory=dict)


class CrawlJobResponse(BaseModel):
    """Current state of a cancellable standalone crawl."""

    job_id: str
    status: Literal["queued", "running", "stopping", "completed", "failed"]
    stop_requested: bool = False
    progress: dict[str, Any] = Field(default_factory=dict)
    result: CrawlGenerationResponse | None = None
    error: str | None = None
