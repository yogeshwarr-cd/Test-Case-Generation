import pytest
from pydantic import ValidationError
from app.schemas.automation_schema import PlaywrightAuthentication, CrawlAndGenerateRequest, ScriptExecutionResult

@pytest.mark.asyncio
async def test_auth_schema_generic_identifier():
    auth = PlaywrightAuthentication(
        auth_mode="credentials",
        identifier="emp_12345",
        password="securepassword"
    )
    assert auth.get_identifier == "emp_12345"
    assert auth.password.get_secret_value() == "securepassword"

@pytest.mark.asyncio
async def test_auth_schema_email_fallback():
    auth = PlaywrightAuthentication(
        auth_mode="credentials",
        email="testuser@example.com",
        password="mypassword"
    )
    assert auth.get_identifier == "testuser@example.com"

@pytest.mark.asyncio
async def test_specific_page_scope_request():
    req = CrawlAndGenerateRequest(
        url="https://example.com/login",
        testing_scope="specific_page",
        authentication=PlaywrightAuthentication(auth_mode="no_auth")
    )
    assert req.testing_scope == "specific_page"
    assert req.authentication.auth_mode == "no_auth"

@pytest.mark.asyncio
async def test_missing_credentials_blocked():
    with pytest.raises(ValidationError):
        PlaywrightAuthentication(auth_mode="credentials")

@pytest.mark.asyncio
async def test_script_execution_result_blocked_status():
    result = ScriptExecutionResult(
        script_id="script-001",
        script_name="Test Blocked Script",
        test_case_id="tc-001",
        scenario_id="sc-001",
        status="blocked",
        duration_seconds=0.0,
        error_message="Authentication failed"
    )
    assert result.status == "blocked"


@pytest.mark.asyncio
async def test_no_auth_never_triggers_authentication():
    from unittest.mock import AsyncMock, MagicMock
    from app.services.automation_service import AutomationService

    service = AutomationService()
    mock_page = MagicMock()
    mock_page.url = "https://blazedemo.com/register"
    mock_password = MagicMock()
    mock_password.count = AsyncMock(return_value=1)
    mock_password.is_visible = AsyncMock(return_value=True)
    mock_page.locator.return_value.first = mock_password

    # no_auth credentials mode
    auth_no_auth = PlaywrightAuthentication(auth_mode="no_auth")

    evidence = await service._authenticate_if_required(
        mock_page, auth_no_auth, "https://blazedemo.com/register"
    )

    assert evidence["required"] is False
    assert evidence["attempted"] is False
    assert evidence["succeeded"] is False


@pytest.mark.asyncio
async def test_ac_specific_evidence_prevents_unrelated_register_selection():
    from app.services.automation_service import _select_ac_page_url

    test_case = {
        "test_case_id": "tc-004",
        "scenario_id": "sc-004",
        "title": "Validate flight result details format",
        "description": "User reviews flight entries in results list",
        "acceptance_criteria_ids": ["AC-1"],
        "steps": [
            {"step_number": 1, "action": "Review flight entries in results list", "expected_result": "Details displayed"}
        ]
    }
    scenario = {
        "scenario_id": "sc-004",
        "acceptance_criteria_ids": ["AC-1"],
        "title": "Validate flight result details format"
    }
    base_url = "https://blazedemo.com/"

    # Elements on /register only (unrelated to flight results AC)
    elements = [
        {"role": "textbox", "name": "name", "page_url": "https://blazedemo.com/register"},
        {"role": "textbox", "name": "email", "page_url": "https://blazedemo.com/register"},
        {"role": "textbox", "name": "password", "page_url": "https://blazedemo.com/register"},
    ]

    page_url, page_elements, has_matching_evidence = _select_ac_page_url(
        test_case, scenario, base_url, elements
    )

    # Must NOT select unrelated /register page
    assert page_url != "https://blazedemo.com/register"


@pytest.mark.asyncio
async def test_missing_exact_ac_evidence_results_in_blocked():
    from app.services.automation_service import _select_ac_page_url

    test_case = {
        "test_case_id": "tc-004",
        "scenario_id": "sc-004",
        "title": "Validate flight result details format",
        "description": "User reviews flight entries in results list",
        "acceptance_criteria_ids": ["AC-1"],
        "steps": [
            {"step_number": 1, "action": "Review flight entries in results list", "expected_result": "Details displayed"}
        ]
    }
    scenario = {
        "scenario_id": "sc-004",
        "acceptance_criteria_ids": ["AC-1"],
        "title": "Validate flight result details format"
    }
    base_url = "https://blazedemo.com/"

    # Only register elements exist (no flight result AC elements)
    elements = [
        {"role": "textbox", "name": "name", "page_url": "https://blazedemo.com/register"},
        {"role": "textbox", "name": "password", "page_url": "https://blazedemo.com/register"},
    ]

    page_url, page_elements, has_matching_evidence = _select_ac_page_url(
        test_case, scenario, base_url, elements
    )

    # Missing exact AC evidence must set has_matching_evidence = False
    assert has_matching_evidence is False
    assert page_url is None

