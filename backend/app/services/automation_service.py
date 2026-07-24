from __future__ import annotations

import asyncio
import ast
import hashlib
import json
import logging
import re
import sys
import time
import traceback
import uuid
from pathlib import Path
from pprint import pformat
from typing import Any, Awaitable, Callable, TypeVar
from urllib.parse import urlsplit

import httpx

from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.automation_schema import (
    AutomationHealth,
    DiscoveredElement,
    AutomationRecommendation,
    DeveloperImplementationPlan,
    ExecuteScriptsRequest,
    ExecutionReport,
    FailureAnalysis,
    FailureEvidence,
    FailureIntelligence,
    GenerateScriptsRequest,
    GeneratedScript,
    ScriptExecutionResult,
    ScriptGenerationResponse,
    RequirementMapping,
    RetestStrategy,
)
from app.services.skyvern_service import SkyvernAdapter
from app.services.cache_service import cache
from app.services.workflow_service import workflow_service

R = TypeVar("R")
logger = logging.getLogger(__name__)
SCRIPT_ARTIFACT_SUFFIX = ".pwscript"


async def _on_playwright_loop(factory: Callable[[], Awaitable[R]]) -> R:
    """Run Playwright on a subprocess-capable loop on Windows.

    Uvicorn reload mode selects a Selector loop on Windows. That loop cannot
    start Playwright's Node subprocess, so browser work gets an isolated
    Proactor loop in a worker thread.
    """
    if sys.platform != "win32":
        return await factory()

    def run() -> R:
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(factory())
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    return await asyncio.to_thread(run)


class AutomationError(AppError):
    error_code = "AUTOMATION_ERROR"


class AutomationNotFound(AppError):
    status_code = 404
    error_code = "AUTOMATION_NOT_FOUND"


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")[:80] or "test"


def _meaningful_words(value: str) -> set[str]:
    ignored = {"a", "an", "and", "the", "to", "with", "using", "verify", "test", "user"}
    return {
        word.lower() for word in re.findall(r"[A-Za-z0-9]+", value)
        if len(word) > 1 and word.lower() not in ignored
    }


def _best_page_url(test_case: dict[str, Any], base_url: str, elements: list[dict[str, Any]]) -> str:
    intent = _meaningful_words(" ".join([
        str(test_case.get("title", "")),
        str(test_case.get("description", "")),
        " ".join(str(step.get("action", "")) for step in test_case.get("steps", [])),
    ]))
    pages = {str(item.get("page_url")) for item in elements if item.get("page_url")}
    if not pages:
        return base_url
    def score(page_url: str) -> int:
        page_words = _meaningful_words(urlsplit(page_url).path)
        page_elements = " ".join(
            " ".join(str(item.get(key) or "") for key in ("name", "label", "placeholder", "visible_text"))
            for item in elements if item.get("page_url") == page_url
        )
        return len(intent & (_meaningful_words(page_elements) | page_words))
    return max(pages, key=lambda page: (score(page), -len(page))) if pages else base_url


def _stable_version(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def _application_map(
    base_url: str, title: str | None, elements: list[dict[str, Any]]
) -> dict[str, Any]:
    pages: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, str]] = []
    origin = urlsplit(base_url)
    for element in elements:
        page_url = str(element.get("page_url") or base_url)
        page = pages.setdefault(
            page_url, {"url": page_url, "title": title if page_url == base_url else None, "elements": []}
        )
        page["elements"].append(element)
        href = element.get("href")
        if href:
            parsed = urlsplit(str(href))
            if parsed.netloc == origin.netloc:
                relationships.append(
                    {
                        "from": page_url,
                        "to": str(href).split("#", 1)[0],
                        "via": str(
                            element.get("name")
                            or element.get("visible_text")
                            or element.get("role")
                            or element.get("tag")
                        ),
                    }
                )
    return {
        "start_url": base_url,
        "pages": list(pages.values()),
        "relationships": relationships,
        "page_count": len(pages),
        "element_count": len(elements),
        "discovery_engine": "Skyvern + Playwright" if settings.skyvern_fallback_enabled else "Playwright",
        "capture_engine": "Playwright",
    }


def _test_case_supported(
    test_case: dict[str, Any], elements: list[dict[str, Any]]
) -> bool:
    identities = [
        _meaningful_words(
            " ".join(
                str(element.get(key) or "")
                for key in ("name", "label", "test_id", "placeholder", "visible_text")
            )
        )
        for element in elements
    ]
    for step in test_case.get("steps", []):
        action = str(step.get("action") or "")
        lowered = action.lower()
        if any(token in lowered for token in ("navigate", "open", "visit", "go to")):
            continue
        actionable = any(
            token in lowered
            for token in (
                "click",
                "press",
                "select",
                "choose",
                "check",
                "uncheck",
                "enter",
                "type",
                "fill",
                "search",
                "submit",
            )
        )
        # Observation/assertion steps do not require a control locator; Playwright
        # validates their expected result after the preceding interaction.
        if not actionable:
            continue
        action_words = _meaningful_words(action)
        if action_words and not any(action_words & identity for identity in identities):
            return False
    return True


def _validate_css_selector(selector: str) -> str:
    """Reject malformed CSS before it reaches Playwright's selector parser."""
    value = selector.strip()
    if not value or any(character in value for character in ("\x00", "\r", "\n")):
        raise ValueError("Selector must be a non-empty, single-line CSS selector")
    if re.search(r"\[[^\]]+[~|^$*]?=\s*/", value):
        raise ValueError("CSS attribute selectors cannot contain regex literals")
    pairs = {"]": "[", ")": "("}
    stack: list[str] = []
    quote: str | None = None
    escaped = False
    for character in value:
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if quote:
            if character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
        elif character in {"[", "("}:
            stack.append(character)
        elif character in pairs:
            if not stack or stack.pop() != pairs[character]:
                raise ValueError("Selector contains unbalanced brackets")
    if quote or stack:
        raise ValueError("Selector contains an unterminated quote or bracket")
    return value


