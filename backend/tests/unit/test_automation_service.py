import uuid

import asyncio

import pytest

from app.schemas.automation_schema import (
    CrawlAndGenerateRequest,
    CrawlGenerationResponse,
    CrawlApplicationRequest,
    CrawlAnalysisResponse,
    DiscoveredElement,
    ExecuteScriptsRequest,
    ExecutionReport,
    FailureAnalysis,
    GenerateScriptsRequest,
    ScriptExecutionResult,
    ScriptGenerationResponse,
)
from app.services.automation_service import (
    SCRIPT_ARTIFACT_SUFFIX,
    AutomationError,
    AutomationService,
    InvalidGeneratedStepError,
    _best_page_url,
    _canonical_page_url,
    _challenge_evidence,
    _coverage_status,
    _link_skip_reason,
    _python_source,
    _step_execution_kind,
    _test_case_supported,
    _validate_css_selector,
    _validate_generated_source,
)


@pytest.mark.parametrize(
    ("percentage", "expected"),
    [(0, "missing"), (19.99, "missing"), (20, "partial"), (60, "partial"), (60.01, "covered"), (100, "covered")],
)
def test_coverage_status_boundaries(percentage, expected):
    assert _coverage_status(percentage, 20, 60) == expected


def test_coverage_status_rejects_reversed_thresholds():
    with pytest.raises(ValueError, match="must not exceed"):
        _coverage_status(50, 61, 60)


def test_step_execution_kind_requires_concrete_action_or_assertion():
    assert _step_execution_kind("Observe the inventory list displayed") == "invalid"
    assert _step_execution_kind("Verify the displayed details") == "invalid"
    assert _step_execution_kind("Click the 'Login' button") == "action"
    assert _step_execution_kind("Verify 'Inventory' text is visible") == "assertion"


def test_failure_locator_evidence_lists_verified_strategies_in_priority_order():
    details, attempts = AutomationService._locator_evidence({
        "tag": "button",
        "test_id": "submit",
        "aria_label": "Submit order",
        "role": "button",
        "name": "Submit",
        "css_selector": "#submit",
        "locator_validated": True,
        "page_url": "https://example.test/checkout",
    })

    assert details["discovered_page_url"] == "https://example.test/checkout"
    assert [item["strategy"] for item in attempts[:3]] == [
        "test_id",
        "aria_label",
        "role_and_accessible_name",
    ]
    assert all(item["attempted"] for item in attempts)


@pytest.mark.asyncio
async def test_observation_only_step_is_generated_script_defect():
    with pytest.raises(InvalidGeneratedStepError, match="no executable action"):
        await AutomationService()._perform(
            object(),
            "Observe the list of products",
            [],
        )


def test_cloudflare_challenge_is_rejected_before_generation():
    evidence = _challenge_evidence(
        title="Just a moment...",
        visible_text="Verify you are human",
        status_code=403,
        elements=[{"tag": "a", "name": "Privacy"}],
    )
    assert evidence is not None
    assert evidence["reason"] == "Cloudflare challenge"


def test_url_normalization_drops_tracking_but_keeps_meaningful_state():
    assert _canonical_page_url(
        "HTTPS://Example.com/products?utm_source=x&page=2#top"
    ) == "https://example.com/products?page=2"


def test_destructive_and_download_links_are_skipped():
    assert _link_skip_reason("https://example.com/logout", "example.com") == (
        "destructive_or_session_ending_link"
    )
    assert _link_skip_reason("https://example.com/report.pdf", "example.com") == (
        "download_only_link"
    )


