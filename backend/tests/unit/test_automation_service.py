import uuid

import pytest

from app.schemas.automation_schema import (
    DiscoveredElement,
    ExecuteScriptsRequest,
    GenerateScriptsRequest,
)
from app.services.automation_service import AutomationService, _python_source


def test_generated_source_is_playwright_page_object_and_contains_traceable_id():
    source = _python_source(
        {
            "test_case_id": "TC-1",
            "title": "User login",
            "steps": [
                {"step_number": 1, "action": "Click the Login button", "expected_result": "Login form"}
            ],
        },
        "https://example.com/",
    )
    assert "class PageObjectUserLogin" in source
    assert "get_by_role" in source
    assert "get_by_label" in source
    assert "assert_expected" in source
    assert "TC-1" in source


@pytest.mark.asyncio
async def test_generation_reads_completed_workflow_without_mutating_it(monkeypatch, tmp_path):
    workflow_id = uuid.uuid4()
    state = {
        "workflow_id": workflow_id,
        "status": "completed",
        "scenarios": [{"scenario_id": "SC-1", "user_story_ids": ["US-1"]}],
        "test_cases": [{
            "test_case_id": "TC-1",
            "scenario_id": "SC-1",
            "title": "Login",
            "steps": [{"step_number": 1, "action": "Open login", "expected_result": "Page opens"}],
            "requirement_ids": ["REQ-1"],
        }],
    }
    original = repr(state)
    service = AutomationService()
    monkeypatch.setattr("app.services.automation_service.workflow_service.get", lambda _: state)
    monkeypatch.setattr("app.services.automation_service.settings.automation_artifacts_path", str(tmp_path))

    async def validate_url(_: str):
        return None

    async def discover(_: str):
        return "Example", [DiscoveredElement(tag="button", role="button", name="Login")]

    monkeypatch.setattr(service, "_validate_url", validate_url)
    monkeypatch.setattr(service, "_discover", discover)
    response = await service.generate(
        GenerateScriptsRequest(workflow_id=workflow_id, application_url="https://example.com")
    )
    assert response.reachable is True
    assert response.scripts[0].requirement_ids == ["REQ-1"]
    assert response.scripts[0].user_story_ids == ["US-1"]
    assert repr(state) == original


@pytest.mark.asyncio
async def test_manual_mode_skips_execution_and_produces_report(monkeypatch, tmp_path):
    workflow_id = uuid.uuid4()
    service = AutomationService()
    monkeypatch.setattr("app.services.automation_service.workflow_service.get", lambda _: {
        "workflow_id": workflow_id,
        "status": "completed",
        "scenarios": [{"scenario_id": "SC-1"}],
        "test_cases": [{
            "test_case_id": "TC-1", "scenario_id": "SC-1", "title": "Login",
            "steps": [{"step_number": 1, "action": "Open", "expected_result": "Open"}],
        }],
    })
    monkeypatch.setattr("app.services.automation_service.settings.automation_artifacts_path", str(tmp_path))
    monkeypatch.setattr(service, "_validate_url", lambda _: pytest.fail("replaced below"))

    async def validate_url(_: str):
        return None

    async def discover(_: str):
        return "Example", []

    monkeypatch.setattr(service, "_validate_url", validate_url)
    monkeypatch.setattr(service, "_discover", discover)
    generated = await service.generate(
        GenerateScriptsRequest(workflow_id=workflow_id, application_url="https://example.com")
    )
    report = await service.execute(
        ExecuteScriptsRequest(generation_id=generated.generation_id, mode="manual")
    )
    assert report.total_scripts == 1
    assert report.skipped_scripts == 1
    assert report.results[0].traceability["test_case_id"] == "TC-1"
