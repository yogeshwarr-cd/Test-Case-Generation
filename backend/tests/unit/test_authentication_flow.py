import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.automation_service import AutomationService, PlaywrightAuthenticationError
from app.schemas.automation_schema import PlaywrightAuthentication


@pytest.mark.asyncio
async def test_no_auth_never_triggers_authentication_verification():
    service = AutomationService()
    page = MagicMock()
    page.url = "https://the-internet.herokuapp.com/login"
    
    # auth_mode = "no_auth"
    creds = PlaywrightAuthentication(auth_mode="no_auth")
    evidence = await service._authenticate_if_required(page, creds, "https://the-internet.herokuapp.com/login")
    
    assert evidence["required"] is False
    assert evidence["attempted"] is False
    assert evidence["succeeded"] is False
    page.locator.assert_not_called()


@pytest.mark.asyncio
async def test_valid_credentials_reaches_authenticated_state():
    service = AutomationService()
    page = MagicMock()
    page.url = "https://the-internet.herokuapp.com/login"
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>You logged into a secure area! <a href='/logout'>Logout</a></body></html>")

    # Mock locators
    password_loc = MagicMock()
    password_loc.count = AsyncMock(return_value=1)
    password_loc.is_visible = AsyncMock(return_value=True)
    password_loc.fill = AsyncMock()
    password_loc.first = password_loc

    email_loc = MagicMock()
    email_loc.count = AsyncMock(return_value=1)
    email_loc.is_visible = AsyncMock(return_value=True)
    email_loc.fill = AsyncMock()
    email_loc.first = email_loc

    submit_loc = MagicMock()
    submit_loc.count = AsyncMock(return_value=1)
    submit_loc.is_visible = AsyncMock(return_value=True)
    submit_loc.first = submit_loc

    body_loc = MagicMock()
    body_loc.wait_for = AsyncMock()

    async def click_side_effect(*args, **kwargs):
        page.url = "https://the-internet.herokuapp.com/secure"

    submit_loc.click = AsyncMock(side_effect=click_side_effect)

    def locator_side_effect(selector):
        if selector == "body":
            return body_loc
        if "password" in selector:
            return password_loc
        if selector == "button[type='submit'],input[type='submit']":
            return submit_loc
        if selector in ["[role='alert'],#flash,.flash.error,.validation-summary-errors,.field-validation-error", "#flash.success,.flash.success,.alert-success,.success"]:
            loc = MagicMock()
            loc.count = AsyncMock(return_value=1 if "success" in selector else 0)
            loc.all_inner_texts = AsyncMock(return_value=["You logged into a secure area!"])
            return loc
        if "logout" in selector:
            loc = MagicMock()
            loc.count = AsyncMock(return_value=1)
            return loc
        loc = MagicMock()
        loc.count = AsyncMock(return_value=0)
        return loc

    page.locator.side_effect = locator_side_effect
    page.get_by_label.return_value = email_loc
    page.get_by_role.return_value = submit_loc

    creds = PlaywrightAuthentication(auth_mode="credentials", email="tomsmith", password="SuperSecretPassword!")
    evidence = await service._authenticate_if_required(page, creds, "https://the-internet.herokuapp.com/login")

    assert evidence["required"] is True
    assert evidence["attempted"] is True
    assert evidence["succeeded"] is True
    assert evidence["redirected_url"] == "https://the-internet.herokuapp.com/secure"


