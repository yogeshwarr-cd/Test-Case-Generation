from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SessionState(StrEnum):
    waiting_for_human = "waiting_for_human"
    recording = "recording"
    generating_scripts = "generating_scripts"
    validating_scripts = "validating_scripts"
    executing_scripts = "executing_scripts"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ActionKind(StrEnum):
    click = "click"
    fill = "fill"
    select = "select"
    check = "check"
    uncheck = "uncheck"
    navigation = "navigation"


class StartSessionRequest(BaseModel):
    workflow_id: uuid.UUID
    scenario_id: str = Field(min_length=1, max_length=200)
    test_case_id: str = Field(min_length=1, max_length=200)
    application_url: HttpUrl


class RecordedAction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sequence: int = 0
    kind: ActionKind
    page_url: str
    role: str | None = None
    accessible_name: str | None = None
    label: str | None = None
    placeholder: str | None = None
    test_id: str | None = None
    stable_id: str | None = None
    stable_css: str | None = None
    exact_text: str | None = None
    input_value: str | None = None
    navigation_url: str | None = None
    visible_result: str | None = None
    occurred_at: datetime = Field(default_factory=utcnow)

    @property
    def is_password(self) -> bool:
        values = (
            self.role,
            self.accessible_name,
            self.label,
            self.placeholder,
            self.stable_id,
        )
        return any("password" in (value or "").lower() for value in values)

    def redacted(self) -> "RecordedAction":
        if self.is_password:
            return self.model_copy(update={"input_value": "<REDACTED>"})
        return self


class GeneratedHumanScript(BaseModel):
    script_id: str
    workflow_id: uuid.UUID
    scenario_id: str
    test_case_id: str
    name: str
    application_url: str
    source: str
    action_count: int


class HumanExecutionSession(BaseModel):
    session_id: str
    workflow_id: uuid.UUID
    scenario_id: str
    test_case_id: str
    application_url: str
    state: SessionState = SessionState.waiting_for_human
    browser_status: str = "launching"
    recorded_action_count: int = 0
    actions: list[RecordedAction] = Field(default_factory=list)
    generated_scripts: list[GeneratedHumanScript] = Field(default_factory=list)
    generation_id: str | None = None
    execution_id: str | None = None
    comparison: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def public(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        payload["actions"] = [item.redacted().model_dump(mode="json") for item in self.actions]
        return payload

