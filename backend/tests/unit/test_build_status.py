import uuid
from pathlib import Path
import pytest
from app.services.automation_service import AutomationService
from app.schemas.automation_schema import ExecuteScriptsRequest, ScriptExecutionResult


def test_build_status_and_critical_suite(monkeypatch, tmp_path):
    workflow_id = uuid.uuid4()
    generation_id = "gen-test-build-status"
    service = AutomationService()

    # Define mock workflow state returned by workflow_service
    mock_workflow = {
        "workflow_id": workflow_id,
        "test_cases": [
            {
                "test_case_id": "tc-critical-pass",
                "title": "Critical Passing TC",
                "functional_area": "Authentication",
                "priority": "critical",
                "in_critical_suite": True,
            },
            {
                "test_case_id": "tc-critical-fail",
                "title": "Critical Failing TC",
                "functional_area": "Payments",
                "priority": "high",
                "in_critical_suite": True,
            },
            {
                "test_case_id": "tc-critical-blocked",
                "title": "Critical Blocked TC",
                "functional_area": "Dashboard",
                "priority": "medium",
                "in_critical_suite": True,
            },
            {
                "test_case_id": "tc-noncritical-fail",
                "title": "Non-critical Failing TC",
                "functional_area": "Reports",
                "priority": "low",
                "in_critical_suite": False,
            },
        ],
    }

    # Case 1: All critical tests pass
    results_all_pass = [
        ScriptExecutionResult(
            script_id="s1",
            script_name="s1",
            test_case_id="tc-critical-pass",
            scenario_id="sc-1",
            status="passed",
            duration_seconds=1.2,
        ),
        ScriptExecutionResult(
            script_id="s2",
            script_name="s2",
            test_case_id="tc-noncritical-fail",
            scenario_id="sc-2",
            status="failed",
            duration_seconds=0.8,
        ),
    ]

    report_all_pass = service._save_report(
        request=ExecuteScriptsRequest(generation_id=generation_id, mode="automated"),
        results=results_all_pass,
        duration=2.0,
        directory=tmp_path,
        generation={"workflow": mock_workflow},
    )

    assert report_all_pass.critical_total == 1
    assert report_all_pass.critical_passed == 1
    assert report_all_pass.critical_failed == 0
    assert report_all_pass.critical_blocked == 0
    assert report_all_pass.build_status == "BUILD PASSED"
    # Non-critical failure must not fail the build status, but must still be clearly reported
    assert report_all_pass.failed == 1

    # Case 2: Any critical test fails
    results_critical_fail = [
        ScriptExecutionResult(
            script_id="s1",
            script_name="s1",
            test_case_id="tc-critical-pass",
            scenario_id="sc-1",
            status="passed",
            duration_seconds=1.2,
        ),
        ScriptExecutionResult(
            script_id="s2",
            script_name="s2",
            test_case_id="tc-critical-fail",
            scenario_id="sc-2",
            status="failed",
            duration_seconds=1.5,
        ),
    ]

    report_critical_fail = service._save_report(
        request=ExecuteScriptsRequest(generation_id=generation_id, mode="automated"),
        results=results_critical_fail,
        duration=2.7,
        directory=tmp_path,
        generation={"workflow": mock_workflow},
    )

    assert report_critical_fail.critical_total == 2
    assert report_critical_fail.critical_passed == 1
    assert report_critical_fail.critical_failed == 1
    assert report_critical_fail.build_status == "BUILD FAILED"

    # Case 3: No critical test failed, but any is blocked
    results_critical_blocked = [
        ScriptExecutionResult(
            script_id="s1",
            script_name="s1",
            test_case_id="tc-critical-pass",
            scenario_id="sc-1",
            status="passed",
            duration_seconds=1.2,
        ),
        ScriptExecutionResult(
            script_id="s2",
            script_name="s2",
            test_case_id="tc-critical-blocked",
            scenario_id="sc-2",
            status="blocked",
            duration_seconds=0.5,
        ),
    ]

    report_critical_blocked = service._save_report(
        request=ExecuteScriptsRequest(generation_id=generation_id, mode="automated"),
        results=results_critical_blocked,
        duration=1.7,
        directory=tmp_path,
        generation={"workflow": mock_workflow},
    )

    assert report_critical_blocked.critical_total == 2
    assert report_critical_blocked.critical_passed == 1
    assert report_critical_blocked.critical_failed == 0
    assert report_critical_blocked.critical_blocked == 1
    assert report_critical_blocked.build_status == "BUILD BLOCKED / NEEDS REVIEW"


def test_build_status_defaults():
    # Verify backward compatibility / default mapping if fields are missing in workflow JSON
    service = AutomationService()
    mock_workflow_legacy = {
        "workflow_id": uuid.uuid4(),
        "test_cases": [
            {
                "test_case_id": "tc-legacy",
                "title": "Legacy TC",
                # functional_area, priority, and in_critical_suite are completely missing
            }
        ],
    }

    results = [
        ScriptExecutionResult(
            script_id="s1",
            script_name="s1",
            test_case_id="tc-legacy",
            scenario_id="sc-1",
            status="passed",
            duration_seconds=1.0,
        )
    ]

    report = service._save_report(
        request=ExecuteScriptsRequest(generation_id="legacy-gen", mode="automated"),
        results=results,
        duration=1.0,
        directory=Path("."),
        generation={"workflow": mock_workflow_legacy},
    )

    # Defaults: in_critical_suite = False, functional_area = Unclassified, priority = medium
    assert report.results[0].functional_area == "Unclassified"
    assert report.results[0].priority == "medium"
    assert report.results[0].in_critical_suite is False
    assert report.critical_total == 0
    assert report.build_status == "BUILD PASSED"
