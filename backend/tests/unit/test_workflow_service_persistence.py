import uuid

from app.services.workflow_service import WorkflowService


def test_completed_workflow_is_restored_after_service_reload(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.workflow_service.settings.automation_artifacts_path",
        str(tmp_path),
    )
    workflow_id = uuid.uuid4()
    project_id = uuid.uuid4()
    state = {
        "workflow_id": workflow_id,
        "project_id": project_id,
        "status": "completed",
        "current_stage": "completed",
        "scenarios": [{"scenario_id": "SC-1"}],
        "test_cases": [{"test_case_id": "TC-1", "scenario_id": "SC-1"}],
    }
    original = WorkflowService()
    original._persist_state(state)

    restarted = WorkflowService()
    restored = restarted.get(workflow_id)

    assert restored["status"] == "completed"
    assert restored["workflow_id"] == workflow_id
    assert restored["test_cases"][0]["test_case_id"] == "TC-1"