@pytest.mark.asyncio
async def test_incomplete_crawl_generates_scripts_for_completed_pages(monkeypatch, tmp_path):
    service = AutomationService()
    url = "https://example.com/"
    monkeypatch.setattr(
        "app.services.automation_service.settings.automation_artifacts_path",
        str(tmp_path),
    )

    async def validate_url(_: str):
        return None

    async def discover(_: str):
        service._crawl_reports[_canonical_page_url(url)] = {
            "status": "crawl_incomplete",
            "start_url": url,
            "actual_application_reached": True,
            "failure_reason": "Maximum crawl execution time was reached.",
            "pages_discovered": 3,
            "pages_completed": 1,
            "pages_skipped": [],
            "remaining_crawl_queue": ["https://example.com/two"],
            "unprocessed_navigation_states": [],
            "navigation_relationships": [],
            "events": ["crawl_started", "crawl_in_progress", "crawl_incomplete"],
            "progress": {
                "pages_discovered": 3,
                "pages_completed": 1,
                "pages_remaining": 1,
                "current_crawl_depth": 1,
                "elapsed_seconds": 30,
                "estimated_completion_seconds": 30,
            },
            "page_inventory": [{
                "url": url,
                "final_url": url,
                "title": "Example",
                "elements": [{
                    "tag": "button",
                    "role": "button",
                    "name": "Continue",
                    "page_url": url,
                    "css_selector": "button:nth-of-type(1)",
                    "locator_validated": True,
                }],
            }],
        }
        raise AutomationError("crawl timed out")

    monkeypatch.setattr(service, "_validate_url", validate_url)
    monkeypatch.setattr(service, "_discover", discover)

    response = await service.crawl_and_generate(
        CrawlAndGenerateRequest(url=url),
        _dedicated_loop=True,
    )
    assert response.crawl_status == "crawl_incomplete"
    assert len(response.scripts) == 1
    assert response.scripts[0].page_url == url
    assert response.crawl_report["progress"]["pages_remaining"] == 1
    assert len(list(tmp_path.glob("crawl-*/*.pwscript"))) == 1


@pytest.mark.asyncio
async def test_crawl_job_stop_waits_for_partial_generation(monkeypatch):
    service = AutomationService()

    async def crawl_until_stopped(request, *, cancel_event=None, **_):
        while cancel_event is not None and not cancel_event.is_set():
            await asyncio.sleep(0)
        return CrawlGenerationResponse(
            crawl_id="crawl-partial",
            url=str(request.url),
            pages_crawled=1,
            elements_found=2,
            crawl_status="crawl_incomplete",
            crawl_report={
                "status": "crawl_incomplete",
                "actual_application_reached": True,
                "stop_requested": True,
                "events": ["crawl_stopped", "partial_script_generation_completed"],
            },
            scripts=[],
        )

    monkeypatch.setattr(service, "crawl_and_generate", crawl_until_stopped)
    started = await service.start_crawl_job(
        CrawlAndGenerateRequest(url="https://example.com")
    )
    stopped = service.stop_crawl_job(started.job_id)
    assert stopped.status == "stopping"
    await service._crawl_jobs[started.job_id]["task"]

    completed = service.crawl_job(started.job_id)
    assert completed.status == "completed"
    assert completed.stop_requested is True
    assert completed.result is not None
    assert completed.result.crawl_status == "crawl_incomplete"


@pytest.mark.asyncio
async def test_workflow_crawl_stop_generates_from_preserved_session(monkeypatch):
    service = AutomationService()
    workflow_id = uuid.uuid4()

    async def analyze_until_stopped(request, *, cancel_event=None, **_):
        while cancel_event is not None and not cancel_event.is_set():
            await asyncio.sleep(0)
        return CrawlAnalysisResponse(
            crawl_id="crawl-workflow-partial",
            application_url=str(request.application_url),
            crawl_status="crawl_incomplete",
            pages_crawled=1,
            elements_found=1,
            crawl_report={
                "status": "crawl_incomplete",
                "actual_application_reached": True,
                "stop_requested": True,
            },
            discovered_elements=[
                DiscoveredElement(tag="button", name="Continue")
            ],
        )

    async def generate_from_preserved(request, **_):
        assert request.crawl_id == "crawl-workflow-partial"
        return ScriptGenerationResponse(
            generation_id="gen-workflow-partial",
            application_url=str(request.application_url),
            reachable=True,
            crawl_report={
                "status": "crawl_incomplete",
                "actual_application_reached": True,
            },
            scripts=[],
        )

    monkeypatch.setattr(service, "analyze_application", analyze_until_stopped)
    monkeypatch.setattr(service, "generate", generate_from_preserved)
    started = await service.start_workflow_crawl_job(
        CrawlApplicationRequest(
            workflow_id=workflow_id,
            application_url="https://example.com",
        )
    )
    service.stop_workflow_crawl_job(started.job_id)
    await service._workflow_crawl_jobs[started.job_id]["task"]

    completed = service.workflow_crawl_job(started.job_id)
    assert completed.status == "completed"
    assert completed.stop_requested is True
    assert completed.crawl is not None
    assert completed.crawl.pages_crawled == 1
    assert completed.generation is not None
    assert completed.generation.generation_id == "gen-workflow-partial"


