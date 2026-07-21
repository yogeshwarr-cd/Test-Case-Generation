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
    page_url: str | None = None
    ui_element: str | None = None
    screenshot: str | None = None
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
    execution_time_seconds: float
    success_percentage: float
    results: list[ScriptExecutionResult]


class AutomationHealth(BaseModel):
    status: Literal["healthy", "degraded", "disabled"]
    playwright_available: bool
    browser_available: bool
    skyvern_enabled: bool
    skyvern_api_reachable: bool | None = None
    skyvern_configuration_valid: bool
    details: dict[str, str] = Field(default_factory=dict)