@pytest.mark.asyncio
async def test_invalid_credentials_detected_as_authentication_failure():
    service = AutomationService()
    page = MagicMock()
    page.url = "https://the-internet.herokuapp.com/login"
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>Your username is invalid!</body></html>")

    password_loc = MagicMock()
    password_loc.count = AsyncMock(return_value=1)
    password_loc.is_visible = AsyncMock(return_value=True)
    password_loc.fill = AsyncMock()
    password_loc.first = password_loc

    email_loc = MagicMock()
    email_loc.count = AsyncMock(return_value=1)
    email_loc.is_visible = AsyncMock(return_value=True)
    email_loc.fill = AsyncMock()
    email_loc.first = email_loc

    submit_loc = MagicMock()
    submit_loc.count = AsyncMock(return_value=1)
    submit_loc.is_visible = AsyncMock(return_value=True)
    submit_loc.click = AsyncMock()
    submit_loc.first = submit_loc

    body_loc = MagicMock()
    body_loc.wait_for = AsyncMock()

    def locator_side_effect(selector):
        if selector == "body":
            return body_loc
        if "password" in selector:
            return password_loc
        if selector == "button[type='submit'],input[type='submit']":
            return submit_loc
        if selector in ["[role='alert'],#flash,.flash.error,.validation-summary-errors,.field-validation-error"]:
            loc = MagicMock()
            loc.count = AsyncMock(return_value=1)
            loc.all_inner_texts = AsyncMock(return_value=["Your username is invalid!"])
            return loc
        loc = MagicMock()
        loc.count = AsyncMock(return_value=0)
        return loc

    page.locator.side_effect = locator_side_effect
    page.get_by_label.return_value = email_loc
    page.get_by_role.return_value = submit_loc

    creds = PlaywrightAuthentication(auth_mode="credentials", email="tomsmith", password="WrongPassword")

    with pytest.raises(PlaywrightAuthenticationError) as exc_info:
        await service._authenticate_if_required(page, creds, "https://the-internet.herokuapp.com/login")

    assert "Authentication Failed" in str(exc_info.value)
    assert "Your username is invalid!" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dynamic_auth_state_selection_during_execution(monkeypatch, tmp_path):
    from app.schemas.automation_schema import (
        ScriptGenerationResponse,
        GeneratedScript,
        ExecuteScriptsRequest,
        PlaywrightAuthentication
    )
    
    import uuid

    # Initialize service
    service = AutomationService()
    monkeypatch.setattr("app.services.automation_service.settings.app_mock_mode", False)
    monkeypatch.setattr("app.services.automation_service.settings.automation_navigation_timeout_seconds", 30)
    monkeypatch.setattr("app.services.automation_service.settings.automation_navigation_settle_timeout_seconds", 3)
    workflow_uuid = uuid.uuid4()
    
    # Mock generation data
    response = ScriptGenerationResponse(
        generation_id="gen-test",
        application_url="https://example.com",
        reachable=True,
        discovered_elements=[],
        crawl_report={"auth_state": {"cookies": [{"name": "session", "value": "123"}]}},
        scripts=[
            GeneratedScript(
                script_id="pw-login",
                workflow_id=workflow_uuid,
                test_case_id="tc-login",
                scenario_id="sc-1",
                name="Successful Login",
                application_url="https://example.com",
                source="print('login')",
                download_path=str(tmp_path / "pw-login.pwscript"),
                lifecycle_status="Valid",
                page_url="https://example.com/auth",
                page_elements=[],
                requirement_ids=[],
                user_story_ids=[],
            ),
            GeneratedScript(
                script_id="pw-protected",
                workflow_id=workflow_uuid,
                test_case_id="tc-protected",
                scenario_id="sc-1",
                name="View Dashboard",
                application_url="https://example.com",
                source="print('dashboard')",
                download_path=str(tmp_path / "pw-protected.pwscript"),
                lifecycle_status="Valid",
                page_url="https://example.com/dashboard",
                page_elements=[],
                requirement_ids=[],
                user_story_ids=[],
            ),
            GeneratedScript(
                script_id="pw-logout",
                workflow_id=workflow_uuid,
                test_case_id="tc-logout",
                scenario_id="sc-1",
                name="Logout",
                application_url="https://example.com",
                source="print('logout')",
                download_path=str(tmp_path / "pw-logout.pwscript"),
                lifecycle_status="Valid",
                page_url="https://example.com/dashboard",
                page_elements=[],
                requirement_ids=[],
                user_story_ids=[],
            )
        ]
    )
    
    generation = {
        "workflow": {
            "test_cases": [
                {
                    "test_case_id": "tc-login",
                    "title": "Successful Login with Valid Credentials",
                    "steps": [{"action": "Fill Password with 'x'"}],
                },
                {
                    "test_case_id": "tc-protected",
                    "title": "View Dashboard",
                    "steps": [{"action": "Verify dashboard text"}],
                },
                {
                    "test_case_id": "tc-logout",
                    "title": "Logout from authenticated session",
                    "steps": [{"action": "Click Logout"}],
                }
            ]
        },
        "response": response,
        "directory": tmp_path
    }
    
    # Mock AutomationService methods
    monkeypatch.setattr(service, "generation", AsyncMock(return_value=generation))
    monkeypatch.setattr(service, "_validate_navigation", AsyncMock())
    monkeypatch.setattr(service, "_expected_page_evidence_present", AsyncMock(return_value=True))
    monkeypatch.setattr(service, "_dismiss_overlays", AsyncMock())
    monkeypatch.setattr(service, "_save_report", MagicMock())
    
    # Mock Playwright execution context
    mock_playwright_instance = MagicMock()
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    
    mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_context.new_page = AsyncMock(return_value=mock_page)
    
    mock_nav_response = MagicMock()
    mock_nav_response.status = 200
    mock_page.goto = AsyncMock(return_value=mock_nav_response)
    mock_page.url = "https://example.com"
    
    class FakeAsyncPlaywright:
        async def __aenter__(self):
            return mock_playwright_instance
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    import playwright.async_api
    monkeypatch.setattr(playwright.async_api, "async_playwright", FakeAsyncPlaywright)
    
    # Run execute request (automated mode)
    request = ExecuteScriptsRequest(
        generation_id="gen-test",
        mode="automated",
        authentication=PlaywrightAuthentication(auth_mode="credentials", email="user@example.com", password="password123")
    )
    
    await service.execute(request, _dedicated_loop=True, _parallel_child=True)
    
    # Inspect arguments passed to browser.new_context for each script run
    calls = mock_browser.new_context.call_args_list
    assert len(calls) == 3
    
    # 1. Login test must start unauthenticated (storage_state=None)
    assert calls[0].kwargs.get("storage_state") is None
    
    # 2. Protected-page test must start authenticated
    assert calls[1].kwargs.get("storage_state") == {"cookies": [{"name": "session", "value": "123"}]}
    
    # 3. Logout test must start authenticated
    assert calls[2].kwargs.get("storage_state") == {"cookies": [{"name": "session", "value": "123"}]}

