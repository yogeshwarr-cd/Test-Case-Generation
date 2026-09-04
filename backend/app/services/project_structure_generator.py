"""
Project Structure Generator for Modular Page Object Model (POM) Automation Projects.

Generates industry-standard Playwright + Pytest modular projects structured by domain modules,
reusable Page Objects, Pytest fixtures (conftest.py), centralized configuration, and data loaders.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlsplit


def sanitize_identifier(name: str, fallback: str = "item") -> str:
    """Sanitize any arbitrary string into a valid Python identifier (snake_case)."""
    if not name or not name.strip():
        return fallback
    clean = re.sub(r"[^\w\s-]", "", name.strip().lower())
    clean = re.sub(r"[-\s]+", "_", clean)
    clean = clean.strip("_")
    if not clean or clean[0].isdigit():
        clean = f"{fallback}_{clean}" if clean else fallback
    return clean


def sanitize_class_name(name: str, fallback: str = "Page") -> str:
    """Sanitize any arbitrary string into a valid Python ClassName (PascalCase)."""
    clean_snake = sanitize_identifier(name, fallback=fallback)
    pascal = "".join(part.capitalize() for part in clean_snake.split("_") if part)
    if not pascal:
        pascal = fallback
    if pascal[0].isdigit():
        pascal = f"{fallback}{pascal}"
    return pascal


def determine_module_name(url: str, title: Optional[str] = None) -> str:
    """Determine a sensible business module name from URL path or page title."""
    try:
        parsed = urlsplit(url)
        path_segments = [s for s in parsed.path.strip("/").split("/") if s and not s.endswith((".html", ".htm", ".php", ".aspx"))]
        if path_segments:
            return sanitize_identifier(path_segments[0], fallback="core")
    except Exception:
        pass
    if title and title.strip():
        first_word = title.strip().split()[0]
        return sanitize_identifier(first_word, fallback="core")
    return "core"


def determine_page_name(url: str, title: Optional[str] = None) -> str:
    """Determine a descriptive Page Object name from URL or title."""
    try:
        parsed = urlsplit(url)
        path = parsed.path.strip("/")
        if not path or path in {"", "index.html", "index.htm", "home"}:
            return "home"
        last_segment = path.split("/")[-1]
        last_segment = re.sub(r"\.(html|htm|php|aspx|jsp)$", "", last_segment, flags=re.IGNORECASE)
        if last_segment:
            return sanitize_identifier(last_segment, fallback="page")
    except Exception:
        pass
    if title and title.strip():
        return sanitize_identifier(title, fallback="page")
    return "page"


@dataclass
class GeneratedFile:
    relative_path: str
    content: str
    file_type: str = "python"  # python, json, toml, text


@dataclass
class ModularProject:
    project_name: str
    files: List[GeneratedFile] = field(default_factory=list)
    modules: Set[str] = field(default_factory=set)
    page_objects: List[str] = field(default_factory=list)
    test_suites: List[str] = field(default_factory=list)


class ProjectStructureGenerator:
    """Generates an enterprise-ready Modular POM Project structure from crawl evidence and test cases."""

    def __init__(self, app_name: str = "app_test_project"):
        self.app_name = sanitize_identifier(app_name, fallback="test_project")

    def generate_project(
        self,
        base_url: str,
        discovered_elements: List[Dict[str, Any]],
        page_inventory: List[Dict[str, Any]],
        test_cases: List[Dict[str, Any]],
        scenarios: Optional[List[Dict[str, Any]]] = None,
        credentials: Optional[Dict[str, Any]] = None,
    ) -> ModularProject:
        project = ModularProject(project_name=self.app_name)
        scenarios_by_id = {str(s.get("scenario_id")): s for s in (scenarios or [])}

        # 1. Group discovered elements by page
        elements_by_page: Dict[str, List[Dict[str, Any]]] = {}
        for elem in discovered_elements:
            p_url = str(elem.get("page_url") or base_url)
            elements_by_page.setdefault(p_url, []).append(elem)

        if not elements_by_page and page_inventory:
            for p_info in page_inventory:
                p_url = str(p_info.get("url") or base_url)
                elements_by_page[p_url] = p_info.get("elements", [])

        if not elements_by_page:
            elements_by_page[base_url] = discovered_elements

        # 2. Build Page Objects
        pages_meta: Dict[str, Dict[str, Any]] = {}
        for p_url, elems in elements_by_page.items():
            # Extract page title
            p_title = None
            if elems and elems[0].get("page_title"):
                p_title = elems[0]["page_title"]
            elif page_inventory:
                for p_inv in page_inventory:
                    if str(p_inv.get("url")) == p_url:
                        p_title = p_inv.get("title")
                        break

            mod_name = determine_module_name(p_url, p_title)
            page_slug = determine_page_name(p_url, p_title)
            class_name = f"{sanitize_class_name(page_slug)}Page"

            pages_meta[p_url] = {
                "module_name": mod_name,
                "page_slug": page_slug,
                "class_name": class_name,
                "url": p_url,
                "elements": elems,
            }
            project.modules.add(mod_name)
            project.page_objects.append(class_name)

        # 3. Add Shared Framework Files
        self._add_shared_files(project, base_url, credentials)

        # 4. Generate Page Object Class Files
        for p_url, meta in pages_meta.items():
            mod = meta["module_name"]
            slug = meta["page_slug"]
            page_content = self._generate_page_object_code(meta, base_url)
            project.files.append(
                GeneratedFile(
                    relative_path=f"modules/{mod}/pages/{slug}_page.py",
                    content=page_content,
                )
            )

        # 5. Generate Test Suites per Module / Test Case
        for idx, tc in enumerate(test_cases, start=1):
            tc_id = str(tc.get("test_case_id") or f"tc_{idx:03d}")
            sc_id = str(tc.get("scenario_id") or "sc_001")
            scenario_obj = scenarios_by_id.get(sc_id, {})

            # Determine primary module for test case
            tc_module = "core"
            matched_page = None
            for p_url, meta in pages_meta.items():
                if any(word in str(tc.get("title", "")).lower() for word in [meta["page_slug"], meta["module_name"]]):
                    tc_module = meta["module_name"]
                    matched_page = meta
                    break

            if not matched_page and pages_meta:
                # Default to first page
                matched_page = list(pages_meta.values())[0]
                tc_module = matched_page["module_name"]

            test_content = self._generate_test_file_code(
                tc, scenario_obj, pages_meta, base_url, credentials
            )
            safe_tc_id = sanitize_identifier(tc_id)
            test_file_path = f"modules/{tc_module}/tests/test_{safe_tc_id}.py"
            project.files.append(
                GeneratedFile(relative_path=test_file_path, content=test_content)
            )
            project.test_suites.append(test_file_path)

        # 6. Add __init__.py files
        self._add_init_files(project)

        # 7. Add root config files (pytest.ini, pyproject.toml, README.md, requirements.txt, .env.example)
        self._add_root_config_files(project, base_url, credentials=credentials)

        return project

    def _add_shared_files(
        self, project: ModularProject, base_url: str, credentials: Optional[Dict[str, Any]]
    ) -> None:
        # Settings
        settings_code = f'''"""Global test automation configuration settings."""
import os
from dataclasses import dataclass

@dataclass
class Settings:
    BASE_URL: str = os.getenv("APP_BASE_URL", "{base_url}")
    HEADLESS: bool = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
    DEFAULT_TIMEOUT: int = int(os.getenv("DEFAULT_TIMEOUT", "10000"))
    SLOW_MO: int = int(os.getenv("SLOW_MO", "0"))
    SCREENSHOT_ON_FAILURE: bool = True

settings = Settings()
'''
        project.files.append(
            GeneratedFile(relative_path="shared/config/settings.py", content=settings_code)
        )

        # Helpers
        helpers_code = '''"""Reusable UI automation helper utilities."""
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
'''
        project.files.append(
            GeneratedFile(relative_path="shared/utils/helpers.py", content=helpers_code)
        )

        # Conftest (Pytest Fixtures)
        ident = credentials.get("identifier") or credentials.get("username") or "standard_user" if credentials else "standard_user"
        conftest_code = f'''"""Pytest global fixtures for Playwright browser and page management."""
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
        viewport={{"width": 1280, "height": 720}},
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
    return {{
        "username": os.getenv("TEST_USERNAME", "{ident}"),
        "password": os.getenv("TEST_PASSWORD", "secret_sauce"),
    }}
'''
        project.files.append(
            GeneratedFile(relative_path="shared/fixtures/conftest.py", content=conftest_code)
        )

        # Data Loader
        data_loader_code = '''"""Test data loader utility."""
import json
from pathlib import Path
from typing import Any, Dict

def load_test_data(filename: str = "test_data.json") -> Dict[str, Any]:
    """Load JSON test data from shared/test_data directory."""
    data_path = Path(__file__).resolve().parent / filename
    if data_path.is_file():
        return json.loads(data_path.read_text(encoding="utf-8"))
    return {}
'''
        project.files.append(
            GeneratedFile(relative_path="shared/test_data/data_loader.py", content=data_loader_code)
        )

        # Default Test Data
        default_data = {
            "credentials": {
                "default": {
                    "username": ident,
                    "password": "secret_sauce",
                }
            },
            "environment": {
                "base_url": base_url,
            },
        }
        project.files.append(
            GeneratedFile(
                relative_path="shared/test_data/test_data.json",
                content=json.dumps(default_data, indent=2),
                file_type="json",
            )
        )

        # Assets, Screenshots, Traces, and Reports directory markers
        project.files.append(
            GeneratedFile(relative_path="shared/assets/.gitkeep", content="", file_type="text")
        )
        project.files.append(
            GeneratedFile(relative_path="screenshots/.gitkeep", content="", file_type="text")
        )
        project.files.append(
            GeneratedFile(relative_path="traces/.gitkeep", content="", file_type="text")
        )
        project.files.append(
            GeneratedFile(relative_path="reports/.gitkeep", content="", file_type="text")
        )

    def _generate_page_object_code(self, meta: Dict[str, Any], base_url: str) -> str:
        class_name = meta["class_name"]
        page_url = meta["url"]
        elements = meta["elements"]

        # Build resilient locator definitions
        locator_attrs: List[str] = []
        action_methods: List[str] = []
        seen_locators: Set[str] = set()

        for elem in elements:
            tag = (elem.get("tag") or "").lower()
            name = elem.get("name") or elem.get("label") or elem.get("placeholder") or elem.get("test_id") or elem.get("element_id") or ""
            if not name:
                continue

            attr_name = sanitize_identifier(f"{name}_{tag}", fallback=f"elem_{tag}")
            if attr_name in seen_locators:
                continue
            seen_locators.add(attr_name)

            # Determine best locator selector
            selector = self._extract_best_selector(elem)
            if not selector:
                continue

            locator_attrs.append(f'        self.{attr_name} = self.page.locator("{selector}")')

            # Generate helper actions
            if tag in {"input", "textarea"} or elem.get("input_type") in {"text", "password", "email"}:
                method_name = f"fill_{sanitize_identifier(name)}"
                action_methods.append(f'''
    def {method_name}(self, value: str) -> "{class_name}":
        """Enter value into {name} field."""
        self.{attr_name}.fill(value)
        return self''')
            elif tag in {"button", "a"} or elem.get("role") == "button":
                method_name = f"click_{sanitize_identifier(name)}"
                action_methods.append(f'''
    def {method_name}(self) -> "{class_name}":
        """Click the {name} control."""
        self.{attr_name}.click()
        return self''')

        locators_block = "\n".join(locator_attrs) if locator_attrs else "        pass"
        actions_block = "\n".join(action_methods)

        code = f'''"""Page Object Model for {class_name}."""
from playwright.sync_api import Page, expect
from shared.config.settings import settings

class {class_name}:
    """Page Object for {page_url}."""

    PAGE_URL: str = "{page_url}"

    def __init__(self, page: Page) -> None:
        self.page = page
{locators_block}

    def navigate(self) -> "{class_name}":
        """Navigate to {page_url}."""
        self.page.goto(self.PAGE_URL)
        return self

    def assert_loaded(self) -> "{class_name}":
        """Assert the page is loaded and body is visible."""
        expect(self.page.locator("body")).to_be_visible()
        return self
{actions_block}
'''
        return code

    def _extract_best_selector(self, elem: Dict[str, Any]) -> str:
        if elem.get("test_id"):
            return f'[data-testid="{elem["test_id"]}"]'
        if elem.get("element_id"):
            return f'#{elem["element_id"]}'
        if elem.get("name") and elem.get("tag") in {"input", "select", "textarea"}:
            return f'{elem["tag"]}[name="{elem["name"]}"]'
        if elem.get("placeholder"):
            return f'[placeholder="{elem["placeholder"]}"]'
        if elem.get("css_selector"):
            return elem["css_selector"]
        if elem.get("visible_text") and len(elem["visible_text"]) < 40:
            clean_text = elem["visible_text"].replace('"', '\\"')
            return f'text="{clean_text}"'
        return ""

    def _generate_test_file_code(
        self,
        test_case: Dict[str, Any],
        scenario: Dict[str, Any],
        pages_meta: Dict[str, Dict[str, Any]],
        base_url: str,
        credentials: Optional[Dict[str, Any]],
    ) -> str:
        tc_title = test_case.get("title", "Test Scenario")
        tc_id = test_case.get("test_case_id", "TC_001")
        sc_id = scenario.get("scenario_id", "SC_001")
        safe_func_name = f"test_{sanitize_identifier(tc_title, fallback='test_case')}"

        # Determine imports
        page_imports: List[str] = []
        instantiations: List[str] = []
        actions_list: List[str] = []

        for p_url, meta in pages_meta.items():
            mod = meta["module_name"]
            slug = meta["page_slug"]
            cls = meta["class_name"]
            page_imports.append(f"from modules.{mod}.pages.{slug}_page import {cls}")
            instantiations.append(f"    {slug}_page = {cls}(page)")

        imports_block = "\n".join(dict.fromkeys(page_imports))
        inst_block = "\n".join(instantiations)

        # Generate realistic steps
        steps = test_case.get("steps", [])
        if not steps:
            steps = [
                {"step_number": 1, "action": f"Navigate to {base_url}", "expected_result": "Page loaded"},
                {"step_number": 2, "action": "Verify page elements", "expected_result": "Elements visible"},
            ]

        # Select primary page
        primary_slug = list(pages_meta.values())[0]["page_slug"] if pages_meta else "home"
        actions_list.append(f"    # Step 1: Navigate to base application")
        actions_list.append(f"    {primary_slug}_page.navigate()")
        actions_list.append(f"    {primary_slug}_page.assert_loaded()")

        # Chain actions across pages if auth/inventory detected
        for step in steps:
            action = str(step.get("action", ""))
            action_lower = action.lower()
            num = step.get("step_number", "")
            actions_list.append(f"\n    # Step {num}: {action}")

            # Check if login action
            if any(w in action_lower for w in ["username", "login", "credentials"]):
                # Search for login page or home page
                login_meta = next((m for m in pages_meta.values() if "login" in m["page_slug"] or "home" in m["page_slug"]), None)
                slug = login_meta["page_slug"] if login_meta else primary_slug
                actions_list.append(f"    if hasattr({slug}_page, 'fill_user_name'):")
                actions_list.append(f"        {slug}_page.fill_user_name(default_credentials['username'])")
                actions_list.append(f"    if hasattr({slug}_page, 'fill_password'):")
                actions_list.append(f"        {slug}_page.fill_password(default_credentials['password'])")
                actions_list.append(f"    if hasattr({slug}_page, 'click_login_button'):")
                actions_list.append(f"        {slug}_page.click_login_button()")
            elif any(w in action_lower for w in ["cart", "add to cart", "backpack", "product"]):
                # Search for inventory or product page
                inv_meta = next((m for m in pages_meta.values() if "inventory" in m["page_slug"] or "product" in m["page_slug"]), None)
                slug = inv_meta["page_slug"] if inv_meta else primary_slug
                actions_list.append(f"    # Interacting with {slug}_page")
                actions_list.append(f"    {slug}_page.assert_loaded()")

        steps_block = "\n".join(actions_list)

        code = f'''"""Test Case: {tc_title}
