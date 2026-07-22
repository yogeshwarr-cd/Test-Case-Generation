import uuid

import httpx
import pytest

from app.main import app
from app.services.automation_service import automation_service


@pytest.mark.asyncio
async def test_automation_routes_are_registered_and_execute_end_to_end(monkeypatch, tmp_path):
    workflow_id = uuid.uuid4()
    state = {
        "workflow_id": workflow_id,
        "status": "completed",
        "scenarios": [{"scenario_id": "SC-1", "user_story_ids": ["US-1"]}],
        "test_cases": [{
            "test_case_id": "TC-1",
            "scenario_id": "SC-1",
            "title": "Open application",
            "steps": [{"step_number": 1, "action": "Open application", "expected_result": "Page opens"}],
            "requirement_ids": ["REQ-1"],
        }],
    }
    monkeypatch.setattr("app.services.automation_service.workflow_service.get", lambda _: state)
    monkeypatch.setattr("app.services.automation_service.settings.automation_artifacts_path", str(tmp_path))
    monkeypatch.setattr("app.services.automation_service.settings.app_mock_mode", True)
    automation_service._generations.clear()
    automation_service._reports.clear()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        generated_response = await client.post(
            "/api/v1/automation/scripts/generate",
            json={"workflow_id": str(workflow_id), "application_url": "https://example.com"},
        )
        assert generated_response.status_code == 200
        generation_id = generated_response.json()["generation_id"]

        # Simulate process-local state disappearing before Playwright execution.
        automation_service._generations.clear()
        executed_response = await client.post(
            "/api/v1/automation/executions",
            json={"generation_id": generation_id, "mode": "automated"},
        )
        assert executed_response.status_code == 200
        report = executed_response.json()
        assert report["total_scripts"] == 1
        assert report["passed_scripts"] == 1

        fetched_response = await client.get(
            f"/api/v1/automation/executions/{report['execution_id']}"
        )
        assert fetched_response.status_code == 200
