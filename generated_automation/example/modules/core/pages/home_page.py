"""Page Object Model for HomePage."""
from playwright.sync_api import Page, expect
from shared.config.settings import settings

class HomePage:
    """Page Object for https://example.com/."""

    PAGE_URL: str = "https://example.com/"

    def __init__(self, page: Page) -> None:
        self.page = page
        pass

    def navigate(self) -> "HomePage":
        """Navigate to https://example.com/."""
        self.page.goto(self.PAGE_URL)
        return self

    def assert_loaded(self) -> "HomePage":
        """Assert the page is loaded and body is visible."""
        expect(self.page.locator("body")).to_be_visible()
        return self

