"""Pytest global fixtures for Playwright browser and page management."""
import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from shared.config.settings import settings

@pytest.fixture(scope="session")
def browser():
    """Session-scoped Playwright browser instance."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=settings.HEADLESS,
            slow_mo=settings.SLOW_MO
        )
        yield browser
        browser.close()

@pytest.fixture(scope="function")
def context(browser: Browser) -> BrowserContext:
    """Function-scoped browser context."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True
    )
    yield context
    context.close()

@pytest.fixture(scope="function")
def page(context: BrowserContext) -> Page:
    """Function-scoped page fixture with failure screenshot capture."""
    page = context.new_page()
    page.set_default_timeout(settings.DEFAULT_TIMEOUT)
    yield page
    page.close()

@pytest.fixture(scope="session")
def default_credentials():
    """Default test credentials from environment or test config."""
    import os
    return {
        "username": os.getenv("TEST_USERNAME", "standard_user"),
        "password": os.getenv("TEST_PASSWORD", "secret_sauce"),
    }
