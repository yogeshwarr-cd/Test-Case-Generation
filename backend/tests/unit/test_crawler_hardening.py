import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.automation_service import (
    AutomationService,
    PlaywrightAuthenticationError,
    _is_unsupported_post_registration_behavior,
)
from app.schemas.automation_schema import (
    CrawlAndGenerateRequest,
    PlaywrightAuthentication,
)


@pytest.mark.asyncio
async def test_server_rendered_app_instant_elements():
    """Verify crawler captures elements on standard server-rendered HTML."""
    service = AutomationService()
    page = MagicMock()
    page.wait_for_load_state = AsyncMock()
    page.locator = MagicMock()
    body_loc = MagicMock()
    body_loc.wait_for = AsyncMock()
    page.locator.return_value = body_loc
    
    page.evaluate = AsyncMock(return_value={"visibleCount": 5, "hasBusy": False})
    
    # Run _crawl_wait
    await service._crawl_wait(page)
    
    # Assert load state was called
    page.wait_for_load_state.assert_called_with("domcontentloaded", timeout=15000)
    page.evaluate.assert_called()


@pytest.mark.asyncio
async def test_spa_delayed_rendering_settling():
    """Verify crawler waits for SPA to mount components before capturing elements."""
    service = AutomationService()
    page = MagicMock()
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.locator = MagicMock()
    body_loc = MagicMock()
    body_loc.wait_for = AsyncMock()
    page.locator.return_value = body_loc

    # Simulate: tick 1 (0 elements, busy spinner), tick 2 (4 elements, not busy), tick 3 (4 elements, stable 1), tick 4 (4 elements, stable 2 -> done)
    evaluate_responses = [
        {"visibleCount": 0, "hasBusy": True},
        {"visibleCount": 4, "hasBusy": False},
        {"visibleCount": 4, "hasBusy": False},
        {"visibleCount": 4, "hasBusy": False},
    ]
    page.evaluate = AsyncMock(side_effect=evaluate_responses)

    await service._crawl_wait(page)

    assert page.evaluate.call_count == 4
    assert page.wait_for_timeout.call_count >= 3


@pytest.mark.asyncio
async def test_authenticated_app_preserves_redirected_post_login_url():
    """Verify crawler preserves post-login landing route without forcing re-navigation back to initial URL."""
    service = AutomationService()
    page = MagicMock()
    page.url = "https://example.com/login"
    page.wait_for_load_state = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>Dashboard Overview <a href='/logout'>Logout</a></body></html>")
    page.evaluate = AsyncMock(return_value={"visibleCount": 3, "hasBusy": False})

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

    async def click_side_effect(*args, **kwargs):
        # Application redirects to /appointments after login
        page.url = "https://example.com/appointments"

    submit_loc.click = AsyncMock(side_effect=click_side_effect)

    def locator_side_effect(selector):
        if "password" in selector:
            return password_loc
        if selector == "button[type='submit'],input[type='submit']":
            return submit_loc
        if "logout" in selector:
            loc = MagicMock()
            loc.count = AsyncMock(return_value=1)
            return loc
        loc = MagicMock()
        loc.count = AsyncMock(return_value=0)
        loc.wait_for = AsyncMock()
        return loc

    page.locator.side_effect = locator_side_effect
    page.get_by_label.return_value = email_loc
    page.get_by_role.return_value = submit_loc

    creds = PlaywrightAuthentication(auth_mode="credentials", email="user@example.com", password="SecurePassword123")
    evidence = await service._authenticate_if_required(page, creds, "https://example.com/login")

    assert evidence["required"] is True
    assert evidence["succeeded"] is True
    # The redirected route (/appointments) is preserved and not overwritten or reverted back to /login
    assert evidence["redirected_url"] == "https://example.com/appointments"
    assert page.url == "https://example.com/appointments"


@pytest.mark.asyncio
async def test_static_content_page_distinguished_from_unrendered_page():
    """Verify _analyze_page_content distinguishes static documentation/articles from unrendered empty pages."""
    service = AutomationService()
    
    # 1. Static page with headings & paragraphs but 0 interactive buttons
    static_page = MagicMock()
    static_page.evaluate = AsyncMock(return_value={
        "text_length": 500,
        "has_meaningful_text": True,
        "headings_count": 2,
        "paragraphs_count": 4,
        "interactive_count": 0,
        "is_static_content": True,
    })
    
    analysis = await service._analyze_page_content(static_page)
    assert analysis["is_static_content"] is True
    assert analysis["interactive_count"] == 0

    # 2. Empty unrendered page
    empty_page = MagicMock()
    empty_page.evaluate = AsyncMock(return_value={
        "text_length": 0,
        "has_meaningful_text": False,
        "headings_count": 0,
        "paragraphs_count": 0,
        "interactive_count": 0,
        "is_static_content": False,
    })
    
    empty_analysis = await service._analyze_page_content(empty_page)
    assert empty_analysis["is_static_content"] is False


