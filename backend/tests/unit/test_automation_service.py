import uuid

import pytest

from app.schemas.automation_schema import (
    DiscoveredElement,
    ExecuteScriptsRequest,
    FailureAnalysis,
    GenerateScriptsRequest,
    ScriptExecutionResult,
)
from app.services.automation_service import (
    SCRIPT_ARTIFACT_SUFFIX,
    AutomationService,
    _best_page_url,
    _python_source,
    _validate_css_selector,
    _validate_generated_source,
)


def test_generated_source_is_playwright_page_object_and_contains_traceable_id():
    source = _python_source(
        {
            "test_case_id": "TC-1",
            "title": "User login",
            "steps": [
                {"step_number": 1, "action": "Click the Login button", "expected_result": "Login form"}
            ],
        },
        "https://example.com/",
    )
    assert "class PageObjectUserLogin" in source
    assert "get_by_role" in source
    assert "get_by_label" in source
    assert "get_by_placeholder" in source
    assert "select_option" in source
    assert ".check()" in source
    assert "assert_expected" in source
    assert "TC-1" in source


def test_quoted_button_name_generates_valid_playwright_locators():
    source = _python_source(
        {
            "test_case_id": "TC-CART-2",
            "title": "Continue shopping from empty cart",
            "steps": [
                {
                    "step_number": 1,
                    "action": 'Click the "Continue shopping" button/link.',
                    "expected_result": "The catalog is displayed",
                }
            ],
        },
        "https://example.com/cart",
        [
            {
                "tag": "button",
                "role": "button",
                "name": "Continue shopping",
                "page_url": "https://example.com/cart",
            }
        ],
    )

    _validate_generated_source(source)
    compile(source, "<generated-test>", "exec")
    # Hallucinated CSS selectors must never appear
    assert 'button[name=/Click the \\\"Continue shopping\\\"' not in source
    # New stable_locator resolves directly from the discovered catalogue:
    # when a discovered element matches (Pass 1), it uses get_by_role with
    # exact=True instead of the old re.compile fallback.
    assert "get_by_role" in source
    # The discovered-element name must appear in the source (as a literal string)
    assert "Continue shopping" in source
    assert AutomationService._locator_phrase(
        'Click the "Continue shopping" button/link.'
    ) == "Continue shopping"


def test_selector_validation_rejects_malformed_quoted_attribute_selector():
    assert _validate_css_selector('button[name="Continue shopping"]') == (
        'button[name="Continue shopping"]'
    )
    with pytest.raises(ValueError):
        _validate_css_selector(
            'button[name=/Click the \\"Continue shopping\\" button/link/i]'
        )


class _FakeLocator:
    def __init__(self, *, visible=True, click_error=None, description="button"):
        self.visible = visible
        self.click_error = click_error
        self.description = description
        self.clicked = False

    @property
    def first(self):
        return self

    async def count(self):
        return 1

    async def is_visible(self):
        return self.visible

    async def evaluate(self, expression):
        return self.description

    async def click(self, **_):
        if self.click_error:
            raise self.click_error
        self.clicked = True


class _FakePage:
    def __init__(self):
        self.discovered = _FakeLocator(click_error=RuntimeError("stale element"))
        self.alternative = _FakeLocator(description="button | Continue shopping")
        self.empty = _FakeLocator(visible=False)

    def get_by_role(self, role, name=None, exact=False):
        if exact and role == "button" and name == "Continue shopping":
            return self.discovered
        if role == "button":
            return self.alternative
        return self.empty

    def get_by_label(self, *_args, **_kwargs):
        return self.empty

    def get_by_placeholder(self, *_args, **_kwargs):
        return self.empty

    def get_by_test_id(self, *_args, **_kwargs):
        return self.empty

    def get_by_text(self, *_args, **_kwargs):
        return self.empty


@pytest.mark.asyncio
async def test_action_retries_alternative_after_discovered_locator_fails():
    page = _FakePage()
    service = AutomationService()

    description = await service._perform(
        page,
        'Click the "Continue shopping" button',
        [{"tag": "button", "role": "button", "name": "Continue shopping"}],
    )

    assert page.alternative.clicked is True
    assert description == "button | Continue shopping"