def _validate_generated_source(source: str) -> None:
    """Compile generated Python and validate every literal CSS locator it contains."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "locator"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            _validate_css_selector(node.args[0].value)


def _python_source(
    test_case: dict[str, Any],
    application_url: str,
    discovered_elements: list[dict[str, Any]] | None = None,
) -> str:
    """Generate a Playwright test script whose selectors come ONLY from the
    discovered DOM.  No CSS is inferred from action text."""
    class_name = "PageObject" + "".join(part.title() for part in _safe_name(test_case["title"]).split("-"))
    steps = pformat(test_case.get("steps", []), width=100, sort_dicts=False)
    discovered = pformat(discovered_elements or [], width=100, sort_dicts=False)
    return f'''"""Generated from test case {test_case["test_case_id"]}."""
import re
from playwright.sync_api import Page, expect

BASE_URL = {application_url!r}
STEPS = {steps}
DISCOVERED_ELEMENTS = {discovered}


class {class_name}:
    def __init__(self, page: Page):
        self.page = page

    # ------------------------------------------------------------------
    # stable_locator: resolves ONLY from the discovered element catalogue.
    # Never invents a CSS selector from action text.
    # ------------------------------------------------------------------
    def stable_locator(self, instruction: str):
        ignored = {{
            "click", "press", "select", "choose", "check", "enter", "type",
            "fill", "button", "link", "field", "dropdown", "into", "from",
            "with", "the", "on", "in", "value",
        }}
        quoted = re.findall(r"[\\'\\\"]([^\\'\\\"]+)[\\'\\\"]", instruction)
        lowered = instruction.lower()
        target = (
            quoted[0]
            if quoted and any(t in lowered for t in ("click", "press"))
            else re.sub(r"[\\'\\\"][^\\'\\\"]+[\\'\\\"]", "", instruction)
        )
        words = [
            w for w in re.findall(r"[A-Za-z0-9]+", target)
            if len(w) > 1 and w.lower() not in ignored
        ]
        phrase_words = {{w.lower() for w in words}}

        # --- Pass 1: match against discovered catalogue ---
        best_score = 0
        best_element: dict | None = None
        for element in DISCOVERED_ELEMENTS:
            identity = " ".join(
                str(element.get(k) or "")
                for k in ("name", "label", "test_id", "placeholder", "visible_text")
            )
            score = len(phrase_words & set(re.findall(r"[a-z0-9]+", identity.lower())))
            if score > best_score:
                best_score = score
                best_element = element

        if best_element:
            if best_element.get("test_id"):
                return self.page.get_by_test_id(best_element["test_id"])
            if best_element.get("label"):
                return self.page.get_by_label(best_element["label"], exact=True)
            if best_element.get("role") and best_element.get("name"):
                return self.page.get_by_role(
                    best_element["role"], name=best_element["name"], exact=True
                )
            if best_element.get("placeholder"):
                return self.page.get_by_placeholder(
                    best_element["placeholder"], exact=True
                )
            if best_element.get("visible_text"):
                return self.page.get_by_text(
                    best_element["visible_text"], exact=False
                ).first

        raise AssertionError(
            f"Feature not found in application: no discovered element matches {{instruction!r}}"
        )

    def perform(self, instruction: str):
        lowered = instruction.lower()
        values = re.findall(r"[\\'\\\"]([^\\'\\\"]+)[\\'\\\"]", instruction)
        value = values[-1] if values else None
        if any(token in lowered for token in ("navigate", "open", "visit", "go to")):
            self.page.goto(BASE_URL, wait_until="domcontentloaded")
            self.page.wait_for_load_state("networkidle")
        elif any(token in lowered for token in ("select", "choose")):
            if value is None:
                raise AssertionError(f"Selection has no explicit UI value: {{instruction}}")
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            if locator.evaluate("el => el.tagName.toLowerCase()") == "select":
                locator.select_option(label=value)
            else:
                locator.click()
                self.page.get_by_role("option", name=re.compile(re.escape(value), re.I)).click()
        elif any(token in lowered for token in ("check", "uncheck")):
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            locator.uncheck() if "uncheck" in lowered else locator.check()
        elif any(token in lowered for token in ("click", "press")):
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            locator.click()
        elif any(token in lowered for token in ("enter", "type", "fill")):
            if value is None:
                raise AssertionError(f"Input has no explicit UI value: {{instruction}}")
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            locator.fill(value)
        else:
            expect(self.page.locator("body")).to_be_visible()

    def assert_expected(self, expected_result: str):
        quoted = re.findall(r"[\\'\\\"]([^\\'\\\"]+)[\\'\\\"]", expected_result)
        if quoted and any(word in expected_result.lower() for word in ("visible", "displayed", "shown")):
            expect(self.page.get_by_text(quoted[-1], exact=False).first).to_be_visible()
        else:
            expect(self.page.locator("body")).to_be_visible()


def test_{_safe_name(test_case["test_case_id"]).replace("-", "_")}(page: Page):
    app = {class_name}(page)
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    for step in STEPS:
        app.perform(step["action"])
        app.assert_expected(step["expected_result"])
'''


class AutomationService:
    def __init__(self) -> None:
        self._generations: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, ExecutionReport] = {}
        self.skyvern = SkyvernAdapter()

    @property
    def artifact_root(self) -> Path:
        root = Path(settings.automation_artifacts_path).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _mark_prior_script_lifecycle(
        self,
        workflow_id: Any,
        requirement_version: str,
        application_map_version: str | None,
        current_test_case_ids: set[str],
    ) -> None:
        """Version prior file-backed generations without changing database tables."""
        for manifest_path in self.artifact_root.glob("gen-*/generation.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if str(manifest.get("workflow", {}).get("workflow_id")) != str(workflow_id):
                    continue
                response = manifest.get("response", {})
                prior_requirement = response.get("requirement_version")
                prior_map = response.get("application_map_version")
                changed = False
                for script in response.get("scripts", []):
                    if str(script.get("test_case_id")) not in current_test_case_ids:
                        status = "Obsolete"
                    elif prior_requirement and prior_requirement != requirement_version:
                        status = "Regeneration Required"
                    elif prior_map and application_map_version and prior_map != application_map_version:
                        status = "Needs Review"
                    else:
                        status = "Valid"
                    if script.get("lifecycle_status") != status:
                        script["lifecycle_status"] = status
                        changed = True
                if changed:
                    manifest_path.write_text(
                        json.dumps(manifest, default=str, indent=2), encoding="utf-8"
                    )
            except (OSError, ValueError, TypeError):
                logger.warning("Could not update script lifecycle manifest path=%s", manifest_path)

    async def _validate_url(self, url: str) -> None:
        if settings.app_mock_mode:
            return
        try:
            async with httpx.AsyncClient(
                follow_redirects=True, timeout=settings.automation_navigation_timeout_seconds
            ) as client:
                response = await client.get(url, headers={"user-agent": "TestCaseAutomation/1.0"})
            if response.status_code >= 500:
                raise AutomationError(f"Application URL returned HTTP {response.status_code}")
        except httpx.HTTPError as exc:
            raise AutomationError("Application URL is not reachable") from exc

    async def _discover(self, url: str) -> tuple[str | None, list[DiscoveredElement]]:
        if settings.app_mock_mode:
            return "Mock Application", [
                DiscoveredElement(tag="button", role="button", name="Mock submit"),
                DiscoveredElement(tag="input", label="Mock input", input_type="text"),
            ]
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                origin = urlsplit(url)
                skyvern_urls = await self.skyvern.discover_urls(
                    url=url,
                    page_limit=settings.automation_crawl_page_limit,
                    depth_limit=settings.automation_crawl_depth_limit,
                )
                verified_candidates = [
                    candidate
                    for candidate in skyvern_urls
                    if urlsplit(candidate).scheme in {"http", "https"}
                    and urlsplit(candidate).netloc == origin.netloc
                ]
                pending = [(url, 0), *[(candidate, 1) for candidate in verified_candidates]]
                visited: set[str] = set()
                raw: list[dict[str, Any]] = []
                title = None
                while pending and len(visited) < settings.automation_crawl_page_limit:
                    page_url, depth = pending.pop(0)
                    if page_url in visited:
                        continue
                    await page.goto(page_url, wait_until="domcontentloaded", timeout=int(settings.automation_navigation_timeout_seconds * 1000))
                    visited.add(page.url)
                    title = title or await page.title()
                    discovered = await page.locator("button,input,select,textarea,a,[role],[data-testid]").evaluate_all(
                        """els => els.slice(0, 300).filter(el => {
                          const style = getComputedStyle(el); const box = el.getBoundingClientRect();
                          return style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
                        }).map(el => ({
                          role: el.getAttribute('role') || (el.tagName.toLowerCase() === 'input'
                            ? ({checkbox:'checkbox',radio:'radio',number:'spinbutton',submit:'button',button:'button'}[el.type] || 'textbox')
                            : ({button:'button',a:'link',select:'combobox',textarea:'textbox'}[el.tagName.toLowerCase()] ?? null)),
                          name: el.getAttribute('aria-label') || el.getAttribute('name') || el.innerText?.trim() || null,
                          label: el.labels?.[0]?.innerText?.trim() || el.getAttribute('aria-labelledby') || null,
                          placeholder: el.getAttribute('placeholder'), test_id: el.getAttribute('data-testid'),
                          visible_text: el.innerText?.trim() || null, href: el.href || null,
                          tag: el.tagName.toLowerCase(), input_type: el.getAttribute('type'),
                          checked: typeof el.checked === 'boolean' ? el.checked : null,
                          options: el.tagName.toLowerCase() === 'select' ? [...el.options].map(o => ({label:o.text.trim(), value:o.value})) : []
                        }))"""
                    )
                    for item in discovered:
                        item["page_url"] = page.url
                    raw.extend(discovered)
                    for item in discovered:
                        href = item.get("href")
                        parsed = urlsplit(href) if href else None
                        if parsed and parsed.scheme in {"http", "https"} and parsed.netloc == origin.netloc:
                            clean_href = href.split("#", 1)[0]
                            queued_urls = {queued_url for queued_url, _ in pending}
                            if (
                                depth < settings.automation_crawl_depth_limit
                                and clean_href not in visited
                                and clean_href not in queued_urls
                            ):
                                pending.append((clean_href, depth + 1))
                await browser.close()
            elements = [DiscoveredElement.model_validate(item) for item in raw]
            logger.info(
                "DOM discovery complete url=%s pages_visited=%d elements_found=%d",
                url, len(visited), len(elements),
            )
            return title, elements
        except Exception as exc:
            # Bug 1 fix: log the real exception so it appears in uvicorn console
            logger.error(
                "DOM discovery failed url=%s  error=%s: %s",
                url, type(exc).__name__, exc, exc_info=exc,
            )
            raise AutomationError(
                f"The URL responded, but Chromium could not inspect it: {type(exc).__name__}: {exc}. "
                "Run `playwright install chromium` if Playwright is not installed."
            ) from exc

    async def generate(
        self, request: GenerateScriptsRequest, *, _dedicated_loop: bool = False
    ) -> ScriptGenerationResponse:
        if sys.platform == "win32" and not settings.app_mock_mode and not _dedicated_loop:
            return await _on_playwright_loop(
                lambda: self.generate(request, _dedicated_loop=True)
            )
        state = workflow_service.get(request.workflow_id)
        if state.get("status") != "completed":
            raise AutomationError(
                f"Test scripts can only be generated for a completed workflow "
                f"(current status: {state.get('status', 'unknown')}). "
                "Wait for the workflow to finish or resume it if it is in manual review."
            )
        # Bug 3 fix: guard empty test_cases early so we return a clear error
        if not state.get("test_cases"):
            raise AutomationError(
                "The workflow completed but produced no test cases. "
                "Check the workflow result or re-run the workflow."
            )
        url = str(request.application_url)
        requirement_payload = {
            "input": state.get("input") or state.get("context"),
            "scenarios": state.get("scenarios", []),
            "test_cases": state.get("test_cases", []),
        }
        requirement_version = _stable_version(requirement_payload)
        logger.info("generate() start workflow_id=%s url=%s", request.workflow_id, url)
        script_cache_key = cache.fingerprint(
            "scripts",
            {
                "generator_version": 5,  # bump when generation logic changes
                "application_url": url,
                "scenarios": [
                    {key:value for key,value in item.items() if key != "project_id"}
                    for item in state.get("scenarios", [])
                ],
                "test_cases": [
                    {key:value for key,value in item.items() if key != "project_id"}
                    for item in state.get("test_cases", [])
                ],
                "review_decisions": state.get("review_decisions", {}),
            },
        )
        cached = await cache.get_json(script_cache_key)
        if cached:
            generation_id = f"gen-{uuid.uuid4()}"
            directory = self.artifact_root / generation_id
            directory.mkdir(parents=True, exist_ok=False)
            scripts = []
            for item in cached.get("scripts", []):
                restored = dict(item)
                restored["workflow_id"] = request.workflow_id
                restored["download_path"] = f"/api/v1/automation/scripts/{generation_id}/{restored['script_id']}/download"
                script = GeneratedScript.model_validate(restored)
                _validate_generated_source(script.source)
                # Keep runtime artifacts outside WatchFiles' default *.py include.
                # Otherwise every generation restarts Uvicorn when --reload is enabled.
                (directory / f"{script.script_id}{SCRIPT_ARTIFACT_SUFFIX}").write_text(
                    script.source, encoding="utf-8"
                )
                scripts.append(script)
            response = ScriptGenerationResponse(
                generation_id=generation_id,
                application_url=url,
                reachable=True,
                page_title=cached.get("page_title"),
                discovered_elements=[DiscoveredElement.model_validate(item) for item in cached.get("discovered_elements", [])],
                application_map=cached.get("application_map", {}),
                application_map_version=cached.get("application_map_version"),
                requirement_version=cached.get("requirement_version") or requirement_version,
                scripts=scripts,
            )
            self._mark_prior_script_lifecycle(
                request.workflow_id,
                requirement_version,
                response.application_map_version,
                {str(item.get("test_case_id")) for item in state.get("test_cases", [])},
            )
            self._generations[generation_id] = {
                "response": response,
                "workflow": state,
                "directory": directory,
                "learned_locators": {},
            }
            await self._cache_generation(generation_id)
            return response
        logger.info("Validating URL url=%s", url)
        await self._validate_url(url)
        logger.info("Starting DOM discovery url=%s", url)
        title, elements = await self._discover(url)
        logger.info(
            "Discovery complete: %d elements found. Building scripts for %d test cases.",
            len(elements), len(state.get("test_cases", [])),
        )
        generation_id = f"gen-{uuid.uuid4()}"
        directory = self.artifact_root / generation_id
        directory.mkdir(parents=True, exist_ok=False)
        scenarios = {str(item["scenario_id"]): item for item in state.get("scenarios", [])}
        element_dicts = [element.model_dump(mode="json") for element in elements]
        application_map = _application_map(url, title, element_dicts)
        application_map_version = _stable_version(application_map)
        self._mark_prior_script_lifecycle(
            request.workflow_id,
            requirement_version,
            application_map_version,
            {str(item.get("test_case_id")) for item in state.get("test_cases", [])},
        )
        scripts = []
        skipped_count = 0
        for index, test_case in enumerate(state.get("test_cases", []), start=1):
            if state.get("review_decisions", {}).get(f"testCase:{test_case['test_case_id']}") == "rejected":
                continue
            dom_supported = _test_case_supported(test_case, element_dicts)
            if not dom_supported:
                logger.info(
                    "Script marked Needs Review because one or more actions are not "
                    "backed by verified DOM elements "
                    "test_case_id=%s",
                    test_case["test_case_id"],
                )



            script_id = f"pw-{index:03d}-{_safe_name(str(test_case['test_case_id']))}"
            path = directory / f"{script_id}{SCRIPT_ARTIFACT_SUFFIX}"
            try:
                source = _python_source(
                    test_case,
                    _best_page_url(test_case, url, element_dicts),
                    element_dicts,
                )
                # Bug 6 fix: catch per-script validation errors so one bad script
                # doesn't abort generation of all remaining scripts.
                _validate_generated_source(source)
            except (SyntaxError, ValueError) as source_err:
                logger.warning(
                    "Script skipped – source validation failed "
                    "test_case_id=%s error=%s: %s",
                    test_case["test_case_id"], type(source_err).__name__, source_err,
                )
                skipped_count += 1
                continue
            path.write_text(source, encoding="utf-8")
            scenario = scenarios.get(str(test_case.get("scenario_id")), {})
            scripts.append(
                GeneratedScript(
                    script_id=script_id,
                    workflow_id=request.workflow_id,
                    test_case_id=str(test_case["test_case_id"]),
                    scenario_id=str(test_case["scenario_id"]),
                    name=test_case["title"],
                    application_url=url,
                    source=source,
                    download_path=f"/api/v1/automation/scripts/{generation_id}/{script_id}/download",
                    requirement_ids=test_case.get("requirement_ids", []),
                    user_story_ids=scenario.get("user_story_ids", []),
                    application_map_version=application_map_version,
                    requirement_version=requirement_version,
                    lifecycle_status="Valid" if dom_supported else "Needs Review",
                )
            )
        logger.info(
            "generate() complete: %d scripts built, %d skipped. generation_id=%s",
            len(scripts), skipped_count, generation_id,
        )
        if not scripts:
            # Provide a clear, actionable message instead of silent empty list
            reason = (
                "The coverage gate filtered all test cases because none of their step "
                "actions matched any element discovered on the page. Check that the "
                "application URL is correct and the page is fully rendered, or review "
                "the test case steps."
                if element_dicts
                else "Playwright could not discover any interactive elements on the page. "
                "Ensure the URL loads a real UI (not a login wall or error page)."
            )
            raise AutomationError(f"No scripts could be generated: {reason}")
        response = ScriptGenerationResponse(
            generation_id=generation_id,
            application_url=url,
            reachable=True,
            page_title=title,
            discovered_elements=elements,
            application_map=application_map,
            application_map_version=application_map_version,
            requirement_version=requirement_version,
            scripts=scripts,
        )
        self._generations[generation_id] = {
            "response": response,
            "workflow": state,
            "directory": directory,
            "learned_locators": {},
        }
        await self._cache_generation(generation_id)
        await cache.set_json(
            script_cache_key,
            {
                "page_title": title,
                "discovered_elements": [item.model_dump(mode="json") for item in elements],
                "application_map": application_map,
                "application_map_version": application_map_version,
                "requirement_version": requirement_version,
                "scripts": [item.model_dump(mode="json") for item in scripts],
            },
            settings.redis_script_ttl_seconds,
        )
        return response

    async def _cache_generation(self, generation_id: str) -> None:
        generation = self._generations[generation_id]
        manifest = {
            "response": generation["response"].model_dump(mode="json"),
            "workflow": generation["workflow"],
            "directory": str(generation["directory"]),
            "learned_locators": generation.get("learned_locators", {}),
        }
        (generation["directory"] / "generation.json").write_text(
            json.dumps(manifest, default=str, indent=2), encoding="utf-8"
        )
        await cache.set_json(
            cache.key("generation", generation_id),
            manifest,
            settings.redis_script_ttl_seconds,
        )

    async def generation(self, generation_id: str) -> dict[str, Any]:
        if generation_id in self._generations:
            return self._generations[generation_id]
        safe_generation_id = _safe_name(generation_id)
        if safe_generation_id == generation_id:
            manifest_path = self.artifact_root / generation_id / "generation.json"
            if manifest_path.is_file():
                try:
                    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
                    generation = {
                        "response": ScriptGenerationResponse.model_validate(stored["response"]),
                        "workflow": stored["workflow"],
                        "directory": manifest_path.parent,
                        "learned_locators": stored.get("learned_locators", {}),
                    }
                    self._generations[generation_id] = generation
                    return generation
                except (KeyError, ValueError, TypeError):
                    logger.warning(
                        "Automation generation manifest is invalid generation_id=%s",
                        generation_id,
                    )
        cached = await cache.get_json(cache.key("generation", generation_id))
        if cached:
            generation = {
                "response": ScriptGenerationResponse.model_validate(cached["response"]),
                "workflow": cached["workflow"],
                "directory": Path(cached["directory"]),
                "learned_locators": cached.get("learned_locators", {}),
            }
            self._generations[generation_id] = generation
            return generation
        raise AutomationNotFound("Script generation was not found")

    async def script_path(self, generation_id: str, script_id: str) -> Path:
        generation = await self.generation(generation_id)
        script = next(
            (item for item in generation["response"].scripts if item.script_id == script_id), None
        )
        if not script:
            raise AutomationNotFound("Generated script was not found")
        path = generation["directory"] / f"{script_id}{SCRIPT_ARTIFACT_SUFFIX}"
        if path.is_file():
            return path
        # Backward compatibility for generations created before runtime scripts
        # moved to the reload-safe artifact extension.
        legacy_path = generation["directory"] / f"{script_id}.py"
        if legacy_path.is_file():
            return legacy_path
        raise AutomationNotFound("Generated script artifact was not found")

    @staticmethod
    def _locator_phrase(action: str) -> str:
        ignored = {
            "click", "press", "select", "choose", "check", "uncheck", "enter", "type",
            "fill", "display", "observe", "verify", "view", "attempt", "handle",
            "switch", "to", "the", "button", "link", "field", "dropdown", "checkbox",
            "radio", "icon", "control", "option", "on", "in", "into", "from", "with",
            "value", "page", "load", "layout", "products", "items", "area", "action",
            "actions", "initial", "state", "by", "for", "a", "an",
        }
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", action)
        lowered = action.lower()
        target = quoted[0] if quoted and any(token in lowered for token in ("click", "press", "select", "choose")) else re.sub(r"['\"][^'\"]+['\"]", "", action)
        words = [word for word in re.findall(r"[A-Za-z0-9]+", target) if word.lower() not in ignored]
        return " ".join(words[-3:]) or action

    @staticmethod
    async def _element_description(locator: Any) -> str:
        try:
            return await locator.evaluate("""el => {
              const tag=el.tagName.toLowerCase(); const label=el.labels?.[0]?.innerText?.trim();
              return [tag, el.getAttribute('role'), label, el.getAttribute('aria-label'),
                el.getAttribute('placeholder'), el.getAttribute('data-testid'), el.innerText?.trim()]
                .filter(Boolean).join(' | ')
            }""")
        except Exception:
            return "UI element could not be inspected"

    @staticmethod
    def _discovered_locator_candidates(
        page: Any,
        phrase: str,
        discovered_elements: list[dict[str, Any]],
    ) -> list[Any]:
        phrase_words = _meaningful_words(phrase)
        ranked: list[tuple[int, dict[str, Any]]] = []
        for element in discovered_elements:
            identity = " ".join(
                str(element.get(key) or "")
                for key in (
                    "name", "label", "test_id", "placeholder", "visible_text",
                    "href", "title", "id", "class",
                )
            )
            score = len(phrase_words & _meaningful_words(identity))
            if score:
                ranked.append((score, element))
        candidates = []
        for _, element in sorted(ranked, key=lambda item: item[0], reverse=True):
            if element.get("test_id"):
                candidates.append(page.get_by_test_id(element["test_id"]))
            if element.get("label"):
                candidates.append(page.get_by_label(element["label"], exact=True))
            if element.get("role") and element.get("name"):
                candidates.append(
                    page.get_by_role(element["role"], name=element["name"], exact=True)
                )
            if element.get("placeholder"):
                candidates.append(
                    page.get_by_placeholder(element["placeholder"], exact=True)
                )
            if element.get("visible_text"):
                candidates.append(
                    page.get_by_text(element["visible_text"], exact=False)
                )
        return candidates

    async def _resolve_locators(
        self,
        page: Any,
        phrase: str,
        roles: tuple[str, ...] = (),
        discovered_elements: list[dict[str, Any]] | None = None,
    ) -> list[tuple[Any, str]]:
        pattern = re.compile(re.escape(phrase), re.I)
        candidates = self._discovered_locator_candidates(
            page, phrase, discovered_elements or []
        )
        for role in roles:
            candidates.append(page.get_by_role(role, name=pattern))
        candidates.extend([
            page.get_by_label(pattern),
            page.get_by_placeholder(pattern),
            page.get_by_test_id(phrase),
            page.get_by_text(pattern, exact=False),
        ])
        # Word-level fallback for individual key terms
        words = [w for w in re.findall(r"[A-Za-z0-9]+", phrase) if len(w) > 2]
        for word in words:
            word_pat = re.compile(re.escape(word), re.I)
            for role in roles:
                candidates.append(page.get_by_role(role, name=word_pat))
            candidates.append(page.get_by_text(word_pat, exact=False))
            if hasattr(page, "locator"):
                candidates.append(page.locator(f"[id*='{word.lower()}']"))
                candidates.append(page.locator(f"[class*='{word.lower()}']"))
                candidates.append(page.locator(f"[title*='{word.lower()}']"))
        resolved = []
        for candidate in candidates:
            try:
                if await candidate.count():
                    locator = candidate.first
                    if await locator.is_visible():
                        resolved.append(
                            (locator, await self._element_description(locator))
                        )
            except Exception:
                # A bad alternative must not prevent the remaining locator
                # strategies from being attempted.
                continue
        if resolved:
            return resolved
        raise LookupError(f"No visible role, label, placeholder, test-id, or text locator matched '{phrase}'")

    async def _perform(
        self,
        page: Any,
        action: str,
        discovered_elements: list[dict[str, Any]] | None = None,
    ) -> str | None:
        lowered = action.lower()
        phrase = self._locator_phrase(action)
        if any(token in lowered for token in ("navigate", "open", "visit", "go to")):
            try:
                locators = await self._resolve_locators(
                    page, phrase, ("link",), discovered_elements
                )
                last_error = None
                for locator, description in locators:
                    try:
                        await locator.click(timeout=int(settings.automation_action_timeout_seconds * 1000))
                        await page.wait_for_load_state(
                            "domcontentloaded",
                            timeout=int(
                                settings.automation_navigation_settle_timeout_seconds
                                * 1000
                            ),
                        )
                        return description
                    except Exception as exc:
                        last_error = exc
                if last_error:
                    raise last_error
            except LookupError:
                return f"page | {page.url}"
        values = re.findall(r"['\"]([^'\"]+)['\"]", action)
        desired = values[-1] if values else None
        roles: tuple[str, ...]
        interactive_tokens = ("click", "press", "select", "choose", "check", "uncheck", "enter", "type", "fill", "radio")
        if not any(token in lowered for token in interactive_tokens):
            # Passive / observation step — no element click/fill required
            return "passive | page state"
        if any(token in lowered for token in ("select", "choose")):
            roles = ("combobox", "radio")
        elif any(token in lowered for token in ("check", "uncheck", "radio")):
            roles = ("checkbox", "radio")
        elif any(token in lowered for token in ("click", "press")):
            roles = ("button", "link")
        elif any(token in lowered for token in ("enter", "type", "fill")):
            if desired is None:
                raise LookupError(f"Input action has no explicit value: '{action}'")
            roles = ("textbox", "spinbutton")
        else:
            roles = ("button", "link")

        locators = await self._resolve_locators(
            page, phrase, roles, discovered_elements
        )
        last_error: Exception | None = None
        for locator, description in locators:
            try:
                if any(token in lowered for token in ("select", "choose")):
                    tag = await locator.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "select":
                        if not desired:
                            raise LookupError(f"Selection action has no value for {description}")
                        options = await locator.locator("option").all()
                        option_data = [
                            (
                                (await option.inner_text()).strip(),
                                await option.get_attribute("value") or "",
                            )
                            for option in options
                        ]
                        match = next(
                            (
                                (label, value)
                                for label, value in option_data
                                if desired.casefold()
                                in {label.casefold(), value.casefold()}
                            ),
                            None,
                        )
                        if not match:
                            desired_words = _meaningful_words(desired)
                            scored = [
                                (
                                    len(
                                        desired_words
                                        & _meaningful_words(" ".join(option))
                                    ),
                                    option,
                                )
                                for option in option_data
                            ]
                            score, match = max(
                                scored, default=(0, None), key=lambda item: item[0]
                            )
                            if score == 0:
                                match = None
                        if not match:
                            raise LookupError(
                                f"No option matching '{desired}' in {description}"
                            )
                        await locator.select_option(
                            value=match[1] or None,
                            label=None if match[1] else match[0],
                        )
                    else:
                        await locator.click()
                        options = await self._resolve_locators(
                            page, desired or phrase, ("option", "radio")
                        )
                        await options[0][0].click()
                elif any(token in lowered for token in ("check", "uncheck", "radio")):
                    if "uncheck" in lowered:
                        await locator.uncheck()
                    else:
                        await locator.check()
                elif any(token in lowered for token in ("enter", "type", "fill")):
                    await locator.fill(
                        desired,
                        timeout=int(settings.automation_action_timeout_seconds * 1000),
                    )
                else:
                    await locator.click(
                        timeout=int(settings.automation_action_timeout_seconds * 1000)
                    )
                return description
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
        raise LookupError(f"No locator could perform action '{action}'")

    async def _retry_recovered(self, page: Any, locator_value: str, action: str) -> None:
        selector = _validate_css_selector(locator_value)
        locator = page.locator(selector).first
        if not await locator.count() or not await locator.is_visible():
            raise LookupError("Recovered selector did not match a visible element")
        lowered = action.lower()
        values = re.findall(r"['\"]([^'\"]+)['\"]", action)
        value = values[-1] if values else None
        if any(token in lowered for token in ("enter", "type", "fill")):
            await locator.fill(
                value or "",
                timeout=int(settings.automation_action_timeout_seconds * 1000),
            )
        elif any(token in lowered for token in ("select", "choose")) and value:
            if await locator.evaluate("el => el.tagName.toLowerCase()") == "select":
                await locator.select_option(label=value)
            else:
                await locator.click()
                await page.get_by_role("option", name=re.compile(re.escape(value), re.I)).click()
        elif any(token in lowered for token in ("check", "uncheck")):
            if "uncheck" in lowered:
                await locator.uncheck()
            else:
                await locator.check()
        else:
            await locator.click(timeout=int(settings.automation_action_timeout_seconds * 1000))

    @staticmethod
    def _learned_locator_key(url: str, action: str) -> str:
        parsed = urlsplit(url)
        return cache.fingerprint(
            "skyvern-locator",
            {
                "origin": f"{parsed.scheme}://{parsed.netloc}",
                "path": parsed.path,
                "action": " ".join(action.casefold().split()),
            },
        )

    async def _load_learned_locator(
        self, generation: dict[str, Any], url: str, action: str
    ) -> str | None:
        key = self._learned_locator_key(url, action)
        local = generation.setdefault("learned_locators", {}).get(key)
        if local:
            return str(local)
        cached = await cache.get_json(key)
        locator = cached.get("locator") if cached else None
        if locator:
            generation["learned_locators"][key] = locator
            return str(locator)
        return None

    async def _save_learned_locator(
        self,
        generation_id: str,
        generation: dict[str, Any],
        url: str,
        action: str,
        locator: str,
    ) -> None:
        selector = _validate_css_selector(locator)
        key = self._learned_locator_key(url, action)
        generation.setdefault("learned_locators", {})[key] = selector
        await cache.set_json(
            key,
            {"locator": selector},
            settings.redis_script_ttl_seconds,
        )
        await self._cache_generation(generation_id)

    # ------------------------------------------------------------------
    # New helpers (requirements 1, 4, 7, 8)
    # ------------------------------------------------------------------

    @staticmethod
    async def _dismiss_overlays(page: Any) -> None:
        """Silently dismiss common cookie banners, GDPR dialogs, and modals.

        Every selector attempt is wrapped in try/except so a missing or already-
        dismissed overlay never interrupts the main test flow.
        """
        dismiss_selectors = [
            "[aria-label*='Accept']",
            "[aria-label*='Close']",
            "[aria-label*='Dismiss']",
            "[id*='cookie'] button",
            "[id*='consent'] button",
            "[class*='cookie'] button",
            "[class*='consent'] button",
            "[class*='banner'] button",
            "[class*='modal'] [class*='close']",
            "button[data-dismiss]",
            "button[data-action*='close']",
        ]
        dismiss_texts = ["Accept", "Accept all", "Accept cookies", "I agree",
                         "Agree", "Close", "Dismiss", "Got it", "OK"]
        for selector in dismiss_selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=2000)
                    await page.wait_for_timeout(300)
            except Exception:
                pass
        for text in dismiss_texts:
            try:
                locator = page.get_by_role("button", name=re.compile(
                    rf"^{re.escape(text)}$", re.I
                ))
                if await locator.count() and await locator.is_visible():
                    await locator.first.click(timeout=2000)
                    await page.wait_for_timeout(300)
            except Exception:
                pass

    @staticmethod
    async def _wait_for_page_stable(page: Any) -> None:
        """Use a short navigation settle wait without blocking on background traffic."""
        try:
            await page.wait_for_load_state(
                "domcontentloaded",
                timeout=int(
                    settings.automation_navigation_settle_timeout_seconds * 1000
                ),
            )
        except Exception:
            return
        if settings.automation_wait_for_network_idle:
            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=int(
                        settings.automation_navigation_settle_timeout_seconds * 1000
                    ),
                )
            except Exception:
                pass

    @staticmethod
    async def _validate_navigation(page: Any, expected_url_prefix: str | None = None) -> None:
        """Assert the page loaded successfully (non-empty title, optional URL check).

        Raises NavigationError (subclass of AutomationError) on failure.
        """
        title = ""
        try:
            title = await page.title()
        except Exception:
            pass
        if not title:
            # Tolerate missing title for SPA apps — check URL instead
            if expected_url_prefix and not page.url.startswith(expected_url_prefix):
                raise AutomationError(
                    f"Navigation failure: unexpected URL {page.url!r}"
                )
        if expected_url_prefix and not page.url.startswith(expected_url_prefix.split("//")[0]):
            raise AutomationError(
                f"Navigation failure: URL scheme mismatch current={page.url!r}"
            )

    @staticmethod
    async def _element_exists(
        page: Any,
        phrase: str,
        discovered_elements: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Return True only if a visible element matching *phrase* exists on the page.

        Uses the same scoring logic as _discovered_locator_candidates so this
        check is consistent with the later _resolve_locators call.
        """
        phrase_words = _meaningful_words(phrase)
        if not phrase_words:
            return True  # empty phrase → no element required
        for element in (discovered_elements or []):
            identity = " ".join(
                str(element.get(k) or "")
                for k in ("name", "label", "test_id", "placeholder", "visible_text")
            )
            score = len(phrase_words & _meaningful_words(identity))
            if score == 0:
                continue
            # Build the locator and check visibility
            try:
                if element.get("test_id"):
                    locator = page.get_by_test_id(element["test_id"])
                elif element.get("label"):
                    locator = page.get_by_label(element["label"], exact=True)
                elif element.get("role") and element.get("name"):
                    locator = page.get_by_role(
                        element["role"], name=element["name"], exact=True
                    )
                elif element.get("placeholder"):
                    locator = page.get_by_placeholder(element["placeholder"], exact=True)
                else:
                    continue
                if await locator.count() and await locator.is_visible():
                    return True
            except Exception:
                continue
        # Broad text/role fallback
        pattern = re.compile(re.escape(phrase), re.I)
        for locator in [
            page.get_by_text(pattern, exact=False),
            page.get_by_role("button", name=pattern),
            page.get_by_role("link", name=pattern),
        ]:
            try:
                if await locator.count() and await locator.is_visible():
                    return True
            except Exception:
                continue
        return False

    async def _assert_expected(self, page: Any, expected_result: str) -> None:
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", expected_result)
        if quoted and any(
            word in expected_result.lower() for word in ("visible", "displayed", "shown")
        ):
            await page.get_by_text(quoted[-1], exact=False).first.wait_for(
                state="visible", timeout=int(settings.automation_action_timeout_seconds * 1000)
            )
        else:
            await page.locator("body").wait_for(state="visible")

    async def _quality_checks(
        self,
        page: Any,
        directory: Path,
        script_id: str,
        network_errors: list[str],
    ) -> dict[str, Any]:
        """Lightweight checks that reuse the live Playwright page and existing artifacts."""
        accessibility = await page.locator(
            "input:not([aria-label]):not([aria-labelledby]),"
            "button:not([aria-label]),img:not([alt])"
        ).evaluate_all(
            """els => els.slice(0, 50).filter(el => {
              if (el.tagName.toLowerCase() === 'input' && el.labels?.length) return false;
              if (el.tagName.toLowerCase() === 'button' && el.innerText?.trim()) return false;
              return true;
            }).map(el => ({tag: el.tagName.toLowerCase(), id: el.id || null}))"""
        )
        visual_path = directory / f"{script_id}-visual-current.png"
        await page.screenshot(path=str(visual_path), full_page=True)
        visual_hash = hashlib.sha256(visual_path.read_bytes()).hexdigest()
        baseline_path = directory / f"{script_id}-visual-baseline.sha256"
        previous_hash = (
            baseline_path.read_text(encoding="utf-8").strip()
            if baseline_path.is_file()
            else None
        )
        if previous_hash is None:
            baseline_path.write_text(visual_hash, encoding="utf-8")
        return {
            "accessibility": {
                "checked": True,
                "potential_violations": accessibility,
            },
            "visual_regression": {
                "checked": True,
                "baseline_created": previous_hash is None,
                "changed": bool(previous_hash and previous_hash != visual_hash),
                "current_screenshot": str(visual_path),
            },
            "api_contract": {
                "checked": True,
                "failed_responses": list(network_errors),
                "note": "Observed HTTP failures are captured; schema validation requires an application contract.",
            },
            "backend_observability": {
                "console_and_failed_request_capture": True,
            },
        }

    async def execute(
        self, request: ExecuteScriptsRequest, *, _dedicated_loop: bool = False
    ) -> ExecutionReport:
        if sys.platform == "win32" and not settings.app_mock_mode and not _dedicated_loop:
            return await _on_playwright_loop(
                lambda: self.execute(request, _dedicated_loop=True)
            )
        generation = await self.generation(request.generation_id)
        response: ScriptGenerationResponse = generation["response"]
        if request.mode == "manual":
            results = [
                ScriptExecutionResult(
                    script_id=script.script_id,
                    script_name=script.name,
                    test_case_id=script.test_case_id,
                    scenario_id=script.scenario_id,
                    status="skipped",
                    duration_seconds=0,
                    traceability={
                        "requirements": script.requirement_ids,
                        "user_stories": script.user_story_ids,
                        "scenario_id": script.scenario_id,
                        "test_case_id": script.test_case_id,
                    },
                )
                for script in response.scripts
            ]
            return self._save_report(request, results, 0, generation["directory"], generation)

        if settings.app_mock_mode:
            results = [
                ScriptExecutionResult(
                    script_id=script.script_id,
                    script_name=script.name,
                    test_case_id=script.test_case_id,
                    scenario_id=script.scenario_id,
                    status="passed",
                    duration_seconds=0.01,
                    traceability=self._traceability(script),
                )
                for script in response.scripts
            ]
            return self._save_report(request, results, 0.01 * len(results), generation["directory"], generation)

        started = time.perf_counter()
        results: list[ScriptExecutionResult] = []
        state = generation["workflow"]
        cases = {str(item["test_case_id"]): item for item in state.get("test_cases", [])}
        run_skyvern_calls = 0
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            disc_dicts = [
                item.model_dump(mode="json") for item in response.discovered_elements
            ]
            for script in response.scripts:
                test_started = time.perf_counter()
                console_logs: list[str] = []
                network_errors: list[str] = []
                # ---- Use a browser context so we can capture traces (req 11) ----
                context = await browser.new_context()
                await context.tracing.start(screenshots=True, snapshots=True, sources=False)
                page = await context.new_page()
                page.on("console", lambda message, logs=console_logs: logs.append(message.text))
                page.on(
                    "requestfailed",
                    lambda request, errors=network_errors: errors.append(
                        f"{request.method} {request.url}: {request.failure}"
                    ),
                )
                page.on(
                    "response",
                    lambda response, errors=network_errors: errors.append(
                        f"HTTP {response.status} {response.request.method} {response.url}"
                    )
                    if response.status >= 400
                    else None,
                )
                failed_step = None
                expected = None
                element = None
                skyvern_attempted = False
                skyvern_succeeded = False
                failure_category = "Script Generation"
                try:
                    test_case = cases[script.test_case_id]
                    target_url = _best_page_url(
                        test_case, response.application_url, disc_dicts
                    )
                    # ---- Navigation with explicit wait + validation (req 4, 7) ----
                    failure_category = "Navigation Failure"
                    try:
                        await page.goto(
                            target_url,
                            wait_until="domcontentloaded",
                            timeout=int(settings.automation_navigation_timeout_seconds * 1000),
                        )
                    except PlaywrightTimeoutError as nav_timeout:
                        failure_category = "Page Load Timeout"
                        raise nav_timeout
                    await self._wait_for_page_stable(page)
                    await self._validate_navigation(page, target_url)
                    # ---- Auto-dismiss overlays once after landing (req 8) ----
                    await self._dismiss_overlays(page)

                    per_test_calls = 0
                    for step in test_case.get("steps", []):
                        failed_step = step.get("step_number")
                        expected = step.get("expected_result")
                        action = step.get("action", "")
                        phrase = self._locator_phrase(action)
                        element = f"Requested target: {phrase}"

                        # ---- Pre-step overlay dismissal (req 8) ----
                        await self._dismiss_overlays(page)
                        lowered = action.lower()
                        failure_category = "Locator Failure"
                        try:
                            page_elements = [
                                el for el in disc_dicts
                                if not el.get("page_url") or el.get("page_url") == page.url
                            ]
                            element = await self._perform(page, action, page_elements)
                        except (LookupError, PlaywrightError, PlaywrightTimeoutError) as action_error:
                            # Classify timeout separately
                            if isinstance(action_error, PlaywrightTimeoutError):
                                failure_category = "Page Load Timeout"
                            action_recovered = False
                            # ---- Learned-locator retry ----
                            learned_locator = await self._load_learned_locator(
                                generation, page.url, action
                            )
                            if learned_locator:
                                try:
                                    await self._retry_recovered(page, learned_locator, action)
                                    element = f"Learned locator: {learned_locator}"
                                    action_recovered = True
                                except (LookupError, ValueError, PlaywrightError):
                                    pass
                            # ---- Skyvern fallback – only after all Playwright strategies fail (req 6) ----
                            if (
                                not action_recovered
                                and self.skyvern.enabled
                                and per_test_calls < settings.skyvern_max_calls_per_test
                                and run_skyvern_calls < settings.skyvern_max_calls_per_run
                            ):
                                per_test_calls += 1
                                run_skyvern_calls += 1
                                recovery = await self.skyvern.recover(
                                    url=page.url,
                                    action=action,
                                    expected_result=expected or "",
                                )
                                skyvern_attempted = recovery.attempted
                                skyvern_succeeded = recovery.succeeded
                                if recovery.locator:
                                    try:
                                        await self._retry_recovered(
                                            page, recovery.locator, action
                                        )
                                        await self._save_learned_locator(
                                            request.generation_id,
                                            generation,
                                            page.url,
                                            action,
                                            recovery.locator,
                                        )
                                        element = f"Skyvern locator: {recovery.locator}"
                                        skyvern_succeeded = True
                                    except (LookupError, ValueError, PlaywrightError):
                                        skyvern_succeeded = False
                                action_recovered = skyvern_succeeded
                            if not action_recovered:
                                raise action_error

                        # ---- Post-action assertion (req 4) ----
                        failure_category = "Assertion Failure"
                        await self._assert_expected(page, expected or "")

                    quality_checks = await self._quality_checks(
                        page, generation["directory"], script.script_id, network_errors
                    )
                    traceability = self._traceability(script)
                    traceability["quality_checks"] = quality_checks
                    results.append(
                        ScriptExecutionResult(
                            script_id=script.script_id,
                            script_name=script.name,
                            test_case_id=script.test_case_id,
                            scenario_id=script.scenario_id,
                            status="passed",
                            duration_seconds=round(time.perf_counter() - test_started, 3),
                            traceability=traceability,
                        )
                    )
                    # Stop trace cleanly on pass (no need to save)
                    try:
                        await context.tracing.stop()
                    except Exception:
                        pass

                except Exception as exc:
                    # ---- Classify environment errors (req 10) ----
                    if isinstance(exc, (ImportError, OSError, PermissionError, EnvironmentError)):
                        failure_category = "Environment Issue"
                    elif isinstance(exc, AssertionError):
                        failure_category = "Assertion Failure"

                    # ---- Screenshot (req 11) ----
                    screenshot_path: Path | None = None
                    try:
                        screenshot_path = generation["directory"] / f"{script.script_id}-failure.png"
                        await page.screenshot(path=str(screenshot_path), full_page=True)
                    except Exception:
                        screenshot_path = None

                    # ---- DOM snapshot (req 11) ----
                    dom_snapshot_path: Path | None = None
                    try:
                        dom_html = await page.content()
                        dom_snapshot_path = generation["directory"] / f"{script.script_id}-failure-dom.html"
                        dom_snapshot_path.write_text(dom_html, encoding="utf-8")
                    except Exception:
                        dom_snapshot_path = None

                    # ---- Playwright trace (req 11) ----
                    trace_path: Path | None = None
                    try:
                        trace_path = generation["directory"] / f"{script.script_id}-failure-trace.zip"
                        await context.tracing.stop(path=str(trace_path))
                    except Exception:
                        trace_path = None

                    failure = FailureAnalysis(
                        test_case_id=script.test_case_id,
                        failed_step=failed_step,
                        expected_result=expected,
                        actual_result=str(exc),
                        failure_reason=type(exc).__name__,
                        failure_category=failure_category,
                        page_url=page.url,
                        ui_element=element,
                        screenshot=str(screenshot_path) if screenshot_path else None,
                        dom_snapshot=str(dom_snapshot_path) if dom_snapshot_path else None,
                        trace_path=str(trace_path) if trace_path else None,
                        console_logs=console_logs,
                        network_errors=network_errors,
                        stack_trace=traceback.format_exc(),
                        skyvern_attempted=skyvern_attempted,
                        skyvern_succeeded=skyvern_succeeded,
                    )
                    results.append(
                        ScriptExecutionResult(
                            script_id=script.script_id,
                            script_name=script.name,
                            test_case_id=script.test_case_id,
                            scenario_id=script.scenario_id,
                            status="failed",
                            duration_seconds=round(time.perf_counter() - test_started, 3),
                            error_message=str(exc),
                            failure=failure,
                            traceability=self._traceability(script),
                        )
                    )
                finally:
                    try:
                        await page.close()
                    except Exception:
                        pass
                    try:
                        await context.close()
                    except Exception:
                        pass
            await browser.close()
        return self._save_report(request, results, time.perf_counter() - started, generation["directory"], generation)

    @staticmethod
    def _traceability(script: GeneratedScript) -> dict[str, Any]:
        return {
            "requirements": script.requirement_ids,
            "user_stories": script.user_story_ids,
            "scenario_id": script.scenario_id,
            "test_case_id": script.test_case_id,
            "script_id": script.script_id,
        }

    @staticmethod
    def _artifact_records(values: Any, id_keys: tuple[str, ...]) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        for index, value in enumerate(values if isinstance(values, list) else []):
            if isinstance(value, dict):
                artifact_id = next(
                    (str(value[key]) for key in id_keys if value.get(key)), str(index + 1)
                )
                title = str(
                    value.get("title")
                    or value.get("name")
                    or value.get("description")
                    or artifact_id
                )
            else:
                text = str(value)
                match = re.match(r"\s*([A-Za-z]+[-_ ]?\d+)", text)
                artifact_id = match.group(1).replace(" ", "-") if match else str(index + 1)
                title = text
            records.append({"id": artifact_id, "title": title})
        return records

    @staticmethod
    def _id_matches(reference: str, candidate: str) -> bool:
        normalize = lambda value: re.sub(r"[^a-z0-9]", "", value.lower()).lstrip("0")
        left, right = normalize(reference), normalize(candidate)
        if left == right:
            return True
        left_match = re.search(r"([a-z]+)0*(\d+)$", left)
        right_match = re.search(r"([a-z]+)0*(\d+)$", right)
        return bool(
            left_match
            and right_match
            and left_match.groups() == right_match.groups()
        )

    def _map_failure_requirements(
        self, workflow: dict[str, Any], result: ScriptExecutionResult
    ) -> tuple[RequirementMapping, dict[str, Any] | None, dict[str, Any] | None]:
        test_case = next(
            (
                item
                for item in workflow.get("test_cases", [])
                if str(item.get("test_case_id")) == result.test_case_id
            ),
            None,
        )
        scenario_id = (
            str(test_case.get("scenario_id"))
            if test_case and test_case.get("scenario_id")
            else result.scenario_id
        )
        scenario = next(
            (
                item
                for item in workflow.get("scenarios", [])
                if str(item.get("scenario_id")) == scenario_id
            ),
            None,
        )
        source = workflow.get("input") or workflow.get("context") or workflow
        story_records = self._artifact_records(
            source.get("user_stories", []), ("user_story_id", "story_id", "id")
        )
        criterion_records = self._artifact_records(
            source.get("acceptance_criteria", []),
            ("acceptance_criteria_id", "criterion_id", "id"),
        )
        feature_records = self._artifact_records(
            source.get("features", []), ("feature_id", "id")
        )
        epic_records = self._artifact_records(source.get("epics", []), ("epic_id", "id"))
        story_ids = {
            str(value)
            for value in (
                (scenario or {}).get("user_story_ids", [])
                or result.traceability.get("user_stories", [])
            )
        }
        criterion_ids = {
            str(value)
            for value in (
                ((test_case or {}).get("acceptance_criteria_ids") or [])
                + ((scenario or {}).get("acceptance_criteria_ids") or [])
            )
        }
        feature_ids = {
            str(value) for value in (scenario or {}).get("feature_ids", [])
        }
        matched_stories = [
            item
            for item in story_records
            if any(self._id_matches(reference, item["id"]) for reference in story_ids)
        ]
        matched_criteria = [
            item
            for item in criterion_records
            if any(
                self._id_matches(reference, item["id"])
                or reference.lower() in item["title"].lower()
                for reference in criterion_ids | story_ids
            )
        ]
        matched_features = [
            item
            for item in feature_records
            if any(self._id_matches(reference, item["id"]) for reference in feature_ids)
        ]
        mapping = RequirementMapping(
            epic=epic_records if len(epic_records) == 1 else [],
            feature=matched_features,
            user_story=matched_stories,
            acceptance_criteria=matched_criteria,
            scenario=[
                {
                    "id": str(scenario.get("scenario_id")),
                    "title": str(scenario.get("title") or scenario.get("scenario_id")),
                }
            ]
            if scenario
            else [],
            test_case=[
                {
                    "id": str(test_case.get("test_case_id")),
                    "title": str(test_case.get("title") or test_case.get("test_case_id")),
                }
            ]
            if test_case
            else [],
            requirement_ids=[
                str(value)
                for value in (
                    (test_case or {}).get("requirement_ids", [])
                    or result.traceability.get("requirements", [])
                )
            ],
        )
        return mapping, scenario, test_case

    @staticmethod
    def _safe_evidence_text(path: str | None, limit: int = 200_000) -> str:
        if not path:
            return ""
        try:
            evidence_path = Path(path)
            if evidence_path.is_file():
                return evidence_path.read_text(encoding="utf-8", errors="ignore")[:limit]
        except OSError:
            pass
        return ""

    def _has_prior_failure(self, generation_id: str, script_id: str) -> bool:
        if any(
            report.generation_id == generation_id
            and any(
                result.script_id == script_id and result.status == "failed"
                for result in report.results
            )
            for report in self._reports.values()
        ):
            return True
        reports_directory = self.artifact_root / "reports"
        if not reports_directory.is_dir():
            return False
        for report_path in sorted(
            reports_directory.glob("exec-*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:200]:
            try:
                stored = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if str(stored.get("generation_id")) != generation_id:
                continue
            if any(
                str(item.get("script_id")) == script_id
                and item.get("status") == "failed"
                for item in stored.get("results", [])
            ):
                return True
        return False

    def _classify_failure(
        self,
        failure: FailureAnalysis,
        mapping: RequirementMapping,
        test_case: dict[str, Any] | None,
    ) -> tuple[str, str, float, bool, str]:
        dom = self._safe_evidence_text(failure.dom_snapshot).lower()
        actual = (failure.actual_result or failure.failure_reason or "").lower()
        console = " ".join(failure.console_logs).lower()
        target = failure.ui_element or ""
        target_words = _meaningful_words(target)
        if not test_case or not mapping.scenario:
            return (
                "REQUIREMENT_MISMATCH",
                "Requirement mismatch",
                0.95,
                False,
                "The executed script cannot be correlated to both a generated test case and scenario.",
            )
        if any(token in dom for token in ("just a moment", "cf-chl-", "captcha")):
            return (
                "ENVIRONMENT_FAILURE",
                "Environment or configuration issue",
                0.96,
                False,
                "The captured DOM is an access challenge rather than the expected application page.",
            )
        significant_network_failure = any(
            re.search(r"\b(?:4|5)\d\d\b", entry)
            or any(token in entry.lower() for token in ("/api/", "graphql", "failed to fetch"))
            for entry in failure.network_errors
        )
        if significant_network_failure or any(
            token in console for token in ("500 ", "502 ", "503 ", "networkerror", "failed to fetch")
        ):
            return (
                "APPLICATION_DEFECT",
                "API/Backend failure",
                0.88,
                True,
                "Network or browser-console evidence shows a failed application request.",
            )
        if failure.failure_category in {"Environment Issue", "Page Load Timeout"}:
            return (
                "ENVIRONMENT_FAILURE",
                "Environment or configuration issue",
                0.84,
                False,
                "The browser or application environment did not reach a stable executable state.",
            )
        if failure.failure_category in {"Navigation Failure", "Navigation"}:
            return (
                "APPLICATION_DEFECT",
                "Navigation problem",
                0.86,
                True,
                "The observed URL or page transition differed from the required navigation path.",
            )
        if failure.failure_category == "Application Feature Missing":
            return (
                "MISSING_FEATURE",
                "Missing application functionality",
                0.94,
                True,
                "The required control or behavior was absent from the captured application state.",
            )
        if failure.failure_category in {"Locator Failure", "Locator"}:
            dom_words = _meaningful_words(dom)
            if target_words and not (target_words & dom_words):
                return (
                    "MISSING_FEATURE",
                    "Missing application functionality",
                    0.72,
                    True,
                    "The expected UI target is not represented in the captured DOM.",
                )
            return (
                "AUTOMATION_DEFECT",
                "Locator or automation issue",
                0.82,
                False,
                "The target appears to exist, but the generated locator or interaction strategy failed.",
            )
        expected = (failure.expected_result or "").lower()
        if any(token in actual for token in ("test data", "fixture", "seed data", "record not found")):
            return (
                "TEST_DATA_FAILURE",
                "Environment or configuration issue",
                0.84,
                False,
                "The failure indicates that required test data or fixtures are unavailable.",
            )
        if any(token in expected for token in ("validation", "required", "invalid", "error message")):
            return (
                "APPLICATION_DEFECT",
                "Validation issue",
                0.82,
                True,
                "The application validation response did not satisfy the expected rule.",
            )
        if failure.failure_category in {"Assertion Failure", "Application"}:
            return (
                "APPLICATION_DEFECT",
                "Incorrect business logic",
                0.85,
                True,
                "The action completed, but the resulting application state contradicted the expected behavior.",
            )
        if "hidden" in actual or "not visible" in actual or "intercept" in actual:
            return (
                "APPLICATION_DEFECT",
                "UI implementation issue",
                0.76,
                True,
                "The UI element exists but its visibility, layering, or interactive state prevented use.",
            )
        return (
            "AUTOMATION_DEFECT",
            "Locator or automation issue",
            0.65,
            False,
            "Available evidence points to the automation layer more strongly than an application defect.",
        )

    def _failure_intelligence(
        self,
        generation_id: str,
        workflow: dict[str, Any],
        result: ScriptExecutionResult,
    ) -> FailureIntelligence:
        failure = result.failure
        assert failure is not None
        mapping, scenario, test_case = self._map_failure_requirements(workflow, result)
        classification, category, confidence, application_issue, cause = self._classify_failure(
            failure, mapping, test_case
        )
        steps = (test_case or {}).get("steps", [])
        failed_step = next(
            (
                step
                for step in steps
                if str(step.get("step_number")) == str(failure.failed_step)
            ),
            {},
        )
        criteria = [
            {
                "id": item["id"],
                "criterion": item["title"],
                "satisfied": False,
                "verification": "Re-run the original Playwright test after implementation.",
            }
            for item in mapping.acceptance_criteria
        ]
        evidence_summary = []
        if failure.screenshot:
            evidence_summary.append("Failure screenshot captured.")
        if failure.dom_snapshot:
            evidence_summary.append("DOM snapshot captured at the deviation point.")
        if failure.trace_path:
            evidence_summary.append("Playwright trace captured for step-by-step replay.")
        if failure.console_logs:
            evidence_summary.append(f"{len(failure.console_logs)} browser console entries captured.")
        if failure.network_errors:
            evidence_summary.append(f"{len(failure.network_errors)} failed network requests captured.")
        evidence = FailureEvidence(
            screenshot=failure.screenshot,
            dom_snapshot=failure.dom_snapshot,
            playwright_trace=failure.trace_path,
            failed_locator=failure.ui_element,
            page_url=failure.page_url,
            console_findings=failure.console_logs[-20:],
            network_findings=failure.network_errors[-20:],
            evidence_summary=evidence_summary,
        )
        expected = failure.expected_result or str(failed_step.get("expected_result") or "Expected behavior was not recorded.")
        actual = failure.actual_result or failure.failure_reason
        previous_failure = self._has_prior_failure(generation_id, result.script_id)
        gate_checks = {
            "requirement_mapping_confirmed": bool(
                mapping.scenario and mapping.test_case and mapping.user_story
            ),
            "expected_and_actual_available": bool(expected.strip() and actual.strip()),
            "application_page_loaded": bool(
                failure.page_url
                and failure.failure_category not in {"Page Load Timeout", "Environment Issue"}
            ),
            "failure_reproducible": (
                previous_failure or not settings.automation_require_reproducible_failure
            ),
            "automation_and_environment_ruled_out": classification
            in {"APPLICATION_DEFECT", "MISSING_FEATURE"},
            "confidence_threshold_met": confidence
            >= settings.automation_defect_confidence_threshold,
        }
        gate_passed = all(gate_checks.values())
        if application_issue and not gate_passed:
            classification = "INCONCLUSIVE"
            application_issue = False
            cause = (
                f"{cause} Developer issue creation was withheld because the evidence "
                "confidence gate did not pass."
            )
        story_refs = [item["id"] for item in mapping.user_story]
        scenario_ref = mapping.scenario[0]["id"] if mapping.scenario else result.scenario_id
        test_case_ref = mapping.test_case[0]["id"] if mapping.test_case else result.test_case_id
        feature = mapping.feature[0]["title"] if mapping.feature else result.script_name
        priority = (
            "Critical"
            if category in {"API/Backend failure", "Missing application functionality"}
            and str((test_case or {}).get("priority", "")).lower() == "critical"
            else "High"
            if application_issue
            else "Medium"
        )
        implementation_plan = None
        automation_recommendation = None
        recommended_fix: list[str]
        if application_issue and gate_passed:
            ui_changes = []
            api_changes = []
            database_changes = ["No database change identified from current evidence."]
            validation_rules = []
            if category in {
                "Missing application functionality",
                "UI implementation issue",
                "Navigation problem",
            }:
                ui_changes = [
                    "Implement or correct the affected control and its accessible states.",
                    "Add stable role, label, and data-testid attributes for automated verification.",
                ]
            if category in {"API/Backend failure", "Incorrect business logic"}:
                api_changes = [
                    "Correct the service/API behavior that produces the observed result.",
                    "Add server-side tests for the mapped acceptance criteria.",
                ]
            if category == "Validation issue":
                validation_rules = [
                    "Implement the validation rule and return the required user-facing feedback.",
                    "Apply equivalent validation on the API boundary.",
                ]
            suggested = [
                "Reproduce the failure using the saved Playwright trace and evidence.",
                f"Implement the behavior described by test case {test_case_ref}.",
                "Add unit/integration coverage for the corrected behavior.",
                f"Re-run script {result.script_id} from generation {generation_id}.",
                "Confirm every mapped acceptance-criteria checklist item passes.",
            ]
            ticket_title = f"[{priority}] {category}: {feature}"
            jira_description = (
                f"h2. Problem\n{cause}\n\nh2. Expected\n{expected}\n\n"
                f"h2. Actual\n{actual}\n\nh2. References\n"
                f"* User stories: {', '.join(story_refs) or 'Unmapped'}\n"
                f"* Scenario: {scenario_ref}\n* Test case: {test_case_ref}\n"
                f"* Script: {result.script_id}\n\nh2. Evidence\n"
                + "\n".join(f"* {item}" for item in evidence_summary)
            )
            implementation_plan = DeveloperImplementationPlan(
                ticket_title=ticket_title,
                feature_affected=feature,
                user_story_reference=story_refs,
                test_scenario_reference=scenario_ref,
                test_case_reference=test_case_ref,
                problem_summary=f"{category} caused the automated scenario to fail.",
                missing_functionality=(
                    f"The application does not currently satisfy this behavior: {expected}"
                ),
                root_cause_analysis=cause,
                expected_behavior=expected,
                actual_behavior=actual,
                ui_changes_required=ui_changes or ["No UI change identified from current evidence."],
                backend_api_changes_required=api_changes or ["No backend/API change identified from current evidence."],
                database_changes=database_changes,
                validation_rules=validation_rules or ["Preserve existing validation rules unless contradicted by the mapped criteria."],
                acceptance_criteria_to_satisfy=[item["title"] for item in mapping.acceptance_criteria],
                suggested_implementation_steps=suggested,
                priority=priority,
                estimated_development_effort=(
                    "2-5 developer days" if priority in {"Critical", "High"} else "1-2 developer days"
                ),
                jira_description=jira_description,
            )
            recommended_fix = suggested
        else:
            automation_recommendation = AutomationRecommendation(
                script_changes=[
                    "Regenerate the script from the latest application map.",
                    "Keep the original scenario and test-case references unchanged.",
                ],
                locator_strategy=[
                    "Prefer data-testid, accessible label, and role/name locators.",
                    "Avoid position-based and generated CSS selectors.",
                ],
                wait_strategy=[
                    "Wait for a specific readiness signal instead of fixed delays.",
                    "Wait for navigation or the expected response after the triggering action.",
                ],
                assertion_strategy=[
                    "Assert the mapped expected result at the failed step.",
                    "Capture the actual visible state before failing.",
                ],
                navigation_strategy=[
                    "Navigate through the discovered application-map path.",
                    "Verify the final URL and page landmark before interacting.",
                ],
            )
            recommended_fix = [
                *automation_recommendation.locator_strategy,
                *automation_recommendation.wait_strategy,
                *automation_recommendation.assertion_strategy,
            ]
        retest = RetestStrategy(
            original_script_id=result.script_id,
            steps=[
                "Deploy the application or automation correction to the target environment.",
                f"Execute generation {generation_id} again in automated mode.",
                f"Verify the run passes the original failed step {failure.failed_step or 'unknown'}.",
                "Confirm mapped user stories, scenario, test case, and acceptance criteria.",
                "Compare the new execution report with this failure report.",
            ],
            verification_scope=[
                *story_refs,
                scenario_ref,
                test_case_ref,
                *[item["id"] for item in mapping.acceptance_criteria],
            ],
            acceptance_criteria_checklist=criteria,
        )
        return FailureIntelligence(
            classification=classification,
            root_cause_category=category,
            confidence=confidence,
            confidence_gate={
                "threshold": settings.automation_defect_confidence_threshold,
                "passed": gate_passed,
                "checks": gate_checks,
            },
            is_application_issue=application_issue,
            deviation_step={
                "step_number": failure.failed_step,
                "action": failed_step.get("action"),
                "expected_result": expected,
                "actual_result": actual,
            },
            requirement_mapping=mapping,
            root_cause_analysis=cause,
            expected_behavior=expected,
            actual_behavior=actual,
            evidence=evidence,
            developer_implementation_plan=implementation_plan,
            automation_recommendation=automation_recommendation,
            acceptance_criteria_checklist=criteria,
            recommended_fix=recommended_fix,
            retest_strategy=retest,
        )

    def _save_report(
        self,
        request: ExecuteScriptsRequest,
        results: list[ScriptExecutionResult],
        duration: float,
        directory: Path,
        generation: dict[str, Any],
    ) -> ExecutionReport:
        execution_id = f"exec-{uuid.uuid4()}"
        passed = sum(result.status == "passed" for result in results)
        failed = sum(result.status == "failed" for result in results)
        skipped = sum(result.status == "skipped" for result in results)
        workflow = generation.get("workflow", {})
        for result in results:
            if result.status == "failed" and result.failure:
                result.failure.intelligence = self._failure_intelligence(
                    request.generation_id, workflow, result
                )
        failed_mappings = [
            {
                "script_id": result.script_id,
                "test_case_id": result.test_case_id,
                "scenario_id": result.scenario_id,
                "root_cause_category": result.failure.intelligence.root_cause_category,
                "classification": result.failure.intelligence.classification,
                "requirement_mapping": result.failure.intelligence.requirement_mapping.model_dump(
                    mode="json"
                ),
            }
            for result in results
            if result.failure and result.failure.intelligence
        ]
        developer_tickets = [
            result.failure.intelligence.developer_implementation_plan
            for result in results
            if result.failure
            and result.failure.intelligence
            and result.failure.intelligence.developer_implementation_plan
        ]
        developer_execution_reports: list[dict[str, Any]] = []
        qa_diagnostic_reports: list[dict[str, Any]] = []
        traceability_chains: list[dict[str, Any]] = []
        for result in results:
            mapping, _mapped_scenario, _mapped_test_case = self._map_failure_requirements(
                workflow, result
            )
            defect_reference = None
            if result.failure and result.failure.intelligence:
                defect_reference = (
                    result.failure.intelligence.developer_implementation_plan.ticket_title
                    if result.failure.intelligence.developer_implementation_plan
                    else result.failure.intelligence.classification
                )
            traceability_chains.append(
                {
                    "epic": mapping.epic,
                    "feature": mapping.feature,
                    "user_story": mapping.user_story,
                    "acceptance_criterion": mapping.acceptance_criteria,
                    "scenario": mapping.scenario,
                    "test_case": mapping.test_case,
                    "script": result.script_id,
                    "execution_status": result.status,
                    "defect": defect_reference,
                }
            )
            failure = result.failure
            intelligence = failure.intelligence if failure else None
            qa_diagnostic_reports.append(
                {
                    "script_id": result.script_id,
                    "status": result.status,
                    "classification": (
                        intelligence.classification if intelligence else None
                    ),
                    "confidence": intelligence.confidence if intelligence else None,
                    "confidence_gate": (
                        intelligence.confidence_gate if intelligence else {}
                    ),
                    "locator": failure.ui_element if failure else None,
                    "stack_trace": failure.stack_trace if failure else None,
                    "screenshots": [failure.screenshot] if failure and failure.screenshot else [],
                    "dom_snapshot": failure.dom_snapshot if failure else None,
                    "network_errors": failure.network_errors if failure else [],
                    "console_logs": failure.console_logs if failure else [],
                    "playwright_trace": failure.trace_path if failure else None,
                    "automation_recommendations": (
                        intelligence.automation_recommendation.model_dump(mode="json")
                        if intelligence and intelligence.automation_recommendation
                        else {}
                    ),
                }
            )
            if result.failure and result.failure.intelligence:
                intelligence = result.failure.intelligence
                plan = intelligence.developer_implementation_plan
                developer_execution_reports.append(
                    {
                        "issue_title": (
                            plan.ticket_title
                            if plan
                            else intelligence.root_cause_category
                        ),
                        "affected_feature_user_story": {
                            "feature": (
                                plan.feature_affected
                                if plan
                                else ", ".join(
                                    item["title"]
                                    for item in intelligence.requirement_mapping.feature
                                )
                            ),
                            "user_stories": (
                                plan.user_story_reference
                                if plan
                                else [
                                    item["id"]
                                    for item in intelligence.requirement_mapping.user_story
                                ]
                            ),
                        },
                        "problem_description": (
                            plan.problem_summary
                            if plan
                            else intelligence.root_cause_analysis
                        ),
                        "expected_vs_actual_application_behavior": {
                            "expected": intelligence.expected_behavior,
                            "actual": intelligence.actual_behavior,
                        },
                        "missing_functionality": (
                            plan.missing_functionality
                            if plan
                            else "Not confirmed; evidence is insufficient for a developer task."
                        ),
                        "developer_implementation_requirements": {
                            "ui": plan.ui_changes_required if plan else [],
                            "backend_api": (
                                plan.backend_api_changes_required if plan else []
                            ),
                            "validation": plan.validation_rules if plan else [],
                            "database": plan.database_changes if plan else [],
                        },
                        "acceptance_criteria": [
                            {"id": item["id"], "title": item["title"]}
                            for item in intelligence.requirement_mapping.acceptance_criteria
                        ],
                        "priority": plan.priority if plan else "Medium",
                        "classification": intelligence.classification,
                        "confidence": intelligence.confidence,
                        "developer_issue_created": bool(plan),
                    }
                )
                continue
            mapping, _scenario, test_case = self._map_failure_requirements(
                workflow, result
            )
            expected_behaviors = [
                str(step.get("expected_result"))
                for step in (test_case or {}).get("steps", [])
                if step.get("expected_result")
            ]
            feature = (
                mapping.feature[0]["title"]
                if mapping.feature
                else result.script_name
            )
            passed_execution = result.status == "passed"
            developer_execution_reports.append(
                {
                    "issue_title": (
                        f"No application issue detected: {feature}"
                        if passed_execution
                        else f"Application behavior not executed: {feature}"
                    ),
                    "affected_feature_user_story": {
                        "feature": feature,
                        "user_stories": [
                            item["id"] for item in mapping.user_story
                        ],
                    },
                    "problem_description": (
                        "The application completed the mapped scenario and test case "
                        "without detecting missing or incorrect functionality."
                        if passed_execution
                        else "This test was not executed, so application functionality was not evaluated."
                    ),
                    "expected_vs_actual_application_behavior": {
                        "expected": (
                            " ".join(expected_behaviors)
                            or "The mapped application behavior should complete successfully."
                        ),
                        "actual": (
                            "All executed steps and expected-result checks completed successfully."
                            if passed_execution
                            else "No application behavior was observed because execution was skipped."
                        ),
                    },
                    "missing_functionality": (
                        "None identified."
                        if passed_execution
                        else "Not evaluated."
                    ),
                    "developer_implementation_requirements": {
                        "ui": ["No UI changes required."],
                        "backend_api": ["No backend or API changes required."],
                        "validation": ["No validation changes required."],
                        "database": ["No database changes required."],
                    },
                    "acceptance_criteria": [
                        {"id": item["id"], "title": item["title"]}
                        for item in mapping.acceptance_criteria
                    ],
                    "priority": "Low",
                    "classification": None,
                    "confidence": 1.0 if passed_execution else 0.0,
                    "developer_issue_created": False,
                }
            )
        prior_failed_ids = {
            prior_result.script_id
            for prior_report in self._reports.values()
            if prior_report.generation_id == request.generation_id
            for prior_result in prior_report.results
            if prior_result.status == "failed"
        }
        reports_directory = self.artifact_root / "reports"
        if reports_directory.is_dir():
            persisted_reports = sorted(
                reports_directory.glob("exec-*.json"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )[:200]
            for persisted_path in persisted_reports:
                try:
                    persisted = json.loads(persisted_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if str(persisted.get("generation_id")) != request.generation_id:
                    continue
                prior_failed_ids.update(
                    str(item.get("script_id"))
                    for item in persisted.get("results", [])
                    if item.get("status") == "failed" and item.get("script_id")
                )
        retest_verification = [
            {
                "script_id": result.script_id,
                "previous_status": "failed",
                "current_status": "passed",
                "verified": True,
                "message": (
                    "The original script now passes. Its mapped test case, scenario, "
                    "user story, and acceptance criteria should be reviewed in the "
                    "current evidence before closing the implementation ticket."
                ),
            }
            for result in results
            if result.status == "passed" and result.script_id in prior_failed_ids
        ]
        total_requirements = {
            str(value)
            for test_case in workflow.get("test_cases", [])
            for value in (
                (test_case.get("requirement_ids") or [])
                + (test_case.get("acceptance_criteria_ids") or [])
            )
        }
        executed_requirements = {
            str(value)
            for result in results
            for value in (
                result.traceability.get("requirements", [])
                + result.traceability.get("user_stories", [])
            )
        }
        failed_requirements = {
            value
            for item in failed_mappings
            for value in (
                item["requirement_mapping"]["requirement_ids"]
                + [
                    entry["id"]
                    for entry in item["requirement_mapping"]["acceptance_criteria"]
                ]
                + [
                    entry["id"]
                    for entry in item["requirement_mapping"]["user_story"]
                ]
            )
        }
        requirement_coverage = {
            "total_mapped_requirements": len(total_requirements),
            "executed_requirement_references": sorted(executed_requirements),
            "failed_requirement_references": sorted(failed_requirements),
            "covered_percentage": round(
                len(executed_requirements & total_requirements)
                / len(total_requirements)
                * 100,
                2,
            )
            if total_requirements
            else 0,
        }
        decisions = workflow.get("review_decisions", {})
        rejected_ids = {
            key.split(":", 1)[1] for key, decision in decisions.items()
            if key.startswith("testCase:") and decision == "rejected"
        }
        rejected_results = [
            {
                "test_case_id": str(item.get("test_case_id")),
                "test_case_name": str(item.get("title") or item.get("test_case_id")),
                "status": "rejected/unsupported",
                "reason": "Rejected during test-case review",
                "duration_seconds": 0,
                "screenshot": None,
                "logs": [],
            }
            for item in workflow.get("test_cases", [])
            if str(item.get("test_case_id")) in rejected_ids
        ]
        rejected = len(rejected_results)
        overall_total = len(results) + rejected
        report = ExecutionReport(
            execution_id=execution_id,
            generation_id=request.generation_id,
            mode=request.mode,
            total_scripts=len(results),
            passed_scripts=passed,
            failed_scripts=failed,
            skipped_scripts=skipped,
            rejected_scripts=rejected,
            execution_time_seconds=round(duration, 3),
            success_percentage=round((passed / len(results) * 100) if results else 0, 2),
            results=results,
            rejected_results=rejected_results,
            overall_summary={
                "total_tests": overall_total,
                "executed_tests": len(results),
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "rejected": rejected,
                "pass_rate": round((passed / overall_total * 100) if overall_total else 0, 2),
                "application_failures": sum(
                    bool(
                        result.failure
                        and result.failure.intelligence
                        and result.failure.intelligence.is_application_issue
                    )
                    for result in results
                ),
                "automation_failures": sum(
                    bool(
                        result.failure
                        and result.failure.intelligence
                        and not result.failure.intelligence.is_application_issue
                    )
                    for result in results
                ),
                "verified_fixes": len(retest_verification),
                "inconclusive": sum(
                    bool(
                        result.failure
                        and result.failure.intelligence
                        and result.failure.intelligence.classification == "INCONCLUSIVE"
                    )
                    for result in results
                ),
            },
            requirement_coverage=requirement_coverage,
            failed_requirement_mapping=failed_mappings,
            developer_ready_tickets=developer_tickets,
            developer_execution_reports=developer_execution_reports,
            qa_diagnostic_reports=qa_diagnostic_reports,
            traceability_chains=traceability_chains,
            requirement_version=response.requirement_version if (response := generation.get("response")) else None,
            script_lifecycle=[
                {
                    "script_id": script.script_id,
                    "status": script.lifecycle_status,
                    "requirement_version": script.requirement_version,
                    "application_map_version": script.application_map_version,
                }
                for script in (response.scripts if response else [])
            ],
            retest_verification=retest_verification,
        )
        self._reports[execution_id] = report
        path = directory / f"{execution_id}.json"
        path.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
        reports_directory.mkdir(parents=True, exist_ok=True)
        (reports_directory / f"{execution_id}.json").write_text(
            json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        return report

    def report(self, execution_id: str) -> ExecutionReport:
        if execution_id in self._reports:
            return self._reports[execution_id]
        if _safe_name(execution_id) == execution_id:
            path = self.artifact_root / "reports" / f"{execution_id}.json"
            if path.is_file():
                try:
                    report = ExecutionReport.model_validate_json(path.read_text(encoding="utf-8"))
                    self._reports[execution_id] = report
                    return report
                except ValueError:
                    logger.warning("Automation report file is invalid execution_id=%s", execution_id)
        raise AutomationNotFound("Execution report was not found")

    async def health(self, *, _dedicated_loop: bool = False) -> AutomationHealth:
        if settings.app_mock_mode:
            return AutomationHealth(
                status="healthy",
                playwright_available=True,
                browser_available=True,
                skyvern_enabled=False,
                skyvern_api_reachable=None,
                skyvern_configuration_valid=True,
                details={"mode": "mock"},
            )
        if sys.platform == "win32" and not _dedicated_loop:
            return await _on_playwright_loop(
                lambda: self.health(_dedicated_loop=True)
            )
        playwright_available = False
        browser_available = False
        details = {}
        try:
            from playwright.async_api import async_playwright

            playwright_available = True
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                browser_available = True
                await browser.close()
        except Exception as exc:
            details["playwright"] = type(exc).__name__
        skyvern_reachable = await self.skyvern.health() if self.skyvern.enabled else None
        healthy = playwright_available and browser_available
        return AutomationHealth(
            status="healthy" if healthy else "degraded",
            playwright_available=playwright_available,
            browser_available=browser_available,
            skyvern_enabled=self.skyvern.enabled,
            skyvern_api_reachable=skyvern_reachable,
            skyvern_configuration_valid=self.skyvern.configuration_valid,
            details=details,
        )


automation_service = AutomationService()