@pytest.mark.asyncio
async def test_execution_job_continues_independently_of_start_request(monkeypatch):
    service = AutomationService()
    release = asyncio.Event()

    async def execute_in_background(request):
        await release.wait()
        return ExecutionReport(
            execution_id="exec-background",
            generation_id=request.generation_id,
            mode=request.mode,
            total_scripts=0,
            passed_scripts=0,
            failed_scripts=0,
            skipped_scripts=0,
            execution_time_seconds=0,
            success_percentage=0,
            results=[],
        )

    monkeypatch.setattr(service, "execute", execute_in_background)
    started = await service.start_execution_job(
        ExecuteScriptsRequest(generation_id="gen-background")
    )
    await asyncio.sleep(0)
    assert service.execution_job(started.job_id).status == "running"

    release.set()
    await service._execution_jobs[started.job_id]["task"]
    completed = service.execution_job(started.job_id)
    assert completed.status == "completed"
    assert completed.report is not None
    assert completed.report.execution_id == "exec-background"


def test_dom_coverage_gate_rejects_generic_verification_steps():
    test_case = {
        "steps": [
            {"action": "Enter 'Lenovo' in the search field"},
            {"action": "Verify matching products are displayed"},
        ]
    }
    elements = [{"tag": "input", "label": "Search store", "page_url": "https://example.com"}]
    assert _test_case_supported(test_case, elements) is False


