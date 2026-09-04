"""
Unit Tests for Modular Page Object Model (POM) Project Structure Generator.
"""

import pytest
from app.services.project_structure_generator import (
    ProjectStructureGenerator,
    sanitize_identifier,
    sanitize_class_name,
    determine_module_name,
    determine_page_name,
)


def test_sanitize_and_naming_helpers():
    assert sanitize_identifier("Sauce Labs Backpack") == "sauce_labs_backpack"
    assert sanitize_identifier("123-invalid-start") == "item_123_invalid_start"
    assert sanitize_identifier("") == "item"
    assert sanitize_class_name("login_page") == "LoginPage"
    assert sanitize_class_name("inventory") == "Inventory"
    assert determine_module_name("https://example.com/checkout/step-one.html") == "checkout"
    assert determine_page_name("https://example.com/inventory.html") == "inventory"
    assert determine_page_name("https://example.com/") == "home"


def test_modular_pom_project_generation():
    generator = ProjectStructureGenerator(app_name="swag_labs")

    discovered_elements = [
        # Login Page Elements
        {
            "tag": "input",
            "name": "user-name",
            "label": "Username",
            "input_type": "text",
            "page_url": "https://www.saucedemo.com/",
            "element_id": "user-name",
            "test_id": "username",
        },
        {
            "tag": "input",
            "name": "password",
            "label": "Password",
            "input_type": "password",
            "page_url": "https://www.saucedemo.com/",
            "element_id": "password",
            "test_id": "password",
        },
        {
            "tag": "button",
            "name": "Login",
            "role": "button",
            "page_url": "https://www.saucedemo.com/",
            "element_id": "login-button",
            "test_id": "login-button",
        },
        # Inventory Page Elements
        {
            "tag": "button",
            "name": "Add to cart",
            "role": "button",
            "page_url": "https://www.saucedemo.com/inventory.html",
            "element_id": "add-to-cart-sauce-labs-backpack",
            "test_id": "add-to-cart-sauce-labs-backpack",
        },
        {
            "tag": "a",
            "name": "Shopping Cart",
            "page_url": "https://www.saucedemo.com/inventory.html",
            "element_id": "shopping_cart_container",
        },
    ]

    page_inventory = [
        {"url": "https://www.saucedemo.com/", "title": "Swag Labs Login"},
        {"url": "https://www.saucedemo.com/inventory.html", "title": "Swag Labs Inventory"},
    ]

    test_cases = [
        {
            "test_case_id": "TC_001",
            "scenario_id": "SC_001",
            "title": "Successful login and add product to cart",
            "steps": [
                {"step_number": 1, "action": "Enter username and password on login page", "expected_result": "Credentials filled"},
                {"step_number": 2, "action": "Click login button", "expected_result": "Navigated to inventory"},
                {"step_number": 3, "action": "Click Add to cart for Sauce Labs Backpack", "expected_result": "Item added to cart"},
            ],
        },
    ]

    scenarios = [
        {"scenario_id": "SC_001", "title": "End to end purchase flow"},
    ]

    project = generator.generate_project(
        base_url="https://www.saucedemo.com/",
        discovered_elements=discovered_elements,
        page_inventory=page_inventory,
        test_cases=test_cases,
        scenarios=scenarios,
        credentials={"identifier": "standard_user", "password": "secret_sauce"},
    )

    assert project.project_name == "swag_labs"
    assert len(project.files) > 0

    file_paths = [f.relative_path for f in project.files]

    # Shared framework files
    assert "shared/config/settings.py" in file_paths
    assert "shared/fixtures/conftest.py" in file_paths
    assert "shared/utils/helpers.py" in file_paths
    assert "shared/test_data/data_loader.py" in file_paths
    assert "shared/test_data/test_data.json" in file_paths
    assert "shared/assets/.gitkeep" in file_paths
    assert "screenshots/.gitkeep" in file_paths
    assert "traces/.gitkeep" in file_paths
    assert "reports/.gitkeep" in file_paths
    assert "requirements.txt" in file_paths
    assert ".env.example" in file_paths
    assert "pytest.ini" in file_paths
    assert "pyproject.toml" in file_paths
    assert "README.md" in file_paths

    # Page Objects
    assert any("pages" in p and "page.py" in p for p in file_paths)

    # Test Suites
    assert any("tests" in p and "test_" in p for p in file_paths)

    # Verify conftest contains Playwright fixtures
    conftest_file = next(f for f in project.files if f.relative_path == "shared/fixtures/conftest.py")
    assert "sync_playwright" in conftest_file.content
    assert "def browser" in conftest_file.content
    assert "def page" in conftest_file.content

    # Verify Page Object has resilient locators and methods
    page_obj_file = next(f for f in project.files if "page.py" in f.relative_path and "modules" in f.relative_path)
    assert "class " in page_obj_file.content
    assert "def navigate" in page_obj_file.content
    assert "def assert_loaded" in page_obj_file.content


def test_cross_page_pom_test_generation():
    generator = ProjectStructureGenerator(app_name="e_commerce")

    discovered_elements = [
        {"tag": "input", "name": "user-name", "element_id": "user-name", "page_url": "https://example.com/login"},
        {"tag": "button", "name": "Login", "element_id": "login-btn", "page_url": "https://example.com/login"},
        {"tag": "button", "name": "Add to cart", "element_id": "add-btn", "page_url": "https://example.com/catalog"},
    ]

    test_cases = [
        {
            "test_case_id": "TC_E2E_01",
            "scenario_id": "SC_E2E_01",
            "title": "Login and add to cart flow",
            "steps": [
                {"step_number": 1, "action": "Enter username credentials", "expected_result": "Username entered"},
                {"step_number": 2, "action": "Add to cart product", "expected_result": "Product added"},
            ],
        }
    ]

    project = generator.generate_project(
        base_url="https://example.com/login",
        discovered_elements=discovered_elements,
        page_inventory=[
            {"url": "https://example.com/login", "title": "Login Page"},
            {"url": "https://example.com/catalog", "title": "Catalog Page"},
        ],
        test_cases=test_cases,
    )

    test_file = next(f for f in project.files if "test_tc_e2e_01.py" in f.relative_path)
    assert "@pytest.mark.regression" in test_file.content
    assert "def test_login_and_add_to_cart_flow" in test_file.content
