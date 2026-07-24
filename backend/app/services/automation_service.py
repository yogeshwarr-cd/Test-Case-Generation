from __future__ import annotations

import asyncio
import ast
import json
import logging
import os
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
    ExecuteScriptsRequest,
    ExecutionReport,
    FailureAnalysis,
    GenerateScriptsRequest,
    GeneratedScript,
    ScriptExecutionResult,
    ScriptGenerationResponse,
    TraceabilityItem,
    TraceabilityReport,
)
from app.services.skyvern_service import SkyvernAdapter
from app.services.failure_analysis_service import FailureAnalysisService
from app.services.cache_service import cache
from app.services.workflow_service import workflow_service
from app.playwright_automation.semantic_mapping import build_intent
from app.playwright_automation.knowledge_graph import build_ui_graph

R = TypeVar("R")
logger = logging.getLogger(__name__)
SCRIPT_ARTIFACT_SUFFIX = ".pwscript"
AUTOMATION_PIPELINE_VERSION = "mapped-ui-v6-2026-07-24"


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


class AutomationAccessBlocked(RuntimeError):
    def __init__(self, access_status: str, reason: str) -> None:
        super().__init__(reason)
        self.access_status = access_status


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")[:80] or "test"


def _meaningful_words(value: str) -> set[str]:
    ignored = {"a", "an", "and", "the", "to", "with", "using", "verify", "test", "user"}
    return {
        word.lower() for word in re.findall(r"[A-Za-z0-9]+", value)
        if len(word) > 1 and word.lower() not in ignored
    }


def _explicit_input_value(
    action: str, expected_result: str, test_data: dict[str, Any] | None, seed: str
) -> str:
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", action)
    if quoted:
        return quoted[-1]
    combined = f"{action} {expected_result}".lower()
    for key, value in (test_data or {}).items():
        if _meaningful_words(str(key)) & _meaningful_words(combined):
            if value is not None and not isinstance(value, (dict, list)):
                return str(value)
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", expected_result)
    if quoted:
        return quoted[-1]
    stable = re.sub(r"[^a-z0-9]", "", seed.lower())[-10:] or "test"
    if "email" in combined:
        return f"automation+{stable}@example.com"
    if "password" in combined:
        return "Automation#2026"
    if "phone" in combined:
        return "2025550147"
    if any(word in combined for word in ("quantity", "number", "amount")):
        return "1"
    if "date" in combined:
        return "2026-01-15"
    return "Automation test"