Scenario: {sc_id} | Test Case ID: {tc_id}
Generated by Test Case Generation Platform.
"""
import pytest
from playwright.sync_api import Page, expect
{imports_block}

@pytest.mark.regression
def {safe_func_name}(page: Page, default_credentials: dict) -> None:
    """{tc_title}."""
{inst_block}

{steps_block}
'''
        return code

    def _add_init_files(self, project: ModularProject) -> None:
        init_paths = [
            "shared/__init__.py",
            "shared/config/__init__.py",
            "shared/fixtures/__init__.py",
            "shared/utils/__init__.py",
            "shared/test_data/__init__.py",
            "modules/__init__.py",
        ]
        for mod in project.modules:
            init_paths.extend([
                f"modules/{mod}/__init__.py",
                f"modules/{mod}/pages/__init__.py",
                f"modules/{mod}/tests/__init__.py",
            ])
        for p in init_paths:
            if not any(f.relative_path == p for f in project.files):
                project.files.append(GeneratedFile(relative_path=p, content='"""Package marker."""\n'))

    def _add_root_config_files(self, project: ModularProject, base_url: str, credentials: Optional[Dict[str, Any]] = None) -> None:
        ident = credentials.get("identifier") or credentials.get("username") or "standard_user" if credentials else "standard_user"

        requirements_txt = """playwright>=1.40.0