def test_evidence_screenshot_can_be_downloaded_as_pdf(tmp_path, monkeypatch):
    from PIL import Image

    monkeypatch.setattr(
        "app.services.automation_service.settings.automation_artifacts_path",
        str(tmp_path),
    )
    service = AutomationService()
    screenshot = tmp_path / "failure.png"
    Image.new("RGBA", (20, 10), (255, 0, 0, 128)).save(screenshot)

    content, filename = service.evidence_artifact_pdf(str(screenshot))

    assert filename == "failure.pdf"
    assert content.read(4) == b"%PDF"


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
async def test_successful_seacrawl_locator_is_saved_and_reused(monkeypatch, tmp_path):
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
        }, {
            "test_case_id": "TC-2",
            "scenario_id": "SC-1",
            "title": "Unsupported carousel",
            "steps": [{"step_number": 1, "action": "Select carousel mode", "expected_result": "Carousel opens"}],
            "requirement_ids": ["REQ-2"],
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
    crawl = await service.analyze_application(
        CrawlApplicationRequest(workflow_id=workflow_id, application_url="https://example.com")
    )
    response = await service.generate(
        GenerateScriptsRequest(
            workflow_id=workflow_id,
            application_url="https://example.com",
            crawl_id=crawl.crawl_id,
        )
    )
    assert response.reachable is True
    assert response.scripts[0].requirement_ids == ["REQ-1"]
    assert response.scripts[0].user_story_ids == ["US-1"]
    assert response.scripts[0].page_url == "https://example.com/"
    assert len(response.scripts) == 1
    assert response.scripts[0].lifecycle_status == "Valid"
    assert repr(state) == original
    assert (tmp_path / response.generation_id / f"{response.scripts[0].script_id}{SCRIPT_ARTIFACT_SUFFIX}").is_file()
    assert not list((tmp_path / response.generation_id).glob("*.py"))


@pytest.mark.asyncio
async def test_generation_uses_pages_captured_before_crawl_timeout(monkeypatch, tmp_path):
    workflow_id = uuid.uuid4()
    url = "https://example.com/"
    second_url = "https://example.com/two"
    service = AutomationService()
    monkeypatch.setattr(
        "app.services.automation_service.workflow_service.get",
        lambda _: {
            "workflow_id": workflow_id,
            "status": "completed",
            "scenarios": [{"scenario_id": "SC-1", "user_story_ids": ["US-1"]}],
            "test_cases": [{
                "test_case_id": "TC-1",
                "scenario_id": "SC-1",
                "title": "Continue",
                "steps": [{
                    "step_number": 1,
                    "action": "Click the Continue button",
                    "expected_result": "The next page opens",
                }],
            }],
        },
    )
    monkeypatch.setattr(
        "app.services.automation_service.settings.automation_artifacts_path",
        str(tmp_path),
    )
    crawl_id = "crawl-partial"
    element = {
        "tag": "button",
        "role": "button",
        "name": "Continue",
        "page_url": url,
        "css_selector": "button:nth-of-type(1)",
        "locator_validated": True,
    }
    partial_report = {
        "status": "crawl_incomplete",
        "actual_application_reached": True,
        "failure_reason": "Configurable hard crawl timeout was reached.",
        "pages_completed": 2,
        "pages_skipped": [],
        "remaining_crawl_queue": ["https://example.com/three"],
        "events": ["crawl_started", "crawl_incomplete"],
    }
    service._crawl_reports[_canonical_page_url(url)] = partial_report
    service._crawls[crawl_id] = {
        "crawl_id": crawl_id,
        "workflow_id": str(workflow_id),
        "application_url": url,
        "page_title": "Example",
        "crawl_report": partial_report,
        "application_map": {
            "pages": [
                {"url": url, "title": "Example", "elements": [element]},
                {"url": second_url, "title": "Second page", "elements": []},
            ],
            "relationships": [],
            "page_count": 2,
        },
        "discovered_elements": [element],
    }

    response = await service.generate(
        GenerateScriptsRequest(
            workflow_id=workflow_id,
            application_url=url,
            crawl_id=crawl_id,
        ),
    )

    assert len(response.scripts) == 2
    assert response.crawl_report["status"] == "crawl_incomplete"
    assert {script.page_url for script in response.scripts} == {url, second_url}


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
    crawl = await service.analyze_application(
        CrawlApplicationRequest(workflow_id=workflow_id, application_url="https://example.com")
    )
    generated = await service.generate(
        GenerateScriptsRequest(
            workflow_id=workflow_id,
            application_url="https://example.com",
            crawl_id=crawl.crawl_id,
        )
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
            page_url="https://example.com/products",
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
    assert intelligence.classification == "INCONCLUSIVE"
    assert intelligence.developer_implementation_plan is None
    assert intelligence.confidence_gate["checks"]["failure_reproducible"] is False
    assert report.developer_ready_tickets == []
    assert report.failed_requirement_mapping[0]["scenario_id"] == "SC-1"
    reproduced = service._save_report(
        ExecuteScriptsRequest(generation_id=generation_id, mode="automated"),
        [failed_result.model_copy(deep=True)],
        1,
        generation_directory,
        {"workflow": workflow},
    )
    reproduced_intelligence = reproduced.results[0].failure.intelligence
    assert reproduced_intelligence.classification == "APPLICATION_DEFECT"
    assert reproduced_intelligence.developer_implementation_plan is not None
    assert reproduced.developer_ready_tickets[0].test_case_reference == "TC-1"
    assert reproduced.qa_diagnostic_reports[0]["classification"] == "APPLICATION_DEFECT"
    assert reproduced.traceability_chains[0]["script"] == "pw-001"

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