def _plan_test_prerequisites(
    test_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build deterministic setup steps from producer cases already in the suite.

    This is domain-neutral: dependencies are inferred from precondition/action
    vocabulary and producer outcomes, not from website or product names.
    """
    planned: list[dict[str, Any]] = []
    producers: list[tuple[set[str], list[dict[str, Any]]]] = []
    dependency_terms = {
        "existing", "created", "available", "present", "added", "authenticated",
        "selected", "completed", "configured", "saved", "contains",
    }
    for original in test_cases:
        case = dict(original)
        own_steps = [dict(step) for step in case.get("steps", [])]
        precondition_text = " ".join(
            str(value) for value in case.get("preconditions", [])
        )
        intent_text = " ".join(
            [str(case.get("title", "")), precondition_text]
            + [str(step.get("action", "")) for step in own_steps[:1]]
        )
        intent_words = _meaningful_words(intent_text)
        needs_setup = bool(intent_words & dependency_terms) or bool(precondition_text)
        setup_steps: list[dict[str, Any]] = []
        if needs_setup and producers:
            ranked = sorted(
                (
                    (len(intent_words & produced_words), steps)
                    for produced_words, steps in producers
                ),
                key=lambda item: item[0],
                reverse=True,
            )
            if ranked and ranked[0][0] > 0:
                setup_steps = [
                    {
                        **step,
                        "step_number": index,
                        "is_prerequisite": True,
                    }
                    for index, step in enumerate(ranked[0][1], start=1)
                ]
        combined = setup_steps + own_steps
        case["steps"] = [
            {**step, "step_number": index}
            for index, step in enumerate(combined, start=1)
        ]
        case["prerequisite_step_count"] = len(setup_steps)
        planned.append(case)
        outcome_text = " ".join(
            [str(case.get("title", ""))]
            + [str(step.get("expected_result", "")) for step in own_steps]
        )
        producers.append((_meaningful_words(outcome_text), combined))
    return planned


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
    """Quality gate: syntax, intent contract, assertions, and CSS literals."""
    tree = ast.parse(source)
    required_names = {"BASE_URL", "STEPS", "DISCOVERED_ELEMENTS", "AUTOMATION_INTENT"}
    assigned = {
        node.targets[0].id
        for node in tree.body
        if isinstance(node, ast.Assign)
        and node.targets
        and isinstance(node.targets[0], ast.Name)
    }
    missing = required_names - assigned
    if missing:
        raise ValueError(f"Generated script is missing quality-gate fields: {sorted(missing)}")
    functions = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if not any(name in functions for name in {"assert_expected", "assert_step", "assert_outcome"}):
        raise ValueError("Generated script contains no deterministic assertion handler")
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
    target_url: str | None = None,
) -> str:
    """Generate a Playwright test script whose selectors come ONLY from the
    discovered DOM.  No CSS is inferred from action text."""
    class_name = "PageObject" + "".join(part.title() for part in _safe_name(test_case["title"]).split("-"))
    steps = pformat(test_case.get("steps", []), width=100, sort_dicts=False)
    discovered = pformat(discovered_elements or [], width=100, sort_dicts=False)
    intent = pformat(build_intent(test_case, discovered_elements or []), width=100, sort_dicts=False)
    return f'''"""Generated from test case {test_case["test_case_id"]}."""
import re
from playwright.sync_api import Page, expect

BASE_URL = {application_url!r}
TARGET_URL = {(target_url or application_url)!r}
STEPS = {steps}
DISCOVERED_ELEMENTS = {discovered}
AUTOMATION_INTENT = {intent}
TEST_DATA = {pformat(test_case.get("test_data", {}), width=100, sort_dicts=False)}
TEST_SEED = {str(test_case["test_case_id"])!r}


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
                for k in ("name", "label", "test_id", "element_id", "html_name",
                          "aria_label", "placeholder", "visible_text")
            )
            score = len(phrase_words & set(re.findall(r"[a-z0-9]+", identity.lower())))
            if score > best_score:
                best_score = score
                best_element = element

        if best_element:
            if best_element.get("test_id"):
                return self.page.get_by_test_id(best_element["test_id"])
            if best_element.get("element_id"):
                return self.page.locator(
                    "[id=" + repr(best_element["element_id"]) + "]"
                )
            if best_element.get("aria_label"):
                return self.page.get_by_label(
                    best_element["aria_label"], exact=True
                )
            if best_element.get("label"):
                return self.page.get_by_label(best_element["label"], exact=True)
            if best_element.get("role") and best_element.get("name"):
                return self.page.get_by_role(
                    best_element["role"], name=best_element["name"], exact=True
                )
            if best_element.get("html_name"):
                return self.page.locator(
                    "[name=" + repr(best_element["html_name"]) + "]"
                )
            if best_element.get("placeholder"):
                return self.page.get_by_placeholder(
                    best_element["placeholder"], exact=True
                )
            if best_element.get("visible_text"):
                return self.page.get_by_text(
                    best_element["visible_text"], exact=False
                ).first

        # --- Pass 2: visible-text fallback using quoted value only ---
        if quoted:
            pattern = re.compile(re.escape(quoted[0]), re.I)
            for candidate in [
                self.page.get_by_role("button", name=pattern),
                self.page.get_by_label(pattern),
                self.page.get_by_placeholder(pattern),
                self.page.get_by_text(pattern, exact=False),
            ]:
                if candidate.count():
                    return candidate.first

        raise AssertionError(
            f"Feature not found in application: no discovered element matches {{instruction!r}}"
        )

    def value_for(self, instruction: str, expected_result: str):
        quoted = re.findall(r"[\\'\\\"]([^\\'\\\"]+)[\\'\\\"]", instruction)
        if quoted:
            return quoted[-1]
        combined = f"{{instruction}} {{expected_result}}".lower()
        for key, value in TEST_DATA.items():
            if set(re.findall(r"[a-z0-9]+", str(key).lower())) & set(re.findall(r"[a-z0-9]+", combined)):
                if value is not None and not isinstance(value, (dict, list)):
                    return str(value)
        stable = re.sub(r"[^a-z0-9]", "", TEST_SEED.lower())[-10:] or "test"
        if "email" in combined:
            return f"automation+{{stable}}@example.com"
        if "password" in combined:
            return "Automation#2026"
        if any(word in combined for word in ("quantity", "number", "amount")):
            return "1"
        return "Automation test"

    def perform(self, instruction: str, expected_result: str):
        lowered = instruction.lower()
        values = re.findall(r"[\\'\\\"]([^\\'\\\"]+)[\\'\\\"]", instruction)
        value = values[-1] if values else self.value_for(instruction, expected_result)
        if any(token in lowered for token in ("navigate", "open", "visit", "go to")):
            self.page.goto(TARGET_URL, wait_until="domcontentloaded")
        elif re.search(r"\\bpress(?:\\s+the)?\\s+(enter|return|tab|escape|space)(?:\\s+key)?\\b", lowered):
            key = re.search(r"\\b(enter|return|tab|escape|space)\\b", lowered).group(1)
            self.page.keyboard.press({{"return": "Enter", "space": "Space"}}.get(key, key.title()))
        elif any(token in lowered for token in ("select", "choose")):
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
        elif "focus" in lowered:
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            locator.focus()
        elif any(token in lowered for token in ("enter", "type", "fill")):
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            locator.fill(value)
        else:
            return

    def assert_expected(self, expected_result: str, action: str):
        lowered = expected_result.lower()
        quoted = re.findall(r"[\\'\\\"]([^\\'\\\"]+)[\\'\\\"]", expected_result)
        if any(word in lowered for word in ("entered", "input", "field", "value")) and any(
            word in lowered for word in ("contains", "display", "entered", "value")
        ):
            expect(self.stable_locator(action)).to_have_value(
                self.value_for(action, expected_result)
            )
            return
        if any(word in lowered for word in ("empty", "cleared")):
            expect(self.stable_locator(action)).to_have_value("")
            return
        if "checked" in lowered or "completed" in lowered:
            try:
                expect(self.stable_locator(action)).to_be_checked()
                return
            except Exception:
                pass
        if any(word in lowered for word in ("not visible", "removed", "disappear")) and quoted:
            expect(self.page.get_by_text(quoted[-1], exact=False).first).not_to_be_visible()
            return
        if quoted and any(word in lowered for word in ("visible", "displayed", "shown", "appears", "contains")):
            for text in quoted:
                expect(self.page.get_by_text(text, exact=False).first).to_be_visible()
            return
        if any(word in lowered for word in ("focus", "focused")):
            expect(self.stable_locator(action)).to_be_focused()
            return
        if any(word in lowered for word in ("enabled", "ready")):
            expect(self.stable_locator(action)).to_be_enabled()
            return
        raise AssertionError(f"Expected outcome is not grounded in a discoverable UI assertion: {{expected_result}}")


def test_{_safe_name(test_case["test_case_id"]).replace("-", "_")}(page: Page):
    app = {class_name}(page)
    page.goto(TARGET_URL, wait_until="domcontentloaded")
    for step in STEPS:
        app.perform(step["action"], step.get("expected_result", ""))
        app.assert_expected(step.get("expected_result", ""), step["action"])
'''


def _ui_python_source(
    script_id: str,
    base_url: str,
    page_url: str,
    elements: list[dict[str, Any]],
) -> str:
    """Render a deterministic script using only the crawled UI catalogue."""
    compact = [
        {
            key: item.get(key)
            for key in (
                "role", "name", "label", "test_id", "tag", "input_type",
                "placeholder", "visible_text",
            )
            if item.get(key) not in (None, "")
        }
        for item in elements[:100]
    ]
    return f'''"""UI-derived Playwright script. No requirement artifacts were used."""
import re
from playwright.sync_api import Page, expect

BASE_URL = {base_url!r}
PAGE_URL = {page_url!r}
UI_ELEMENTS = {pformat(compact, width=100, sort_dicts=False)}


def locator_for(page: Page, element: dict):
    if element.get("test_id"):
        return page.get_by_test_id(element["test_id"]).first
    if element.get("label"):
        return page.get_by_label(element["label"], exact=True).first
    if element.get("role") and element.get("name"):
        return page.get_by_role(element["role"], name=element["name"], exact=True).first
    if element.get("placeholder"):
        return page.get_by_placeholder(element["placeholder"], exact=True).first
    text = element.get("visible_text") or element.get("name")
    if text:
        return page.get_by_text(re.compile(re.escape(str(text)[:120]), re.I), exact=False).first
    return page.locator(element.get("tag") or "body").first


def test_{_safe_name(script_id).replace("-", "_")}(page: Page):
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    expect(page.locator("body")).to_be_visible()
    for element in UI_ELEMENTS:
        locator = locator_for(page, element)
        if locator.count():
            expect(locator).to_be_visible()
'''


class AutomationService:
    def __init__(self) -> None:
        self._generations: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, ExecutionReport] = {}
        self._comparisons: dict[str, TraceabilityReport] = {}
        self.skyvern = SkyvernAdapter()
        self.failure_analysis = FailureAnalysisService()

    @property
    def artifact_root(self) -> Path:
        root = Path(settings.automation_artifacts_path).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

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

    @staticmethod
    async def _access_gate(page: Any) -> tuple[str, str | None]:
        title = (await page.title()).casefold()
        current_url = page.url.casefold()
        try:
            body = (await page.locator("body").inner_text(timeout=3000)).casefold()[:12000]
        except Exception:
            body = ""
        content = f"{title}\n{current_url}\n{body}"
        if any(marker in content for marker in (
            "performing security verification", "verify you are human",
            "checking your browser", "just a moment", "__cf_chl",
            "ray id:", "performance and security by cloudflare",
        )):
            return "bot_challenge_blocked", "Bot/security verification page detected"
        if any(marker in content for marker in ("g-recaptcha", "hcaptcha", "cf-turnstile", "captcha")):
            return "captcha_blocked", "CAPTCHA challenge detected"
        if any(marker in content for marker in (
            "access denied", "request blocked", "forbidden",
            "you don't have permission to access",
        )):
            return "access_denied", "Access-denied page detected"
        if await page.locator('input[type="password"]').count() and any(
            marker in content for marker in ("sign in", "log in", "login", "authentication")
        ):
            return "authentication_required", "Authentication page detected"
        return "ready", None

    async def _discover(
        self, url: str
    ) -> tuple[str | None, list[DiscoveredElement], dict[str, Any]]:
        if settings.app_mock_mode:
            return "Mock Application", [
                DiscoveredElement(tag="button", role="button", name="Mock submit"),
                DiscoveredElement(tag="input", label="Mock input", input_type="text"),
            ], {
                "access_status": "ready", "crawl_status": "completed",
                "pages_discovered": 1, "inaccessible_pages": [], "crawl_warnings": [],
            }
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                origin = urlsplit(url)
                pending = [url]
                visited: set[str] = set()
                raw: list[dict[str, Any]] = []
                inaccessible: list[dict[str, str]] = []
                title = None
                while pending and len(visited) < 50:
                    page_url = pending.pop(0)
                    if page_url in visited:
                        continue
                    try:
                        await page.goto(page_url, wait_until="domcontentloaded", timeout=int(settings.automation_navigation_timeout_seconds * 1000))
                    except Exception as exc:
                        inaccessible.append({"url": page_url, "reason": f"Navigation failed: {type(exc).__name__}"})
                        continue
                    access_status, blocked_reason = await self._access_gate(page)
                    if access_status != "ready":
                        if not visited:
                            raise AutomationError(
                                f"{blocked_reason}. The actual application could not be crawled "
                                f"(access status: {access_status}). Configure an authorized test "
                                "session, allowlisted automation runner, or staging security rule."
                            )
                        inaccessible.append({"url": page_url, "reason": blocked_reason or access_status})
                        continue
                    visited.add(page.url)
                    title = title or await page.title()
                    # Dismiss non-destructive consent overlays before discovery.  This is
                    # deliberately conservative: only buttons with common consent labels
                    # are clicked, and failures are ignored so discovery remains read-only.
                    try:
                        await page.get_by_role(
                            "button",
                            name=re.compile(
                                r"^(accept|accept all|allow all|agree|i agree|got it|close)$",
                                re.I,
                            ),
                        ).first.click(timeout=600)
                    except Exception:
                        pass
                    # Trigger ordinary lazy rendering before taking the DOM
                    # snapshot. Multiple bounded passes cover infinite-scroll pages while
                    # preventing an unbounded crawl.
                    try:
                        await page.evaluate("""async () => {
                          const pause = ms => new Promise(r => setTimeout(r, ms));
                          let stable = 0; let previous = 0;
                          for (let pass = 0; pass < 8 && stable < 2; pass++) {
                            const limit = Math.min(document.documentElement.scrollHeight, 30000);
                            for (let y = 0; y <= limit; y += 700) {
                              window.scrollTo(0, y); await pause(80);
                            }
                            await pause(150);
                            const current = document.documentElement.scrollHeight;
                            stable = current === previous ? stable + 1 : 0;
                            previous = current;
                          }
                          window.scrollTo(0, 0);
                        }""")
                    except Exception:
                        pass
                    discovered: list[dict[str, Any]] = []
                    for frame in page.frames:
                        try:
                            frame_items = await frame.locator(
                                "button,input,select,textarea,a[href],label,form,table,menu,"
                                "dialog,[role],[data-testid],[data-test],[data-cy],"
                                "[contenteditable='true'],[tabindex],[onclick]"
                            ).evaluate_all(
                        """els => els.slice(0, 500).filter(el => {
                          const style = getComputedStyle(el); const box = el.getBoundingClientRect();
                          return style.visibility !== 'hidden' && style.display !== 'none' && box.width > 0 && box.height > 0;
                        }).map(el => ({
                          role: el.getAttribute('role') || (el.tagName.toLowerCase() === 'input'
                            ? ({checkbox:'checkbox',radio:'radio',number:'spinbutton',submit:'button',button:'button'}[el.type] || 'textbox')
                            : ({button:'button',a:'link',select:'combobox',textarea:'textbox'}[el.tagName.toLowerCase()] ?? null)),
                          name: el.getAttribute('aria-label') || el.labels?.[0]?.innerText?.trim()
                            || el.getAttribute('name') || el.innerText?.trim() || null,
                          element_id: el.id || null, html_name: el.getAttribute('name'),
                          aria_label: el.getAttribute('aria-label'),
                          aria_labelledby: el.getAttribute('aria-labelledby'),
                          label: el.labels?.[0]?.innerText?.trim() || null,
                          placeholder: el.getAttribute('placeholder'),
                          test_id: el.getAttribute('data-testid') || el.getAttribute('data-test')
                            || el.getAttribute('data-cy'),
                          visible_text: el.innerText?.trim() || null, href: el.href || null,
                          tag: el.tagName.toLowerCase(), input_type: el.getAttribute('type'),
                          checked: typeof el.checked === 'boolean' ? el.checked : null,
                          attributes: Object.fromEntries([...el.attributes]
                            .filter(a => a.name.startsWith('data-')).map(a => [a.name, a.value])),
                          parent_tag: el.parentElement?.tagName?.toLowerCase() || null,
                          parent_id: el.parentElement?.id || null,
                          parent_role: el.parentElement?.getAttribute('role') || null,
                          css_path: el.id ? `#${CSS.escape(el.id)}` : null,
                          options: el.tagName.toLowerCase() === 'select' ? [...el.options].map(o => ({label:o.text.trim(), value:o.value})) : []
                        }))"""
                            )
                            for item in frame_items:
                                item["frame_url"] = frame.url
                                attrs = item.setdefault("attributes", {})
                                for key in ("parent_tag", "parent_id", "parent_role"):
                                    if item.get(key):
                                        attrs[key] = str(item.pop(key))
                            discovered.extend(frame_items)
                        except Exception as frame_error:
                            inaccessible.append({
                                "url": frame.url or page.url,
                                "reason": f"Frame inspection failed: {type(frame_error).__name__}",
                            })
                    # Playwright locators pierce open shadow roots, but a frame-level
                    # locator query does not expose the host relationship. Traverse open
                    # roots explicitly and add the same stable metadata for those nodes.
                    try:
                        shadow_items = await page.evaluate("""() => {
                          const selector = "button,input,select,textarea,a[href],label,form,table,menu,dialog,[role],[data-testid],[data-test],[data-cy],[contenteditable='true'],[tabindex],[onclick]";
                          const out = []; const seen = new Set();
                          const text = el => (el.innerText || el.getAttribute('aria-label') || el.getAttribute('name') || '').trim() || null;
                          const walk = (root, host = null) => {
                            if (!root || !root.querySelectorAll) return;
                            root.querySelectorAll(selector).forEach(el => {
                              if (seen.has(el)) return; seen.add(el);
                              const r = el.getAttribute('role') || (el.tagName.toLowerCase() === 'button' ? 'button' : null);
                              out.push({tag: el.tagName.toLowerCase(), role: r, name: text(el), element_id: el.id || null,
                                html_name: el.getAttribute('name'), aria_label: el.getAttribute('aria-label'),
                                aria_labelledby: el.getAttribute('aria-labelledby'), label: el.labels?.[0]?.innerText?.trim() || null,
                                placeholder: el.getAttribute('placeholder'), test_id: el.getAttribute('data-testid') || el.getAttribute('data-test') || el.getAttribute('data-cy'),
                                visible_text: el.innerText?.trim() || null, href: el.href || null, input_type: el.getAttribute('type'),
                                frame_url: location.href, css_path: el.id ? '#' + CSS.escape(el.id) : null,
                                attributes: {shadow_host: host?.tagName?.toLowerCase() || ''}});
                              if (el.shadowRoot) walk(el.shadowRoot, el);
                            });
                            root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) walk(el.shadowRoot, el); });
                          };
                          walk(document); return out;
                        }""")
                        for item in shadow_items:
                            item["page_url"] = page.url
                        discovered.extend(shadow_items)
                    except Exception as shadow_error:
                        inaccessible.append({"url": page.url, "reason": f"Shadow DOM inspection failed: {type(shadow_error).__name__}"})
                    for item in discovered:
                        item["page_url"] = page.url
                    raw.extend(discovered)
                    for item in discovered:
                        href = item.get("href")
                        parsed = urlsplit(href) if href else None
                        if parsed and parsed.scheme in {"http", "https"} and parsed.netloc == origin.netloc:
                            clean_href = href.split("#", 1)[0]
                            if clean_href not in visited and clean_href not in pending:
                                pending.append(clean_href)
                await browser.close()
            elements = [DiscoveredElement.model_validate(item) for item in raw]
            logger.info(
                "DOM discovery complete url=%s pages_visited=%d elements_found=%d",
                url, len(visited), len(elements),
            )
            return title, elements, {
                "access_status": "ready",
                "crawl_status": "partial" if inaccessible or pending else "completed",
                "pages_discovered": len(visited),
                "inaccessible_pages": inaccessible,
                "crawl_warnings": (
                    ["Crawl stopped at the 50-page safety limit."] if pending else []
                ),
            }
        except AutomationError:
            raise
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
        url = str(request.application_url)
        logger.info("generate() start workflow_id=%s url=%s", request.workflow_id, url)
        script_cache_key = cache.fingerprint(
            "scripts",
            {
                "generator_version": 6,
                "pipeline_version": AUTOMATION_PIPELINE_VERSION,
                "generation_mode": "mapped_ui",
                "application_url": url,
                "test_cases": state.get("test_cases", []),
            },
        )
        cached = await cache.get_json(script_cache_key)
        if cached and cached.get("pipeline_version") != AUTOMATION_PIPELINE_VERSION:
            cached = None
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
                scripts=scripts,
                access_status=cached.get("access_status", "ready"),
                crawl_status=cached.get("crawl_status", "completed"),
                pages_discovered=cached.get("pages_discovered", 0),
                inaccessible_pages=cached.get("inaccessible_pages", []),
                crawl_warnings=cached.get("crawl_warnings", []),
            )
            self._generations[generation_id] = {
                "response": response,
                "workflow": state,
                "directory": directory,
                "learned_locators": {},
                "execution_cases": cached.get("execution_cases", []),
                "pipeline_version": AUTOMATION_PIPELINE_VERSION,
            }
            await self._cache_generation(generation_id)
            return response
        logger.info("Validating URL url=%s", url)
        await self._validate_url(url)
        logger.info("Starting DOM discovery url=%s", url)
        discovery = await self._discover(url)
        if len(discovery) == 2:
            title, elements = discovery
            crawl_summary = {
                "access_status": "ready", "crawl_status": "completed",
                "pages_discovered": len({item.page_url or url for item in elements}),
                "inaccessible_pages": [], "crawl_warnings": [],
            }
        else:
            title, elements, crawl_summary = discovery
        logger.info(
            "Discovery complete: %d elements found. Building UI-derived scripts.",
            len(elements),
        )
        generation_id = f"gen-{uuid.uuid4()}"
        directory = self.artifact_root / generation_id
        directory.mkdir(parents=True, exist_ok=False)
        element_dicts = [element.model_dump(mode="json") for element in elements]
        ui_graph = build_ui_graph(element_dicts, url)
        planned_cases = _plan_test_prerequisites(state.get("test_cases", []))
        scenarios = {
            str(item.get("scenario_id")): item for item in state.get("scenarios", [])
        }
        scripts: list[GeneratedScript] = []
        for index, test_case in enumerate(planned_cases, start=1):
            target_url = _best_page_url(test_case, url, element_dicts)
            page_elements = [
                element for element in element_dicts
                if str(element.get("page_url") or url) == target_url
            ] or element_dicts
            script_id = f"pw-{index:03d}-{_safe_name(str(test_case['test_case_id']))}"
            path = directory / f"{script_id}{SCRIPT_ARTIFACT_SUFFIX}"
            try:
                source = _python_source(
                    test_case,
                    url,
                    page_elements,
                    target_url=target_url,
                )
                _validate_generated_source(source)
            except (SyntaxError, ValueError) as source_err:
                logger.warning(
                    "Script skipped – source validation failed "
                    "script_id=%s error=%s: %s",
                    script_id, type(source_err).__name__, source_err,
                )
                continue
            path.write_text(source, encoding="utf-8")
            scenario = scenarios.get(str(test_case.get("scenario_id")), {})
            scripts.append(
                GeneratedScript(
                    script_id=script_id,
                    workflow_id=request.workflow_id,
                    test_case_id=str(test_case["test_case_id"]),
                    scenario_id=str(test_case.get("scenario_id") or "unmapped"),
                    name=str(test_case.get("title") or script_id),
                    application_url=url,
                    source=source,
                    download_path=f"/api/v1/automation/scripts/{generation_id}/{script_id}/download",
                    requirement_ids=test_case.get("requirement_ids", []),
                    user_story_ids=scenario.get("user_story_ids", []),
                )
            )
        logger.info(
            "generate() complete: %d mapped scripts built. generation_id=%s",
            len(scripts), generation_id,
        )
        if not scripts:
            raise AutomationError("No valid UI-derived scripts could be generated.")
        response = ScriptGenerationResponse(
            generation_id=generation_id,
            application_url=url,
            reachable=True,
            page_title=title,
            discovered_elements=elements,
            scripts=scripts,
            **crawl_summary,
        )
        self._generations[generation_id] = {
            "response": response,
            "workflow": state,
            "directory": directory,
            "learned_locators": {},
            "execution_cases": planned_cases,
            "pipeline_version": AUTOMATION_PIPELINE_VERSION,
            "ui_knowledge_graph": ui_graph,
        }
        await self._cache_generation(generation_id)
        await cache.set_json(
            script_cache_key,
            {
                "page_title": title,
                "discovered_elements": [item.model_dump(mode="json") for item in elements],
                "scripts": [item.model_dump(mode="json") for item in scripts],
                "execution_cases": planned_cases,
                "pipeline_version": AUTOMATION_PIPELINE_VERSION,
                "ui_knowledge_graph": ui_graph,
                **crawl_summary,
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
            "execution_cases": generation.get("execution_cases", []),
            "pipeline_version": generation.get("pipeline_version", AUTOMATION_PIPELINE_VERSION),
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
            generation = self._generations[generation_id]
            if generation.get("pipeline_version") != AUTOMATION_PIPELINE_VERSION:
                self._generations.pop(generation_id, None)
                raise AutomationNotFound(
                    "This generation belongs to an older automation pipeline. "
                    "Generate the scripts again before execution."
                )
            return generation
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
                        "execution_cases": stored.get("execution_cases", []),
                        "pipeline_version": stored.get("pipeline_version"),
                    }
                    if generation["pipeline_version"] != AUTOMATION_PIPELINE_VERSION:
                        raise AutomationNotFound(
                            "This generation belongs to an older automation pipeline. "
                            "Generate the scripts again before execution."
                        )
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
                "execution_cases": cached.get("execution_cases", []),
                "pipeline_version": cached.get("pipeline_version"),
            }
            if generation["pipeline_version"] != AUTOMATION_PIPELINE_VERSION:
                raise AutomationNotFound(
                    "This generation belongs to an older automation pipeline. "
                    "Generate the scripts again before execution."
                )
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
                    "name", "label", "test_id", "element_id", "html_name",
                    "aria_label", "placeholder", "visible_text", "href",
                )
            )
            score = len(phrase_words & _meaningful_words(identity))
            if score:
                ranked.append((score, element))
        candidates = []
        for _, element in sorted(ranked, key=lambda item: item[0], reverse=True):
            scope = page
            frame_url = element.get("frame_url")
            if frame_url and frame_url != page.url:
                matching_frame = next(
                    (frame for frame in page.frames if frame.url == frame_url), None
                )
                if matching_frame is not None:
                    scope = matching_frame
            if element.get("test_id"):
                candidates.append(scope.get_by_test_id(element["test_id"]))
            if element.get("element_id"):
                candidates.append(
                    scope.locator("[id=" + json.dumps(str(element["element_id"])) + "]")
                )
            if element.get("aria_label"):
                candidates.append(
                    scope.locator(
                        "[aria-label=" + json.dumps(str(element["aria_label"])) + "]"
                    )
                )
            if element.get("role") and element.get("name"):
                candidates.append(
                    scope.get_by_role(element["role"], name=element["name"], exact=True)
                )
            if element.get("label"):
                candidates.append(scope.get_by_label(element["label"], exact=True))
            if element.get("html_name"):
                candidates.append(
                    scope.locator("[name=" + json.dumps(str(element["html_name"])) + "]")
                )
            if element.get("placeholder"):
                candidates.append(
                    scope.get_by_placeholder(element["placeholder"], exact=True)
                )
            if element.get("visible_text"):
                candidates.append(
                    scope.get_by_text(element["visible_text"], exact=False)
                )
            if element.get("css_path"):
                candidates.append(scope.locator(element["css_path"]))
            if element.get("xpath"):
                candidates.append(scope.locator("xpath=" + str(element["xpath"])))
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
        expected_result: str = "",
        test_data: dict[str, Any] | None = None,
        seed: str = "test",
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
                        await page.wait_for_load_state("domcontentloaded")
                        return description
                    except Exception as exc:
                        last_error = exc
                if last_error:
                    raise last_error
            except LookupError:
                return f"page | {page.url}"
        values = re.findall(r"['\"]([^'\"]+)['\"]", action)
        desired = values[-1] if values else _explicit_input_value(
            action, expected_result, test_data, seed
        )
        key_match = re.search(
            r"\bpress(?:\s+the)?\s+(enter|return|tab|escape|space)(?:\s+key)?\b",
            lowered,
        )
        if key_match:
            key = {"return": "Enter", "space": "Space"}.get(
                key_match.group(1), key_match.group(1).title()
            )
            await page.keyboard.press(key)
            return f"keyboard | {key}"
        roles: tuple[str, ...]
        interactive_tokens = (
            "click", "press", "select", "choose", "check", "uncheck",
            "enter", "type", "fill", "radio", "focus",
        )
        if not any(token in lowered for token in interactive_tokens):
            # Passive / observation step — no element click/fill required
            return "passive | page state"
        if any(token in lowered for token in ("select", "choose")):
            roles = ("combobox", "radio")
        elif any(token in lowered for token in ("check", "uncheck", "radio")):
            roles = ("checkbox", "radio")
        elif any(token in lowered for token in ("click", "press")):
            roles = ("button", "link")
        elif "focus" in lowered:
            roles = ("textbox", "spinbutton", "combobox", "button", "link")
        elif any(token in lowered for token in ("enter", "type", "fill")):
            roles = ("textbox", "spinbutton")
        else:
            roles = ("button", "link")

        locators: list[tuple[Any, str]] = []
        # Dynamic row/card controls often have a generic accessible name
        # ("Toggle", "Remove") while the instruction names the surrounding
        # item. Resolve the named item first, then search its nearest semantic
        # container. This is framework- and application-independent.
        if values and any(
            token in lowered for token in ("click", "check", "uncheck", "radio")
        ):
            try:
                named_item = page.get_by_text(values[0], exact=False).first
                if await named_item.count():
                    container = named_item.locator(
                        "xpath=ancestor-or-self::*[self::li or self::tr or self::article or self::section or self::form or self::div][1]"
                    )
                    for role in roles:
                        contextual = container.get_by_role(role)
                        if await contextual.count() and await contextual.first.is_visible():
                            locators.append((
                                contextual.first,
                                f"contextual {role} near {values[0]!r}",
                            ))
            except Exception:
                pass
        try:
            locators.extend(
                await self._resolve_locators(
                    page, phrase, roles, discovered_elements
                )
            )
        except LookupError:
            if not locators:
                raise
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
                elif "focus" in lowered:
                    await locator.focus()
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
        """Wait briefly for DOM readiness without requiring an idle network.

        Modern applications commonly keep analytics, sockets, and polling
        requests open, so networkidle is not a reliable readiness signal.
        """
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        try:
            await page.locator("body").wait_for(state="visible", timeout=5000)
            await page.wait_for_timeout(250)
        except Exception:
            pass
        # Do not require network-idle (SPAs often keep sockets open), but give
        # pending route/render work a bounded opportunity to settle.
        try:
            await page.wait_for_function(
                "() => !document.querySelector('[aria-busy=\"true\"], .loading, .spinner')",
                timeout=1500,
            )
        except Exception:
            pass

    async def _perform_with_retries(
        self,
        page: Any,
        action: str,
        page_elements: list[dict[str, Any]],
        expected: str,
        test_data: dict[str, Any],
        test_case_id: str,
        max_retries: int = 2,
    ) -> tuple[Any, int]:
        """Execute one deterministic action with bounded synchronization retries.

        Retries only repeat the same business action; they never alter the test
        case or automation intent. This handles detached locators and SPA
        transitions before recovery services are considered.
        """
        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                await self._wait_for_page_stable(page)
                return await self._perform(
                    page, action, page_elements, expected, test_data, test_case_id
                ), attempt
            except Exception as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
                await self._dismiss_overlays(page)
                await page.wait_for_timeout(150 * (attempt + 1))
        assert last_error is not None
        raise last_error

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

    async def _assert_expected(
        self,
        page: Any,
        expected_result: str,
        action: str = "",
        test_data: dict[str, Any] | None = None,
        seed: str = "test",
    ) -> None:
        lowered = expected_result.lower()
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", expected_result)
        # Input-value outcomes must be checked as values, not as visible text.
        if any(word in lowered for word in ("entered", "input", "field", "value")) and (
            any(word in lowered for word in ("contains", "display", "entered", "value"))
        ):
            try:
                locators = await self._resolve_locators(
                    page, self._locator_phrase(action), ("textbox", "spinbutton", "combobox")
                )
                expected_value = _explicit_input_value(
                    action, expected_result, test_data, seed
                )
                actual = await locators[0][0].input_value()
                if actual != expected_value:
                    raise AssertionError(
                        f"Expected field value {expected_value!r}, received {actual!r}"
                    )
                return
            except LookupError:
                pass
        if quoted and any(
            phrase in lowered for phrase in ("not visible", "removed", "disappear")
        ):
            await page.get_by_text(quoted[-1], exact=False).first.wait_for(
                state="hidden",
                timeout=int(settings.automation_action_timeout_seconds * 1000),
            )
            return
        if any(word in lowered for word in ("empty", "cleared")):
            locators = await self._resolve_locators(
                page, self._locator_phrase(action), ("textbox", "spinbutton")
            )
            actual = await locators[0][0].input_value()
            if actual:
                raise AssertionError(f"Expected an empty field, received {actual!r}")
            return
        if any(word in lowered for word in ("checked", "completed")):
            if quoted:
                try:
                    item = page.get_by_text(quoted[-1], exact=False).first
                    container = item.locator(
                        "xpath=ancestor-or-self::*[self::li or self::tr or self::div][1]"
                    )
                    checkbox = container.get_by_role("checkbox").first
                    if await checkbox.count() and await checkbox.is_checked():
                        return
                except Exception:
                    pass
            try:
                locators = await self._resolve_locators(
                    page, self._locator_phrase(action), ("checkbox", "radio")
                )
                if await locators[0][0].is_checked():
                    return
            except LookupError:
                pass
        if quoted and any(
            word in lowered for word in (
                "visible", "displayed", "shown", "appears", "contains", "display"
            )
        ):
            for text in quoted:
                await page.get_by_text(text, exact=False).first.wait_for(
                    state="visible",
                    timeout=int(settings.automation_action_timeout_seconds * 1000),
                )
            return
        if any(word in lowered for word in ("focus", "focused")):
            has_focus = await page.evaluate(
                "() => document.activeElement && document.activeElement !== document.body"
            )
            if not has_focus:
                raise AssertionError("Expected an interactive element to have focus")
            return
        if any(word in lowered for word in ("enabled", "ready")) and action:
            locators = await self._resolve_locators(
                page,
                self._locator_phrase(action),
                ("textbox", "button", "link", "combobox", "checkbox", "radio"),
            )
            if not await locators[0][0].is_enabled():
                raise AssertionError("Expected the target UI element to be enabled")
            return
        raise AssertionError(
            f"Expected outcome is not grounded in a discoverable UI assertion: {expected_result}"
        )

    async def _execute_ui_specs(
        self, request: ExecuteScriptsRequest, generation: dict[str, Any]
    ) -> ExecutionReport:
        from playwright.async_api import async_playwright

        started = time.perf_counter()
        response: ScriptGenerationResponse = generation["response"]
        scripts = {script.script_id: script for script in response.scripts}
        results: list[ScriptExecutionResult] = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            for spec in generation.get("ui_specs", []):
                script = scripts.get(str(spec["script_id"]))
                if not script:
                    continue
                test_started = time.perf_counter()
                context = await browser.new_context()
                page = await context.new_page()
                console_logs: list[str] = []
                network_errors: list[str] = []
                page.on("console", lambda message, logs=console_logs: logs.append(message.text))
                page.on(
                    "requestfailed",
                    lambda failed_request, errors=network_errors: errors.append(
                        f"{failed_request.method} {failed_request.url}"
                    ),
                )
                try:
                    await page.goto(
                        spec["page_url"],
                        wait_until="domcontentloaded",
                        timeout=int(settings.automation_navigation_timeout_seconds * 1000),
                    )
                    access_status, blocked_reason = await self._access_gate(page)
                    if access_status != "ready":
                        raise AutomationAccessBlocked(
                            access_status, blocked_reason or access_status
                        )
                    await page.locator("body").wait_for(state="visible")
                    visible = 0
                    for element in spec.get("elements", [])[:100]:
                        identity = " ".join(
                            str(element.get(key) or "")
                            for key in ("test_id", "label", "name", "placeholder", "visible_text")
                        ).strip()
                        if not identity:
                            continue
                        candidates = self._discovered_locator_candidates(
                            page, identity, [element]
                        )
                        for candidate in candidates:
                            try:
                                if await candidate.count() and await candidate.first.is_visible():
                                    visible += 1
                                    break
                            except Exception:
                                continue
                    results.append(
                        ScriptExecutionResult(
                            script_id=script.script_id,
                            script_name=script.name,
                            test_case_id=script.test_case_id,
                            scenario_id=script.scenario_id,
                            status="passed",
                            duration_seconds=round(time.perf_counter() - test_started, 3),
                            traceability={
                                "generation_basis": "application_ui",
                                "page_url": spec["page_url"],
                                "discovered_elements": len(spec.get("elements", [])),
                                "visible_elements": visible,
                            },
                        )
                    )
                except Exception as exc:
                    blocked = isinstance(exc, AutomationAccessBlocked)
                    results.append(
                        ScriptExecutionResult(
                            script_id=script.script_id,
                            script_name=script.name,
                            test_case_id=script.test_case_id,
                            scenario_id=script.scenario_id,
                            status="blocked" if blocked else "automation_error",
                            duration_seconds=round(time.perf_counter() - test_started, 3),
                            error_message=str(exc),
                            failure=FailureAnalysis(
                                test_case_id=script.test_case_id,
                                failure_reason=str(exc),
                                failure_category=(
                                    "Authentication Required"
                                    if blocked and exc.access_status == "authentication_required"
                                    else "Environment Blocked"
                                    if blocked
                                    else "Automation Error"
                                ),
                                page_url=str(spec.get("page_url")),
                                console_logs=console_logs,
                                network_errors=network_errors,
                            ),
                            traceability={"generation_basis": "application_ui"},
                        )
                    )
                finally:
                    await context.close()
            await browser.close()
        return self._save_report(
            request,
            results,
            time.perf_counter() - started,
            generation["directory"],
            generation,
        )

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

        if generation.get("ui_specs"):
            return await self._execute_ui_specs(request, generation)

        started = time.perf_counter()
        results: list[ScriptExecutionResult] = []
        state = generation["workflow"]
        execution_cases = generation.get("execution_cases") or state.get("test_cases", [])
        cases = {str(item["test_case_id"]): item for item in execution_cases}
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
                failed_step = None
                expected = None
                element = None
                skyvern_attempted = False
                skyvern_succeeded = False
                recovery_attempts = 0
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
                        # ---- Wait for page to settle before each step (req 4) ----
                        await self._wait_for_page_stable(page)

                        failure_category = "Locator Failure"
                        try:
                            page_elements = [
                                el for el in disc_dicts
                                if not el.get("page_url") or el.get("page_url") == page.url
                            ]
                            element, action_attempts = await self._perform_with_retries(
                                page,
                                action,
                                page_elements,
                                expected or "",
                                test_case.get("test_data", {}),
                                str(test_case["test_case_id"]),
                            )
                            recovery_attempts += action_attempts
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
                                recovery_attempts += int(getattr(recovery, "attempts", 0) or 0)
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
                        await self._assert_expected(
                            page,
                            expected or "",
                            action,
                            test_case.get("test_data", {}),
                            str(test_case["test_case_id"]),
                        )

                    results.append(
                        ScriptExecutionResult(
                            script_id=script.script_id,
                            script_name=script.name,
                            test_case_id=script.test_case_id,
                            scenario_id=script.scenario_id,
                            status="passed",
                            duration_seconds=round(time.perf_counter() - test_started, 3),
                            traceability={
                                **self._traceability(script),
                                "recovery_attempts": recovery_attempts,
                            },
                        )
                    )
                    # Stop trace cleanly on pass (no need to save)
                    try:
                        await context.tracing.stop()
                    except Exception:
                        pass

                except Exception as exc:
                    # Central deterministic classification.  Keep the legacy
                    # schema labels while exposing the recommendation in the
                    # execution log; no LLM is involved in this path.
                    diagnostic = self.failure_analysis.classify(
                        exc,
                        network_errors=network_errors,
                        page_url=page.url,
                    )
                    failure_category = diagnostic.category

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
                        failure_reason=(
                            f"{type(exc).__name__}: {diagnostic.reason}; "
                            f"recommended_action={diagnostic.recommended_action}"
                        ),
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
                        recovery_attempts=recovery_attempts,
                        repaired_locator=(element if recovery_attempts and element else None),
                        recommended_action=diagnostic.recommended_action,
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
        blocked = sum(result.status == "blocked" for result in results)
        automation_errors = sum(result.status == "automation_error" for result in results)
        workflow = generation.get("workflow", {})
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
            blocked_scripts=blocked,
            automation_error_scripts=automation_errors,
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
                "blocked": blocked,
                "automation_errors": automation_errors,
                "rejected": rejected,
                "pass_rate": round((passed / overall_total * 100) if overall_total else 0, 2),
            },
        )
        self._reports[execution_id] = report
        path = directory / f"{execution_id}.json"
        path.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
        reports_directory = self.artifact_root / "reports"
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

    async def compare(self, execution_id: str, workflow_id: Any) -> TraceabilityReport:
        execution = self.report(execution_id)
        generation = await self.generation(execution.generation_id)
        workflow = generation.get("workflow", {})
        if str(workflow.get("workflow_id")) != str(workflow_id):
            raise AutomationError("The execution and workflow do not belong together.")

        executed_ids = {
            result.script_id for result in execution.results
            if result.status in {"passed", "failed"}
        }
        specs = [
            spec for spec in generation.get("ui_specs", [])
            if str(spec.get("script_id")) in executed_ids
        ]
        script_tokens: dict[str, set[str]] = {}
        script_evidence: dict[str, str] = {}
        for spec in specs:
            evidence = " ".join(
                [
                    str(spec.get("page_url") or ""),
                    *[
                        " ".join(
                            str(element.get(key) or "")
                            for key in (
                                "role", "name", "label", "placeholder", "test_id",
                                "visible_text", "href", "tag", "input_type",
                            )
                        )
                        for element in spec.get("elements", [])
                    ],
                ]
            )
            script_id = str(spec["script_id"])
            script_tokens[script_id] = _meaningful_words(evidence)
            script_evidence[script_id] = str(spec.get("page_url") or "")

        artifacts: list[tuple[str, str, str, str]] = []
        for scenario in workflow.get("scenarios", []):
            artifacts.append(
                (
                    "scenario",
                    str(scenario.get("scenario_id")),
                    str(scenario.get("title") or scenario.get("scenario_id")),
                    json.dumps(scenario, default=str),
                )
            )
        for test_case in workflow.get("test_cases", []):
            artifacts.append(
                (
                    "test_case",
                    str(test_case.get("test_case_id")),
                    str(test_case.get("title") or test_case.get("test_case_id")),
                    json.dumps(test_case, default=str),
                )
            )

        items: list[TraceabilityItem] = []
        matched_ui_ids: set[str] = set()
        for artifact_type, artifact_id, title, text in artifacts:
            artifact_tokens = _meaningful_words(text)
            ranked = sorted(
                (
                    (len(artifact_tokens & tokens), script_id)
                    for script_id, tokens in script_tokens.items()
                ),
                reverse=True,
            )
            matches = [(score, script_id) for score, script_id in ranked if score]
            found = set().union(
                *(artifact_tokens & script_tokens[script_id] for _, script_id in matches)
            ) if matches else set()
            denominator = max(1, min(len(artifact_tokens), 12))
            coverage = round(min(100.0, len(found) / denominator * 100), 2)
            status = "covered" if coverage >= 60 else "partial" if coverage >= 25 else "missing"
            matched_ids = [script_id for _, script_id in matches[:5]]
            matched_ui_ids.update(matched_ids)
            items.append(
                TraceabilityItem(
                    artifact_type=artifact_type,
                    artifact_id=artifact_id,
                    title=title,
                    status=status,
                    coverage_percentage=coverage,
                    matched_script_ids=matched_ids,
                    matched_evidence=[
                        f"{script_id}: {script_evidence[script_id]}"
                        for script_id in matched_ids
                    ],
                    gaps=sorted(artifact_tokens - found)[:12],
                )
            )

        covered = sum(item.status == "covered" for item in items)
        partial = sum(item.status == "partial" for item in items)
        missing = sum(item.status == "missing" for item in items)
        overall = round(
            sum(item.coverage_percentage for item in items) / len(items), 2
        ) if items else 0
        comparison = TraceabilityReport(
            comparison_id=f"cmp-{uuid.uuid4()}",
            execution_id=execution_id,
            generation_id=execution.generation_id,
            workflow_id=workflow_id,
            total_scenarios=len(workflow.get("scenarios", [])),
            total_test_cases=len(workflow.get("test_cases", [])),
            covered=covered,
            partial=partial,
            missing=missing,
            overall_coverage_percentage=overall,
            items=items,
            uncovered_ui_scripts=[
                {
                    "script_id": str(spec["script_id"]),
                    "page_url": str(spec.get("page_url") or ""),
                    "reason": "Executed UI coverage has no matching requirement artifact.",
                }
                for spec in specs
                if str(spec["script_id"]) not in matched_ui_ids
            ],
            summary=(
                f"{covered} covered, {partial} partially covered, and {missing} missing "
                f"across {len(items)} requirement artifacts."
            ),
        )
        self._comparisons[comparison.comparison_id] = comparison
        reports_directory = self.artifact_root / "reports"
        reports_directory.mkdir(parents=True, exist_ok=True)
        (reports_directory / f"{comparison.comparison_id}.json").write_text(
            json.dumps(comparison.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        return comparison

    async def health(self, *, _dedicated_loop: bool = False) -> AutomationHealth:
        identity = {
            "pipeline_version": AUTOMATION_PIPELINE_VERSION,
            "process_id": str(os.getpid()),
            "codebase": str(Path(__file__).resolve().parents[3]),
        }
        if settings.app_mock_mode:
            return AutomationHealth(
                status="healthy",
                playwright_available=True,
                browser_available=True,
                skyvern_enabled=False,
                skyvern_api_reachable=None,
                skyvern_configuration_valid=True,
                details={"mode": "mock", **identity},
            )
        if sys.platform == "win32" and not _dedicated_loop:
            return await _on_playwright_loop(
                lambda: self.health(_dedicated_loop=True)
            )
        playwright_available = False
        browser_available = False
        details = dict(identity)
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