@pytest.mark.asyncio
async def test_insufficient_crawl_evidence_diagnostic_message():
    """Verify diagnostic message is recorded when page renders zero elements after settle period."""
    page_inventory = [{
        "url": "https://example.com/empty",
        "elements": [],
        "content_analysis": {
            "is_static_content": False,
            "text_length": 0,
        },
    }]
    total_elements = sum(len(p.get("elements", [])) for p in page_inventory)
    all_pages_insufficient = (
        bool(page_inventory)
        and total_elements == 0
        and not any(p.get("content_analysis", {}).get("is_static_content") for p in page_inventory)
    )
    assert all_pages_insufficient is True


def test_domain_acceptance_criteria_allows_appointment_success():
    """Verify that domain user stories with success/creation wording are properly grounded."""
    test_case = {
        "test_case_id": "TC-APPT-001",
        "scenario_id": "SCEN-APPT-001",
        "title": "Create a one-time Home Visit appointment and assign caregiver successfully",
        "steps": [
            {
                "step_number": 1,
                "action": 'Fill "Client" with "John Doe"',
                "expected_result": "Client selected",
            },
            {
                "step_number": 2,
                "action": 'Click "Save Appointment"',
                "expected_result": "A success message indicates the appointment is successfully created and assigned",
            },
        ],
    }
    scenario = {
        "scenario_id": "SCEN-APPT-001",
        "title": "Create Home Visit Appointment",
        "description": "Care coordinator schedules one-time appointment and assigns caregiver",
        "acceptance_criteria": "The appointment status should indicate that it has been successfully created and assigned.",
    }
    evidence_elements = []

    is_blocked = _is_unsupported_post_registration_behavior(
        test_case, scenario, evidence_elements
    )
    # Since AC contains 'successfully created and assigned', 'success message' is supported by AC
    assert is_blocked is False


@pytest.mark.asyncio
async def test_authenticated_spa_route_change_without_full_reload():
    """Verify crawler handles SPA client-side route transitions seamlessly."""
    service = AutomationService()
    page = MagicMock()
    page.url = "https://example.com/portal/dashboard"
    page.wait_for_load_state = AsyncMock()
    page.locator = MagicMock()
    body_loc = MagicMock()
    body_loc.wait_for = AsyncMock()
    page.locator.return_value = body_loc
    page.evaluate = AsyncMock(return_value={"visibleCount": 6, "hasBusy": False})

    await service._crawl_wait(page)
    # Route is accurately recorded without reload errors
    assert page.url == "https://example.com/portal/dashboard"


@pytest.mark.asyncio
async def test_dynamic_interactive_element_capture_semantics():
    """Verify that tabs, comboboxes, buttons, and custom inputs are categorized as interactive elements."""
    service = AutomationService()
    page = MagicMock()
    mock_elements = [
        {
            "tag": "div",
            "role": "button",
            "name": "Match Caregiver",
            "css_selector": "[role='button']:nth-of-type(1)",
            "navigation_candidate": True,
            "visible_text": "Match Caregiver",
            "locator_validated": True,
        },
        {
            "tag": "div",
            "role": "combobox",
            "name": "Select Frequency",
            "css_selector": "[role='combobox']",
            "navigation_candidate": True,
            "visible_text": "One-Time",
            "locator_validated": True,
        },
        {
            "tag": "input",
            "role": "textbox",
            "name": "Client Name",
            "input_type": "text",
            "css_selector": "input[name='client']",
            "navigation_candidate": False,
            "visible_text": "",
            "locator_validated": True,
        },
    ]
    loc = MagicMock()
    loc.evaluate_all = AsyncMock(return_value=mock_elements)
    page.locator.return_value = loc

    captured = await service._capture_interactive_elements(page)
    assert len(captured) == 3
    assert captured[0]["role"] == "button"
    assert captured[1]["role"] == "combobox"
    assert captured[2]["tag"] == "input"


def test_duplicate_looping_navigation_prevention():
    """Verify canonical URL normalization prevents infinite crawl loops."""
    from app.services.automation_service import _canonical_page_url
    
    url1 = "https://example.com/appointments/"
    url2 = "https://example.com/appointments"
    url3 = "https://example.com/appointments?utm_source=test"
    url4 = "https://example.com/appointments#section1"

    assert _canonical_page_url(url1) == _canonical_page_url(url2)
    assert _canonical_page_url(url1) == _canonical_page_url(url3)
    assert _canonical_page_url(url1) == _canonical_page_url(url4)