@pytest.mark.asyncio
async def test_successful_skyvern_locator_is_saved_and_reused(monkeypatch, tmp_path):
    service = AutomationService()
    generation_id = "gen-test"
    generation = {
        "response": None,
        "workflow": {},
        "directory": tmp_path,
        "learned_locators": {},
    }
    stored = {}

    async def set_json(key, value, _ttl):
        stored[key] = value

    async def cache_generation(_generation_id):
        return None

    monkeypatch.setattr("app.services.automation_service.cache.set_json", set_json)
    monkeypatch.setattr(service, "_cache_generation", cache_generation)

    await service._save_learned_locator(
        generation_id,
        generation,
        "https://example.com/cart",
        'Click the "Continue shopping" button',
        'button[name="Continue shopping"]',
    )
    reused = await service._load_learned_locator(
        generation,
        "https://example.com/cart",
        'Click the "Continue shopping" button',
    )

    assert reused == 'button[name="Continue shopping"]'
    assert next(iter(stored.values()))["locator"] == reused


def test_registration_case_selects_discovered_signup_page():
    elements = [
        {"page_url": "https://example.com/", "role": "link", "name": "Home"},
        {"page_url": "https://example.com/signup", "label": "Email", "placeholder": "you@example.com"},
        {"page_url": "https://example.com/signup", "role": "button", "name": "Sign Up"},
    ]
    test_case = {
        "title": "Register a new account",
        "description": "Sign up with email",
        "steps": [{"action": "Click the Sign Up button"}],
    }
    assert _best_page_url(test_case, "https://example.com/", elements) == "https://example.com/signup"


@pytest.mark.asyncio
async def test_page_settle_does_not_wait_for_network_idle_by_default(monkeypatch):
    calls = []

    class Page:
        async def wait_for_load_state(self, state, timeout):
            calls.append((state, timeout))

    monkeypatch.setattr(
        "app.services.automation_service.settings.automation_wait_for_network_idle",
        False,
    )
    monkeypatch.setattr(
        "app.services.automation_service.settings.automation_navigation_settle_timeout_seconds",
        3,
    )

    await AutomationService._wait_for_page_stable(Page())

    assert calls == [("domcontentloaded", 3000)]


@pytest.mark.asyncio
async def test_network_idle_wait_is_short_and_explicitly_configurable(monkeypatch):
    calls = []

    class Page:
        async def wait_for_load_state(self, state, timeout):
            calls.append((state, timeout))

    monkeypatch.setattr(
        "app.services.automation_service.settings.automation_wait_for_network_idle",
        True,
    )
    monkeypatch.setattr(
        "app.services.automation_service.settings.automation_navigation_settle_timeout_seconds",
        2,
    )

    await AutomationService._wait_for_page_stable(Page())

    assert calls == [("domcontentloaded", 2000), ("networkidle", 2000)]


@pytest.mark.asyncio
async def test_generation_reads_completed_workflow_without_mutating_it(monkeypatch, tmp_path):
    workflow_id = uuid.uuid4()
    state = {
        "workflow_id": workflow_id,
        "status": "completed",
        "scenarios": [{"scenario_id": "SC-1", "user_story_ids": ["US-1"]}],
        "test_cases": [{
            "test_case_id": "TC-1",
            "scenario_id": "SC-1",
            "title": "Login",
            "steps": [{"step_number": 1, "action": "Open login", "expected_result": "Page opens"}],
            "requirement_ids": ["REQ-1"],
        }],
    }
    original = repr(state)
    service = AutomationService()
    monkeypatch.setattr("app.services.automation_service.workflow_service.get", lambda _: state)
    monkeypatch.setattr("app.services.automation_service.settings.automation_artifacts_path", str(tmp_path))

    async def validate_url(_: str):
        return None

    async def discover(_: str):
        return "Example", [DiscoveredElement(tag="button", role="button", name="Login")]

    monkeypatch.setattr(service, "_validate_url", validate_url)
    monkeypatch.setattr(service, "_discover", discover)
    response = await service.generate(
        GenerateScriptsRequest(workflow_id=workflow_id, application_url="https://example.com")
    )
    assert response.reachable is True
    assert response.scripts[0].requirement_ids == ["REQ-1"]
    assert response.scripts[0].user_story_ids == ["US-1"]
    assert repr(state) == original
    assert (tmp_path / response.generation_id / f"{response.scripts[0].script_id}{SCRIPT_ARTIFACT_SUFFIX}").is_file()
    assert not list((tmp_path / response.generation_id).glob("*.py"))


