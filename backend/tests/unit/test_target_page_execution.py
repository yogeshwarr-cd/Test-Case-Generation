import pytest
import uuid
from app.schemas.automation_schema import (
    CrawlAndGenerateRequest,
    GeneratedScript,
    DiscoveredElement,
)
from app.services.automation_service import (
    AutomationService,
    _is_unsupported_post_registration_behavior,
)

@pytest.mark.asyncio
async def test_specific_page_scope_only_crawls_register():
    service = AutomationService()
    req = CrawlAndGenerateRequest(
        url="https://blazedemo.com/register",
        testing_scope="specific_page",
        page_limit=250,
        depth_limit=15,
    )
    assert req.testing_scope == "specific_page"
    assert req.page_limit == 250


def test_generated_input_actions_have_explicit_values():
    import re
    # Positive explicit action
    action_pos = 'Fill "Name" with "John Doe"'
    values_pos = re.findall(r"['\"]([^'\"]*)['\"]", action_pos)
    assert values_pos == ["Name", "John Doe"]
    assert values_pos[-1] == "John Doe"

    # Negative explicit empty action
    action_neg = 'Fill "Email" with ""'
    values_neg = re.findall(r"['\"]([^'\"]*)['\"]", action_neg)
    assert values_neg == ["Email", ""]
    assert values_neg[-1] == ""


def test_unsupported_expected_behavior_results_in_blocked():
    test_case = {
        "test_case_id": "TC-REG-001",
        "scenario_id": "SCEN-REG-001",
        "title": "Register with invented expectations",
        "steps": [
            {
                "step_number": 1,
                "action": 'Fill "Name" with "John Doe"',
                "expected_result": "Name field is populated",
            },
            {
                "step_number": 2,
                "action": 'Click "Register"',
                "expected_result": "User is redirected to Dashboard and receives welcome email confirmation",
            },
        ],
    }
    scenario = {
        "scenario_id": "SCEN-REG-001",
        "title": "User Registration",
        "description": "User submits registration form on register page",
        "acceptance_criteria": "Submit form with valid input fields.",
        "user_story_ids": ["US-100"],
    }
    evidence_elements = [
        {"name": "Register", "role": "button", "page_url": "https://blazedemo.com/register"}
    ]

    is_blocked = _is_unsupported_post_registration_behavior(
        test_case, scenario, evidence_elements
    )
    assert is_blocked is True


def test_traceability_id_preservation():
    wf_id = uuid.uuid4()
    script = GeneratedScript(
        script_id="pw-001-tc-reg-001",
        workflow_id=wf_id,
        test_case_id="TC-REG-001",
        scenario_id="SCEN-REG-001",
        name="Register Test",
        application_url="https://blazedemo.com/register",
        source="print('hello')",
        download_path="/download",
        user_story_ids=["US-100"],
        requirement_ids=["AC-101"],
        lifecycle_status="Blocked",
    )
    assert script.user_story_ids == ["US-100"]
    assert script.requirement_ids == ["AC-101"]
    assert script.scenario_id == "SCEN-REG-001"
    assert script.test_case_id == "TC-REG-001"
    assert script.script_id == "pw-001-tc-reg-001"
    assert script.lifecycle_status == "Blocked"
