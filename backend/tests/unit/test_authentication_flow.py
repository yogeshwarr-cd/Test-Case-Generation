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