@pytest.mark.asyncio
async def test_manual_mode_skips_execution_and_produces_report(monkeypatch, tmp_path):
    workflow_id = uuid.uuid4()
    service = AutomationService()
    monkeypatch.setattr("app.services.automation_service.workflow_service.get", lambda _: {
        "workflow_id": workflow_id,
        "status": "completed",
        "scenarios": [{"scenario_id": "SC-1"}],
        "test_cases": [{
            "test_case_id": "TC-1", "scenario_id": "SC-1", "title": "Login",
            "steps": [{"step_number": 1, "action": "Open", "expected_result": "Open"}],
        }],
    })
    monkeypatch.setattr("app.services.automation_service.settings.automation_artifacts_path", str(tmp_path))
    monkeypatch.setattr(service, "_validate_url", lambda _: pytest.fail("replaced below"))

    async def validate_url(_: str):
        return None

    async def discover(_: str):
        return "Example", []

    monkeypatch.setattr(service, "_validate_url", validate_url)
    monkeypatch.setattr(service, "_discover", discover)
    generated = await service.generate(
        GenerateScriptsRequest(workflow_id=workflow_id, application_url="https://example.com")
    )
    # A new service instance simulates a Uvicorn reload between generation and execution.
    restarted_service = AutomationService()
    report = await restarted_service.execute(
        ExecuteScriptsRequest(generation_id=generated.generation_id, mode="manual")
    )
    assert report.total_scripts == 1
    assert report.skipped_scripts == 1
    assert report.results[0].traceability["test_case_id"] == "TC-1"
    reloaded_report = AutomationService().report(report.execution_id)
    assert reloaded_report.execution_id == report.execution_id


def test_failed_execution_generates_developer_ticket_and_retest_verification(
    monkeypatch, tmp_path
):
    workflow_id = uuid.uuid4()
    service = AutomationService()
    monkeypatch.setattr(
        "app.services.automation_service.settings.automation_artifacts_path",
        str(tmp_path),
    )
    generation_id = "gen-intelligence"
    generation_directory = tmp_path / generation_id
    generation_directory.mkdir()
    workflow = {
        "workflow_id": workflow_id,
        "input": {
            "epics": ["EP-1 Commerce"],
            "features": ["FEAT-1 Product search"],
            "user_stories": ["US-1 Search products"],
            "acceptance_criteria": ["AC-1 US-1 matching products are displayed"],
        },
        "scenarios": [
            {
                "scenario_id": "SC-1",
                "title": "Search products",
                "feature_ids": ["FEAT-1"],
                "user_story_ids": ["US-1"],
                "acceptance_criteria_ids": ["AC-1"],
            }
        ],
        "test_cases": [
            {
                "test_case_id": "TC-1",
                "scenario_id": "SC-1",
                "title": "Search returns matching products",
                "priority": "high",
                "requirement_ids": ["REQ-1"],
                "acceptance_criteria_ids": ["AC-1"],
                "steps": [
                    {
                        "step_number": 1,
                        "action": "Search for Lenovo",
                        "expected_result": "Matching products are displayed",
                    }
                ],
            }
        ],
    }
    failed_result = ScriptExecutionResult(
        script_id="pw-001",
        script_name="Search returns matching products",
        test_case_id="TC-1",
        scenario_id="SC-1",
        status="failed",
        duration_seconds=1,
        error_message="Expected matching products",
        failure=FailureAnalysis(
            test_case_id="TC-1",
            failed_step=1,
            expected_result="Matching products are displayed",
            actual_result="No products were displayed",
            failure_reason="AssertionError",
            failure_category="Assertion Failure",
        ),
        traceability={
            "requirements": ["REQ-1"],
            "user_stories": ["US-1"],
        },
    )
    report = service._save_report(
        ExecuteScriptsRequest(generation_id=generation_id, mode="automated"),
        [failed_result],
        1,
        generation_directory,
        {"workflow": workflow},
    )

    intelligence = report.results[0].failure.intelligence
    assert intelligence is not None
    assert intelligence.root_cause_category == "Incorrect business logic"
    assert intelligence.requirement_mapping.user_story[0]["id"] == "US-1"
    assert intelligence.developer_implementation_plan is not None
    assert "Matching products are displayed" in (
        intelligence.developer_implementation_plan.missing_functionality
    )
    assert report.developer_ready_tickets[0].test_case_reference == "TC-1"
    assert report.failed_requirement_mapping[0]["scenario_id"] == "SC-1"

    passed_result = ScriptExecutionResult(
        script_id="pw-001",
        script_name="Search returns matching products",
        test_case_id="TC-1",
        scenario_id="SC-1",
        status="passed",
        duration_seconds=1,
    )
    retest = service._save_report(
        ExecuteScriptsRequest(generation_id=generation_id, mode="automated"),
        [passed_result],
        1,
        generation_directory,
        {"workflow": workflow},
    )
    assert retest.retest_verification[0]["verified"] is True
    assert retest.developer_execution_reports[0]["missing_functionality"] == "None identified."
    assert retest.developer_execution_reports[0]["priority"] == "Low"