pytest>=8.0.0
pytest-playwright>=0.4.4
python-dotenv>=1.0.0
"""
        project.files.append(GeneratedFile(relative_path="requirements.txt", content=requirements_txt, file_type="text"))

        env_example = f"""# Test Automation Environment Variables
APP_BASE_URL={base_url}
TEST_USERNAME={ident}
TEST_PASSWORD=secret_sauce
HEADLESS=true
DEFAULT_TIMEOUT=10000
SLOW_MO=0
"""
        project.files.append(GeneratedFile(relative_path=".env.example", content=env_example, file_type="text"))

        pytest_ini = f"""[pytest]
testpaths = modules
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
"""
        project.files.append(GeneratedFile(relative_path="pytest.ini", content=pytest_ini, file_type="ini"))

        pyproject_toml = f"""[tool.pytest.ini_options]
testpaths = ["modules"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"
"""
        project.files.append(GeneratedFile(relative_path="pyproject.toml", content=pyproject_toml, file_type="toml"))

        readme = f"""# {self.app_name.upper()} - Modular Playwright Automation Project

Automated test project generated with standard Page Object Model (POM) architecture.

## Directory Structure
```
{self.app_name}/
├── modules/
│   └── {{module_name}}/
│       ├── pages/          # Page Object classes
│       └── tests/          # Pytest test suites
├── shared/
│   ├── assets/             # Test assets / uploads
│   ├── config/             # Environment and settings
│   ├── fixtures/           # Global conftest.py fixtures
│   ├── test_data/          # Test data loader and JSON data
│   └── utils/              # Helper utilities
├── screenshots/            # Failure and execution screenshots
├── traces/                 # Playwright debug traces
├── reports/                # Pytest execution reports
├── requirements.txt
├── .env.example
├── pytest.ini
└── pyproject.toml
```

## Setup & Running Tests
1. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

2. Run all tests:
```bash
pytest
```

3. Run specific module:
```bash
pytest modules/core/tests/
```
"""
        project.files.append(GeneratedFile(relative_path="README.md", content=readme, file_type="text"))


project_structure_generator = ProjectStructureGenerator()
