"""Reusable UI automation helper utilities."""
from typing import Optional
from playwright.sync_api import Page, Locator, expect

def wait_and_click(locator: Locator, timeout: int = 10000) -> None:
    """Wait for element to be visible and click."""
    locator.wait_for(state="visible", timeout=timeout)
    locator.click()

def safe_fill(locator: Locator, value: str, timeout: int = 10000) -> None:
    """Wait for input to be visible, clear, and fill value."""
    locator.wait_for(state="visible", timeout=timeout)
    locator.fill(value)

def assert_element_text(locator: Locator, expected_text: str, timeout: int = 10000) -> None:
    """Assert locator contains expected text."""
    expect(locator).to_contain_text(expected_text, timeout=timeout)
