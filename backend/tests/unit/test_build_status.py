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


def test_critical_priority_rules(monkeypatch, tmp_path):
    from app.schemas.testcase_schema import TestCase as SchemaTestCase
    from app.schemas.common import EntityEdit
    from app.models.testcase import TestCaseVersion
    from app.services.workflow_service import WorkflowService

    # 1. Pydantic Schema enforcement: priority = critical automatically sets in_critical_suite = True
    tc_data = {
        "title": "Test case critical priority schema test",
        "description": "Ensure critical priority automatically sets critical suite",
        "priority": "critical",
        "in_critical_suite": False,
        "steps": [{"step_number": 1, "action": "Verify schema", "expected_result": "Sets critical suite to true"}]
    }
    tc_schema = SchemaTestCase.model_validate(tc_data)
    assert tc_schema.in_critical_suite is True

    # High/Medium/Low do not automatically add it to the Critical Suite
    tc_data_high = tc_data.copy()
    tc_data_high["priority"] = "high"
    tc_schema_high = SchemaTestCase.model_validate(tc_data_high)
    assert tc_schema_high.in_critical_suite is False

    # 2. EntityEdit Schema enforcement
    ee_data = {
        "title": "Edit test",
        "priority": "critical",
        "in_critical_suite": False,
    }
    ee_schema = EntityEdit.model_validate(ee_data)
    assert ee_schema.in_critical_suite is True

    ee_data_medium = {
        "title": "Edit test medium",
        "priority": "medium",
        "in_critical_suite": False,
    }
    ee_schema_medium = EntityEdit.model_validate(ee_data_medium)
    assert ee_schema_medium.in_critical_suite is False

    # 3. Model enforcement: priority = critical automatically sets in_critical_suite = True
    model_version = TestCaseVersion(
        test_case_id=uuid.uuid4(),
        version_number=1,
        title="Critical test model validation",
        description="Verify model validation",
        test_case_type="functional",
        priority="critical",
        in_critical_suite=False,
    )
    assert model_version.in_critical_suite is True

    # 4. Model Update Enforcement: Changing priority to critical updates in_critical_suite
    model_version_2 = TestCaseVersion(
        test_case_id=uuid.uuid4(),
        version_number=1,
        title="Critical test model validation 2",
        description="Verify model validation",
        test_case_type="functional",
        priority="medium",
        in_critical_suite=False,
    )
    assert model_version_2.in_critical_suite is False
    model_version_2.priority = "critical"
    assert model_version_2.in_critical_suite is True

    # Setting in_critical_suite to False on a critical test is overridden to True
    model_version_2.in_critical_suite = False
    assert model_version_2.in_critical_suite is True

    # 5. Workflow State Update Enforcement
    workflow_id = uuid.uuid4()
    w_service = WorkflowService()
    mock_workflow = {
        "workflow_id": workflow_id,
        "test_cases": [
            {
                "test_case_id": "tc-workflow-1",
                "title": "Workflow TC 1",
                "priority": "medium",
                "in_critical_suite": False,
            }
        ]
    }
    w_service._states[workflow_id] = mock_workflow
    
    # Update priority to critical via workflow service
    import asyncio
    updated_tc = asyncio.run(w_service.update_testcase(workflow_id, "tc-workflow-1", {"priority": "critical"}))
    assert updated_tc["in_critical_suite"] is True

    # Attempt to set in_critical_suite to False on a critical test case in workflow
    updated_tc = asyncio.run(w_service.update_testcase(workflow_id, "tc-workflow-1", {"in_critical_suite": False}))
    assert updated_tc["in_critical_suite"] is True

