from __future__ import annotations

import asyncio
import ast
import hashlib
import io
import json
import logging
import re
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from pprint import pformat
from threading import Event
from typing import Any, Awaitable, Callable, TypeVar
from urllib.parse import parse_qsl, urlencode, urlsplit

import httpx

from app.core.config import settings
from app.core.exceptions import AppError
from app.schemas.automation_schema import (
    AutomationHealth,
    CrawlAnalysisResponse,
    CrawlApplicationRequest,
    CrawlAndGenerateRequest,
    CrawlGenerationResponse,
    CrawlJobResponse,
    DiscoveredElement,
    AutomationRecommendation,
    DeveloperImplementationPlan,
    ExecuteScriptsRequest,
    ExecutionJobResponse,
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
    TraceabilityComparisonReport,
    WorkflowCrawlJobResponse,
)
from app.services.seacrawl_service import SeacrawlAdapter
from app.services.cache_service import cache
from app.services.workflow_service import workflow_service
from tests import config as playwright_test_config

R = TypeVar("R")
logger = logging.getLogger(__name__)
SCRIPT_ARTIFACT_SUFFIX = ".pwscript"


def _coverage_status(percentage: float, missing_threshold: float, covered_threshold: float) -> str:
    """Classify a percentage using inclusive partial-coverage boundaries."""
    if missing_threshold > covered_threshold:
        raise ValueError("Missing coverage threshold must not exceed covered threshold")
    if percentage < missing_threshold:
        return "missing"
    if percentage <= covered_threshold:
        return "partial"
    return "covered"


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


class InvalidGeneratedStepError(ValueError):
    """The generated step describes an observation but no executable action."""


class PlaywrightAuthenticationError(RuntimeError):
    """Authentication was required but could not be completed or verified."""


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")[:80] or "test"


def _meaningful_words(value: str) -> set[str]:
    ignored = {"a", "an", "and", "the", "to", "with", "using", "verify", "test", "user"}
    return {
        word.lower() for word in re.findall(r"[A-Za-z0-9]+", value)
        if len(word) > 1 and word.lower() not in ignored
    }


def _best_page_url(test_case: dict[str, Any], base_url: str, elements: list[dict[str, Any]]) -> str:
    page_url, _, _ = _select_ac_page_url(test_case, {}, base_url, elements)
    return page_url or base_url


def _select_ac_page_url(
    test_case: dict[str, Any],
    scenario: dict[str, Any],
    base_url: str,
    elements: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]], bool]:
    """Select target page_url for a test case based on exact AC evidence.

    Returns:
        (page_url, page_elements, has_matching_evidence)
        If no matching AC evidence exists, returns (None, [], False).
    """
    if not elements:
        return base_url, [], True

    # 1. Direct AC / Requirement ID tag match on elements
    tc_ac_ids = set(str(x) for x in (test_case.get("acceptance_criteria_ids") or []))
    sc_ac_ids = set(str(x) for x in (scenario.get("acceptance_criteria_ids") or []))
    all_ac_ids = tc_ac_ids | sc_ac_ids

    tc_req_ids = set(str(x) for x in (test_case.get("requirement_ids") or []))
    sc_req_ids = set(str(x) for x in (scenario.get("requirement_ids") or []))
    all_req_ids = tc_req_ids | sc_req_ids

    if all_ac_ids or all_req_ids:
        matching_pages: dict[str, list[dict[str, Any]]] = {}
        for item in elements:
            item_ac_ids = set(str(x) for x in (item.get("acceptance_criteria_ids") or item.get("ac_ids") or []))
            if item.get("ac_id"):
                item_ac_ids.add(str(item["ac_id"]))
            item_req_ids = set(str(x) for x in (item.get("requirement_ids") or []))
            if item.get("requirement_id"):
                item_req_ids.add(str(item["requirement_id"]))

            if (all_ac_ids & item_ac_ids) or (all_req_ids & item_req_ids):
                p_url = _canonical_page_url(str(item.get("page_url") or base_url))
                matching_pages.setdefault(p_url, []).append(item)

        if matching_pages:
            best_page = max(matching_pages.keys(), key=lambda p: len(matching_pages[p]))
            p_elements = [
                item for item in elements
                if _canonical_page_url(str(item.get("page_url") or base_url)) == best_page
            ]
            return best_page, p_elements, True

    # 2. Match AC / Test Case intent & step actions against candidate pages
    pages = {str(item.get("page_url")) for item in elements if item.get("page_url")}
    if not pages:
        pages = {base_url}

    steps_text = " ".join(str(step.get("action") or "") for step in test_case.get("steps", []))
    full_text = " ".join([
        str(test_case.get("title") or ""),
        str(test_case.get("description") or ""),
        str(scenario.get("title") or ""),
        str(scenario.get("description") or ""),
        steps_text,
    ]).lower()

    intent_words = _meaningful_words(full_text)
    step_words = _meaningful_words(steps_text)

    is_auth_ac = any(
        w in full_text
        for w in ("login", "register", "sign in", "signin", "signup", "sign up", "password reset", "credential")
    )

    page_scores: dict[str, tuple[int, list[dict[str, Any]]]] = {}
    for p_url in pages:
        path = urlsplit(p_url).path.lower()
        is_auth_page = any(x in path for x in ("register", "login", "signin", "sign-in", "signup", "sign-up"))

        # Disqualify auth/register pages for non-auth ACs
        if is_auth_page and not is_auth_ac:
            continue

        p_elements = [
            item for item in elements
            if _canonical_page_url(str(item.get("page_url") or base_url)) == _canonical_page_url(p_url)
        ]
        element_text = " ".join(
            " ".join(str(item.get(k) or "") for k in ("name", "label", "placeholder", "visible_text"))
            for item in p_elements
        )
        elem_words = _meaningful_words(element_text)

        matching_action_words = step_words & elem_words
        matching_intent_words = intent_words & elem_words

        if matching_action_words or len(matching_intent_words) >= 2:
            score = len(matching_action_words) * 3 + len(matching_intent_words)
            page_scores[p_url] = (score, p_elements)

    if page_scores:
        best_url = max(page_scores.keys(), key=lambda p: page_scores[p][0])
        best_elements = page_scores[best_url][1]
        return best_url, best_elements, True

    # Check base_url if non-auth AC
    base_canonical = _canonical_page_url(base_url)
    base_elements = [
        item for item in elements
        if _canonical_page_url(str(item.get("page_url") or base_url)) == base_canonical
    ]
    base_elem_text = " ".join(
        " ".join(str(item.get(k) or "") for k in ("name", "label", "placeholder", "visible_text"))
        for item in base_elements
    )
    base_words = _meaningful_words(base_elem_text)
    if (step_words & base_words or (intent_words & base_words)) and not (is_auth_ac and "register" in base_canonical):
        return base_url, base_elements, True

    # No matching evidence directly associated with AC
    return None, [], False


def _stable_version(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()[:16]


def _application_map(
    base_url: str, title: str | None, elements: list[dict[str, Any]]
) -> dict[str, Any]:
    base_url = _canonical_page_url(base_url)
    pages: dict[str, dict[str, Any]] = {
        base_url: {"url": base_url, "title": title, "elements": []}
    }
    relationships: list[dict[str, str]] = []
    origin = urlsplit(base_url)
    for element in elements:
        page_url = _canonical_page_url(str(element.get("page_url") or base_url))
        element = {**element, "page_url": page_url}
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
        "discovery_engine": "Seacrawl + Playwright" if settings.seacrawl_fallback_enabled else "Playwright",
        "capture_engine": "Playwright",
    }


def _canonical_page_url(value: str) -> str:
    parsed = urlsplit(value)
    meaningful_query_keys = {
        "page", "pagenumber", "category", "search", "q", "query",
        "filter", "sort", "orderby", "view", "tab",
    }
    query = urlencode([
        (key, query_value)
        for key, query_value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() in meaningful_query_keys
    ])
    return (
        f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path or '/'}"
        f"{'?' + query if query else ''}"
    )


_CHALLENGE_MARKERS = {
    "just a moment": "Cloudflare challenge",
    "verify you are human": "human-verification challenge",
    "checking your browser": "browser-verification challenge",
    "captcha": "CAPTCHA challenge",
    "access denied": "access-denied page",
    "request blocked": "access-denied page",
    "sign in to continue": "login wall",
    "authentication required": "login wall",
    "temporarily unavailable": "maintenance page",
    "under maintenance": "maintenance page",
    "please wait while we": "loading/interstitial page",
}


def _challenge_evidence(
    *, title: str, visible_text: str, status_code: int | None, elements: list[dict[str, Any]]
) -> dict[str, Any] | None:
    combined = f"{title}\n{visible_text[:12000]}".lower()
    matched = [
        {"marker": marker, "reason": reason}
        for marker, reason in _CHALLENGE_MARKERS.items()
        if marker in combined
    ]
    suspicious_status = status_code in {401, 403, 407, 429, 503}
    application_controls = sum(
        item.get("tag") in {"input", "select", "textarea", "button"}
        for item in elements
    )
    privacy_only = (
        0 < len(elements) <= 3
        and application_controls == 0
        and all(
            any(token in str(item.get("name") or item.get("visible_text") or "").lower()
                for token in ("privacy", "terms", "cookie"))
            for item in elements
        )
    )
    if not matched and not suspicious_status and not privacy_only:
        return None
    reason = (
        matched[0]["reason"] if matched
        else f"HTTP {status_code} access response" if suspicious_status
        else "interstitial page exposed only privacy/challenge navigation"
    )
    return {
        "reason": reason,
        "http_status": status_code,
        "page_title": title,
        "matched_markers": matched,
        "visible_text_excerpt": visible_text[:1000],
        "element_names": sorted({
            str(item.get("name") or item.get("visible_text"))
            for item in elements if item.get("name") or item.get("visible_text")
        })[:30],
    }


def _crawl_failure_message(report: dict[str, Any]) -> str:
    status = report.get("status", "crawl_incomplete")
    reason = report.get("failure_reason") or "The crawl did not complete."
    corrective = report.get("recommended_corrective_action") or (
        "Open the URL from the same environment, resolve access controls, then retry."
    )
    return (
        f"Script generation stopped because {status}: {reason} "
        f"Blocked URL: {report.get('blocked_url') or '-'}. "
        f"Pages completed: {report.get('pages_completed', 0)}; "
        f"remaining queue: {len(report.get('remaining_crawl_queue', []))}. "
        f"Recommended action: {corrective}"
    )


def _link_skip_reason(href: str, origin_netloc: str) -> str | None:
    parsed = urlsplit(href)
    if parsed.scheme not in {"http", "https"}:
        return "unsupported_link_scheme"
    if parsed.netloc.lower() != origin_netloc.lower():
        return "external_domain"
    lowered = f"{parsed.path} {parsed.query}".lower()
    if re.search(r"logout|log-out|signout|sign-out|delete|remove|unsubscribe", lowered):
        return "destructive_or_session_ending_link"
    if re.search(r"\.(pdf|zip|csv|xlsx?|docx?|png|jpe?g|gif|webp)$", parsed.path.lower()):
        return "download_only_link"
    return None


def _attach_navigation_context(
    start_url: str,
    relationships: list[dict[str, Any]],
    elements: list[dict[str, Any]],
    page_inventory: list[dict[str, Any]] | None = None,
) -> None:
    start = _canonical_page_url(start_url)
    adjacency: dict[str, list[str]] = {}
    parent: dict[str, str | None] = {start: None}
    paths: dict[str, list[str]] = {start: [start]}
    for relationship in relationships:
        source = _canonical_page_url(str(relationship.get("from") or start))
        target = _canonical_page_url(str(relationship.get("to") or source))
        adjacency.setdefault(source, []).append(target)
    queue = [start]
    while queue:
        source = queue.pop(0)
        for target in adjacency.get(source, []):
            if target in paths:
                continue
            parent[target] = source
            paths[target] = [*paths[source], target]
            queue.append(target)
    page_context = {
        _canonical_page_url(str(item.get("final_url") or item.get("url") or start)): item
        for item in (page_inventory or [])
    }
    for element in elements:
        page_url = _canonical_page_url(str(element.get("page_url") or start))
        context = page_context.get(page_url, {})
        element["page_url"] = page_url
        element["parent_page"] = parent.get(page_url)
        element["navigation_path"] = paths.get(
            page_url,
            [start] if page_url == start else [start, page_url],
        )
        element.setdefault("page_title", context.get("title"))
        element.setdefault("dom_snapshot", context.get("dom_snapshot"))
        element.setdefault(
            "application_state", context.get("application_state") or {}
        )
        element.setdefault(
            "discovery_timestamp", context.get("discovery_timestamp")
        )


def _page_script_source(name: str, page_url: str, elements: list[dict[str, Any]]) -> str:
    test_name = _safe_name(name).replace("-", "_")
    catalogue = pformat(elements, width=100, sort_dicts=False)
    return f'''"""Generated from a fresh DOM capture of {page_url}."""
from playwright.sync_api import Page, expect

PAGE_URL = {page_url!r}
ELEMENTS = {catalogue}


def locator_for(page: Page, element: dict):
    if element.get("test_id"):
        return page.get_by_test_id(element["test_id"])
    if element.get("aria_label"):
        return page.locator("[aria-label=" + repr(element["aria_label"]) + "]")
    if element.get("role") and element.get("name"):
        return page.get_by_role(element["role"], name=element["name"], exact=True)
    if element.get("label"):
        return page.get_by_label(element["label"], exact=True)
    if element.get("placeholder"):
        return page.get_by_placeholder(element["placeholder"], exact=True)
    if element.get("element_id"):
        return page.locator("[id=" + repr(element["element_id"]) + "]")
    if element.get("name"):
        return page.locator("[name=" + repr(element["name"]) + "]").first
    if element.get("css_selector") and element.get("locator_validated"):
        return page.locator(element["css_selector"]).first
    if element.get("visible_text"):
        return page.get_by_text(element["visible_text"], exact=True).first
    raise AssertionError("Element has no verified stable locator")


def test_{test_name}(page: Page):
    page.goto(PAGE_URL, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    expect(page.locator("body")).to_be_visible()
    for element in ELEMENTS:
        locator = locator_for(page, element)
        locator.scroll_into_view_if_needed()
        expect(locator).to_be_visible()
'''


def _step_execution_kind(action: str) -> str:
    lowered = " ".join(action.lower().split())
    interaction_patterns = (
        r"\b(click|fill|type|enter|select|choose|selectoption|check|uncheck)\b",
        r"\bpress\b.+\b(enter|escape|tab|arrow|space)\b",
        r"\bhover\b",
        r"\bwait\s+(for|until)\b",
        r"\b(navigate|open|visit|go\s+to)\b",
    )
    if any(re.search(pattern, lowered) for pattern in interaction_patterns):
        return "action"
    assertion_verb = re.search(r"\b(assert|expect|confirm|ensure|verify)\b", lowered)
    assertion_condition = re.search(
        r"\b(visible|hidden|contains?|text|value|checked|unchecked|enabled|"
        r"disabled|url|title|count|equals?|matches?)\b",
        lowered,
    )
    if assertion_verb and assertion_condition:
        return "assertion"
    return "invalid"


def _invalid_test_steps(
    test_case: dict[str, Any], elements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    identities = [
        _meaningful_words(
            " ".join(
                str(element.get(key) or "")
                for key in ("name", "label", "test_id", "placeholder", "visible_text")
            )
        )
        for element in elements
    ]
    invalid: list[dict[str, Any]] = []
    for step in test_case.get("steps", []):
        action = str(step.get("action") or "")
        kind = _step_execution_kind(action)
        if kind == "invalid":
            invalid.append({
                "step_number": step.get("step_number"),
                "action": action,
                "reason": (
                    "Step has no concrete Playwright action or verifiable assertion."
                ),
            })
            continue
        lowered = action.lower()
        if any(token in lowered for token in ("navigate", "open", "visit", "go to")):
            continue
        if kind == "assertion" and any(
            token in lowered for token in ("url", "title")
        ):
            continue
        action_words = _meaningful_words(action)
        if action_words and not any(action_words & identity for identity in identities):
            invalid.append({
                "step_number": step.get("step_number"),
                "action": action,
                "reason": "No crawl-verified element matches the step target.",
            })
    return invalid


def _test_case_supported(
    test_case: dict[str, Any], elements: list[dict[str, Any]]
) -> bool:
    return not _invalid_test_steps(test_case, elements)


def _is_unsupported_post_registration_behavior(
    test_case: dict[str, Any],
    scenario: dict[str, Any],
    evidence_elements: list[dict[str, Any]],
) -> bool:
    """Check if expected results predict post-registration or post-action outcomes not supported by AC or page evidence."""
    steps = test_case.get("steps", [])
    ac_text = " ".join([
        str(scenario.get("acceptance_criteria") or ""),
        str(scenario.get("description") or ""),
        str(scenario.get("title") or ""),
        str(test_case.get("description") or ""),
    ]).lower()
    
    post_action_patterns = [
        r"redirect", r"dashboard", r"welcome", r"confirmation", r"account created",
        r"logged in", r"success message", r"check email", r"inbox"
    ]
    
    for step in steps:
        expected = str(step.get("expected_result") or "").lower()
        matched_patterns = [pat for pat in post_action_patterns if re.search(pat, expected)]
        if matched_patterns:
            supported_by_ac = any(re.search(pat, ac_text) for pat in matched_patterns)
            supported_by_evidence = any(
                any(re.search(pat, str(el.get(k) or "").lower()) for k in ("name", "label", "visible_text", "page_title", "href"))
                for el in evidence_elements
                for pat in matched_patterns
            )
            if not supported_by_ac and not supported_by_evidence:
                return True
    return False


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
from pathlib import Path
from playwright.sync_api import Page, expect

BASE_URL = {application_url!r}
STEPS = {steps}
DISCOVERED_ELEMENTS = {discovered}


class {class_name}:
    def __init__(self, page: Page):
        self.page = page

    def restore_context(self, element: dict):
        expected_url = element.get("page_url") or BASE_URL
        path = element.get("navigation_path") or [expected_url]
        for url in path:
            if self.page.url.rstrip("/") != url.rstrip("/"):
                self.page.goto(url, wait_until="domcontentloaded")
                self.page.wait_for_load_state("networkidle")
        if self.page.url.rstrip("/") != expected_url.rstrip("/"):
            self.page.goto(expected_url, wait_until="domcontentloaded")
            self.page.wait_for_load_state("networkidle")
        if self.page.url.rstrip("/") != expected_url.rstrip("/"):
            raise AssertionError(
                f"URL differs from crawl evidence: expected {{expected_url}}, got {{self.page.url}}"
            )
        expected_title = element.get("page_title")
        if expected_title and self.page.title().strip().lower() != expected_title.strip().lower():
            raise AssertionError(
                f"Title differs from crawl evidence: expected {{expected_title!r}}, "
                f"got {{self.page.title()!r}}"
            )
        for selector in (element.get("application_state") or {{}}).get("expanded_selectors", []):
            control = self.page.locator(selector).first
            if control.count() and control.is_visible() and control.get_attribute("aria-expanded") != "true":
                control.scroll_into_view_if_needed()
                control.click()

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
            self.restore_context(best_element)
            if best_element.get("test_id"):
                return self.page.get_by_test_id(best_element["test_id"])
            if best_element.get("aria_label"):
                return self.page.locator(
                    "[aria-label=" + repr(best_element["aria_label"]) + "]"
                )
            if best_element.get("role") and best_element.get("name"):
                return self.page.get_by_role(
                    best_element["role"], name=best_element["name"], exact=True
                )
            if best_element.get("label"):
                return self.page.get_by_label(best_element["label"], exact=True)
            if best_element.get("placeholder"):
                return self.page.get_by_placeholder(
                    best_element["placeholder"], exact=True
                )
            if best_element.get("element_id"):
                return self.page.locator(
                    "[id=" + repr(best_element["element_id"]) + "]"
                )
            if best_element.get("name"):
                return self.page.locator(
                    "[name=" + repr(best_element["name"]) + "]"
                ).first
            if best_element.get("css_selector") and best_element.get("locator_validated"):
                return self.page.locator(best_element["css_selector"]).first
            if best_element.get("visible_text"):
                return self.page.get_by_text(
                    best_element["visible_text"], exact=True
                ).first

        raise AssertionError(
            f"Feature not found in application: no discovered element matches {{instruction!r}}"
        )

    def perform(self, instruction: str):
        lowered = instruction.lower()
        values = re.findall(r"[\\'\\\"]([^\\'\\\"]+)[\\'\\\"]", instruction)
        value = values[-1] if values else None
        is_assertion = (
            any(token in lowered for token in ("assert", "expect", "confirm", "ensure", "verify"))
            and any(token in lowered for token in (
                "visible", "hidden", "text", "value", "checked", "enabled",
                "disabled", "url", "title", "contains", "matches",
            ))
        )
        if is_assertion:
            if "url" in lowered:
                if value is None:
                    raise AssertionError(f"URL assertion requires an explicit value: {{instruction}}")
                expect(self.page).to_have_url(re.compile(re.escape(value)))
            elif "title" in lowered:
                if value is None:
                    raise AssertionError(f"Title assertion requires an explicit value: {{instruction}}")
                expect(self.page).to_have_title(re.compile(re.escape(value), re.I))
            else:
                locator = self.stable_locator(instruction)
                if "hidden" in lowered:
                    expect(locator).to_be_hidden()
                elif "checked" in lowered and "unchecked" not in lowered:
                    expect(locator).to_be_checked()
                elif "value" in lowered:
                    if value is None:
                        raise AssertionError(f"Value assertion requires an explicit value: {{instruction}}")
                    expect(locator).to_have_value(value)
                elif "text" in lowered or "contain" in lowered or "match" in lowered:
                    if value is None:
                        raise AssertionError(f"Text assertion requires an explicit value: {{instruction}}")
                    expect(locator).to_contain_text(value)
                else:
                    expect(locator).to_be_visible()
        elif any(token in lowered for token in ("navigate", "open", "visit", "go to")):
            self.page.goto(BASE_URL, wait_until="domcontentloaded")
            self.page.wait_for_load_state("networkidle")
        elif "hover" in lowered:
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            locator.scroll_into_view_if_needed()
            locator.hover()
        elif "wait for" in lowered or "wait until" in lowered:
            self.stable_locator(instruction).wait_for(state="visible")
        elif "press" in lowered:
            key = re.search(r"\\b(Enter|Escape|Tab|Space|Arrow(?:Up|Down|Left|Right))\\b", instruction, re.I)
            if key is None:
                raise AssertionError(f"Press action requires a supported key: {{instruction}}")
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            locator.press(key.group(1))
        elif any(token in lowered for token in ("select", "choose")):
            if value is None:
                raise AssertionError(f"Selection has no explicit UI value: {{instruction}}")
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            locator.scroll_into_view_if_needed()
            if locator.evaluate("el => el.tagName.toLowerCase()") == "select":
                locator.select_option(label=value)
            else:
                locator.click()
                self.page.get_by_role("option", name=re.compile(re.escape(value), re.I)).click()
        elif any(token in lowered for token in ("check", "uncheck")):
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            locator.scroll_into_view_if_needed()
            locator.uncheck() if "uncheck" in lowered else locator.check()
        elif any(token in lowered for token in ("click", "press")):
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            locator.scroll_into_view_if_needed()
            locator.click()
        elif any(token in lowered for token in ("enter", "type", "fill")):
            if value is None:
                raise AssertionError(f"Input has no explicit UI value: {{instruction}}")
            locator = self.stable_locator(instruction)
            locator.wait_for(state="visible")
            locator.scroll_into_view_if_needed()
            locator.fill(value)
        else:
            expect(self.page).to_have_url(re.compile(r"^https?://"))

    def assert_expected(self, expected_result: str):
        quoted = re.findall(r"[\\'\\\"]([^\\'\\\"]+)[\\'\\\"]", expected_result)
        if quoted and any(word in expected_result.lower() for word in ("visible", "displayed", "shown")):
            expect(self.page.get_by_text(quoted[-1], exact=False).first).to_be_visible()
        else:
            expect(self.page).to_have_url(re.compile(r"^https?://"))


def test_{_safe_name(test_case["test_case_id"]).replace("-", "_")}(page: Page):
    app = {class_name}(page)
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    try:
        for step in STEPS:
            app.perform(step["action"])
            app.assert_expected(step["expected_result"])
    except Exception:
        page.screenshot(path="playwright-action-failure.png", full_page=True)
        Path("playwright-action-failure.html").write_text(
            page.content(), encoding="utf-8"
        )
        raise
'''


class AutomationService:
    def __init__(self) -> None:
        self._generations: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, ExecutionReport] = {}
        self._crawl_reports: dict[str, dict[str, Any]] = {}
        self._crawls: dict[str, dict[str, Any]] = {}
        self._crawl_jobs: dict[str, dict[str, Any]] = {}
        self._workflow_crawl_jobs: dict[str, dict[str, Any]] = {}
        self._execution_jobs: dict[str, dict[str, Any]] = {}
        self.seacrawl = SeacrawlAdapter()

    def _crawl_job_response(self, job_id: str) -> CrawlJobResponse:
        job = self._crawl_jobs.get(job_id)
        if job is None:
            raise AutomationError("Crawl job was not found or has expired.")
        report = self._crawl_reports.get(job["report_key"], {})
        return CrawlJobResponse(
            job_id=job_id,
            status=job["status"],
            stop_requested=job["cancel_event"].is_set(),
            progress=report.get("progress", {}),
            result=job.get("result"),
            error=job.get("error"),
        )

    async def start_crawl_job(
        self, request: CrawlAndGenerateRequest
    ) -> CrawlJobResponse:
        job_id = f"crawl-job-{uuid.uuid4()}"
        job: dict[str, Any] = {
            "status": "queued",
            "cancel_event": Event(),
            "report_key": _canonical_page_url(str(request.url)),
            "result": None,
            "error": None,
        }
        self._crawl_jobs[job_id] = job

        async def run() -> None:
            job["status"] = "running"
            try:
                job["result"] = await self.crawl_and_generate(
                    request, cancel_event=job["cancel_event"]
                )
                job["status"] = "completed"
            except Exception as exc:
                job["error"] = str(exc)
                job["status"] = "failed"
                logger.exception("Crawl job failed job_id=%s", job_id)

        job["task"] = asyncio.create_task(run())
        return self._crawl_job_response(job_id)

    def crawl_job(self, job_id: str) -> CrawlJobResponse:
        return self._crawl_job_response(job_id)

    def stop_crawl_job(self, job_id: str) -> CrawlJobResponse:
        job = self._crawl_jobs.get(job_id)
        if job is None:
            raise AutomationError("Crawl job was not found or has expired.")
        if job["status"] in {"queued", "running"}:
            job["cancel_event"].set()
            job["status"] = "stopping"
        return self._crawl_job_response(job_id)

    def _workflow_crawl_job_response(
        self, job_id: str
    ) -> WorkflowCrawlJobResponse:
        job = self._workflow_crawl_jobs.get(job_id)
        if job is None:
            raise AutomationError("Workflow crawl job was not found or has expired.")
        report = self._crawl_reports.get(job["report_key"], {})
        return WorkflowCrawlJobResponse(
            job_id=job_id,
            status=job["status"],
            stop_requested=job["cancel_event"].is_set(),
            progress=report.get("progress", {}),
            crawl=job.get("crawl"),
            generation=job.get("generation"),
            error=job.get("error"),
        )

    async def start_workflow_crawl_job(
        self, request: CrawlApplicationRequest
    ) -> WorkflowCrawlJobResponse:
        job_id = f"workflow-crawl-job-{uuid.uuid4()}"
        job: dict[str, Any] = {
            "status": "queued",
            "cancel_event": Event(),
            "report_key": _canonical_page_url(str(request.application_url)),
            "crawl": None,
            "generation": None,
            "error": None,
        }
        self._workflow_crawl_jobs[job_id] = job

        async def run() -> None:
            job["status"] = "running"
            try:
                crawl = await self.analyze_application(
                    request, cancel_event=job["cancel_event"]
                )
                job["crawl"] = crawl
                has_scanned_data = (
                    crawl.crawl_status != "crawl_blocked"
                    and (
                        crawl.pages_crawled > 0
                        or bool(crawl.discovered_elements)
                    )
                )
                if has_scanned_data:
                    job["generation"] = await self.generate(
                        GenerateScriptsRequest(
                            workflow_id=request.workflow_id,
                            application_url=request.application_url,
                            crawl_id=crawl.crawl_id,
                        )
                    )
                job["status"] = "completed"
            except Exception as exc:
                job["error"] = str(exc)
                job["status"] = "failed"
                logger.exception(
                    "Workflow crawl job failed job_id=%s", job_id
                )

        job["task"] = asyncio.create_task(run())
        return self._workflow_crawl_job_response(job_id)

    def workflow_crawl_job(self, job_id: str) -> WorkflowCrawlJobResponse:
        return self._workflow_crawl_job_response(job_id)

    def stop_workflow_crawl_job(
        self, job_id: str
    ) -> WorkflowCrawlJobResponse:
        job = self._workflow_crawl_jobs.get(job_id)
        if job is None:
            raise AutomationError("Workflow crawl job was not found or has expired.")
        if job["status"] in {"queued", "running"}:
            job["cancel_event"].set()
            job["status"] = "stopping"
        return self._workflow_crawl_job_response(job_id)

    def _execution_job_response(self, job_id: str) -> ExecutionJobResponse:
        job = self._execution_jobs.get(job_id)
        if job is None:
            raise AutomationError("Execution job was not found or has expired.")
        return ExecutionJobResponse(
            job_id=job_id,
            status=job["status"],
            report=job.get("report"),
            error=job.get("error"),
        )

    async def start_execution_job(
        self, request: ExecuteScriptsRequest
    ) -> ExecutionJobResponse:
        job_id = f"execution-job-{uuid.uuid4()}"
        job: dict[str, Any] = {
            "status": "queued",
            "report": None,
            "error": None,
        }
        self._execution_jobs[job_id] = job

        async def run() -> None:
            job["status"] = "running"
            try:
                job["report"] = await self.execute(request)
                job["status"] = "completed"
            except Exception as exc:
                job["error"] = str(exc)
                job["status"] = "failed"
                logger.exception("Execution job failed job_id=%s", job_id)

        job["task"] = asyncio.create_task(run())
        return self._execution_job_response(job_id)

    def execution_job(self, job_id: str) -> ExecutionJobResponse:
        return self._execution_job_response(job_id)

    def _completed_crawl_report(
        self, url: str, title: str | None, elements: list[DiscoveredElement]
    ) -> dict[str, Any]:
        report = self._crawl_reports.get(_canonical_page_url(url))
        if report is None:
            # Compatibility for injected discovery adapters and existing tests.
            pages = {
                _canonical_page_url(str(item.page_url or url))
                for item in elements
            } or {_canonical_page_url(url)}
            report = {
                "status": "crawl_completed",
                "start_url": url,
                "actual_application_reached": True,
                "pages_discovered": len(pages),
                "pages_completed": len(pages),
                "pages_skipped": [],
                "remaining_crawl_queue": [],
                "unprocessed_navigation_states": [],
                "page_inventory": [],
                "navigation_relationships": [],
                "events": ["crawl_started", "crawl_completed"],
                "page_title": title,
            }
        if report.get("status") != "crawl_completed":
            raise AutomationError(_crawl_failure_message(report))
        if not report.get("actual_application_reached"):
            raise AutomationError(
                "Script generation stopped because the actual application UI was not reached."
            )
        if report.get("remaining_crawl_queue"):
            raise AutomationError(
                "Script generation stopped because the crawl queue is not empty."
            )
        return report

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

    @staticmethod
    async def _crawl_wait(page: Any) -> None:
        timeout = int(settings.automation_navigation_timeout_seconds * 1000)
        await page.wait_for_load_state("domcontentloaded", timeout=timeout)
        if settings.automation_wait_for_network_idle:
            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=int(
                        settings.automation_crawl_network_idle_timeout_seconds * 1000
                    ),
                )
            except Exception:
                logger.debug("Network remained active after DOM readiness url=%s", page.url)
        await page.locator("body").wait_for(state="visible", timeout=timeout)

    async def _navigate_with_retries(self, page: Any, url: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(settings.automation_navigation_retry_limit + 1):
            try:
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=int(settings.automation_navigation_timeout_seconds * 1000),
                )
                await self._crawl_wait(page)
                return response
            except Exception as exc:
                last_error = exc
                if attempt >= settings.automation_navigation_retry_limit:
                    break
                await asyncio.sleep(min(0.5 * (2**attempt), 4.0))
        assert last_error is not None
        raise last_error

    @staticmethod
    def _alternate_locators(page: Any, element: dict[str, Any]) -> list[Any]:
        locators: list[Any] = []
        if element.get("test_id"):
            locators.append(page.get_by_test_id(element["test_id"]))
        if element.get("label"):
            locators.append(page.get_by_label(element["label"], exact=True))
        if element.get("role") and element.get("name"):
            locators.append(
                page.get_by_role(
                    element["role"], name=element["name"], exact=True
                )
            )
        if element.get("placeholder"):
            locators.append(
                page.get_by_placeholder(element["placeholder"], exact=True)
            )
        if element.get("element_id"):
            locators.append(page.locator(f'[id="{element["element_id"]}"]'))
        if element.get("name"):
            locators.append(page.locator(f'[name="{element["name"]}"]'))
        if element.get("css_selector"):
            locators.append(page.locator(element["css_selector"]))
        if element.get("visible_text"):
            locators.append(page.get_by_text(element["visible_text"], exact=True))
        return locators

    @staticmethod
    async def _capture_interactive_elements(page: Any) -> list[dict[str, Any]]:
        return await page.locator(
            "a,button,input,select,textarea,[role='link'],[role='button'],"
            "[role='tab'],[role='menuitem'],[data-testid]"
        ).evaluate_all(
            """els => els.slice(0, 500).filter(el => {
              const s=getComputedStyle(el), b=el.getBoundingClientRect();
              return s.visibility!=='hidden' && s.display!=='none' && b.width>0 && b.height>0 && !el.disabled;
            }).map(el => {
              const tag=el.tagName.toLowerCase();
              const role=el.getAttribute('role') || ({a:'link',button:'button',select:'combobox',textarea:'textbox'}[tag]
                || (tag==='input' ? ({checkbox:'checkbox',radio:'radio',submit:'button',button:'button'}[el.type] || 'textbox') : null));
              const text=(el.innerText || el.textContent || '').trim();
              const name=el.getAttribute('aria-label') || el.getAttribute('name') || text || null;
              const testId=el.getAttribute('data-testid'), id=el.id || null;
              const css=testId ? `[data-testid="${CSS.escape(testId)}"]` : id ? `#${CSS.escape(id)}`
                : el.getAttribute('name') ? `${tag}[name="${CSS.escape(el.getAttribute('name'))}"]`
                : `${tag}:nth-of-type(${[...el.parentElement.children].filter(x=>x.tagName===el.tagName).indexOf(el)+1})`;
              const nav=`${text} ${name || ''}`.toLowerCase();
              const unsafe=/delete|remove|logout|log out|sign out|submit|save|pay|purchase|checkout|confirm|cancel account/.test(nav);
              return {tag,role,name,aria_label:el.getAttribute('aria-label'),
                element_id:id,css_selector:css,test_id:testId,
                label:el.labels?.[0]?.innerText?.trim() || el.getAttribute('aria-labelledby') || null,
                placeholder:el.getAttribute('placeholder'),visible_text:text || null,href:el.href || null,
                input_type:el.getAttribute('type'),checked:typeof el.checked==='boolean' ? el.checked : null,
                options:tag==='select' ? [...el.options].map(o=>({label:o.text.trim(),value:o.value})) : [],
                locator_validated:true,
                navigation_candidate:!unsafe && (tag==='a' || ['link','tab','menuitem'].includes(role)
                  || (role==='button' && /menu|next|previous|back|home|dashboard|view|open|details|login|signin|sign-in|log-in|sign\s*in|signup|sign-up|sign\s*up|register|get\s*started|start/.test(nav)))};
            })"""
        )

    async def _discover(
        self,
        url: str,
        *,
        cancel_event: Event | None = None,
        authentication: Any = None,
        testing_scope: str = "full_application",
    ) -> tuple[str | None, list[DiscoveredElement]]:
        if settings.app_mock_mode:
            self._crawl_reports[_canonical_page_url(url)] = {
                "status": "crawl_completed", "start_url": url,
                "actual_application_reached": True, "pages_discovered": 1,
                "pages_completed": 1, "pages_skipped": [],
                "remaining_crawl_queue": [], "unprocessed_navigation_states": [],
                "events": ["crawl_started", "page_discovered", "page_scanned", "crawl_completed"],
            }
            return "Mock Application", [
                DiscoveredElement(tag="button", role="button", name="Mock submit"),
                DiscoveredElement(tag="input", label="Mock input", input_type="text"),
            ]
        discovery_cache_key = cache.fingerprint(
            "application-crawl",
            {
                "crawler_version": 3,
                "url": _canonical_page_url(url),
                "page_limit": settings.automation_crawl_page_limit,
                "depth_limit": settings.automation_crawl_depth_limit,
                "testing_scope": testing_scope,
            },
        )
        cached_discovery = await cache.get_json(discovery_cache_key)
        if (
            cached_discovery
            and cached_discovery.get("crawl_report", {}).get("status")
            == "crawl_completed"
        ):
            cached_report = cached_discovery["crawl_report"]
            cached_report["cache_hit"] = True
            self._crawl_reports[_canonical_page_url(url)] = cached_report
            return (
                cached_discovery.get("page_title"),
                [
                    DiscoveredElement.model_validate(item)
                    for item in cached_discovery.get("discovered_elements", [])
                ],
            )
        report: dict[str, Any] = {
            "status": "crawl_started",
            "start_url": url,
            "actual_application_reached": False,
            "pages_discovered": 0,
            "pages_completed": 0,
            "pages_skipped": [],
            "remaining_crawl_queue": [],
            "unprocessed_navigation_states": [],
            "navigation_relationships": [],
            "page_inventory": [],
            "challenge_evidence": [],
            "console_errors": [],
            "network_failures": [],
            "events": ["crawl_started"],
            "progress": {},
            "progress_history": [],
            "recommended_corrective_action": None,
        }
        report_key = _canonical_page_url(url)
        # Store the live report object so crawl-job polling can expose progress.
        self._crawl_reports[report_key] = report
        started_at = time.monotonic()
        deadline = started_at + settings.automation_crawl_timeout_seconds
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=settings.automation_crawl_headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )

                storage_state = None
                auth_mode = getattr(authentication, "auth_mode", None) if authentication else None
                if isinstance(authentication, dict):
                    auth_mode = authentication.get("auth_mode")

                if authentication and auth_mode == "existing_session":
                    sess_val = (
                        getattr(authentication, "session_state", None)
                        if hasattr(authentication, "session_state")
                        else (authentication.get("session_state") if isinstance(authentication, dict) else None)
                    )
                    if isinstance(sess_val, str):
                        try:
                            sess_val = json.loads(sess_val)
                        except Exception:
                            sess_val = None
                    if not sess_val:
                        report["status"] = "crawl_blocked"
                        report["failure_reason"] = "Authentication required: No valid session state provided."
                        report["recommended_corrective_action"] = "Provide a valid session state object or JSON string before retrying."
                        return None, []
                    storage_state = sess_val

                context = await browser.new_context(
                    storage_state=storage_state,
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        f"Chrome/{browser.version} Safari/537.36"
                    ),
                    locale="en-US",
                    viewport={"width": 1440, "height": 900},
                )
                await context.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                )
                page = await context.new_page()
                page.on(
                    "console",
                    lambda message: report["console_errors"].append(message.text)
                    if message.type == "error" else None,
                )
                page.on(
                    "requestfailed",
                    lambda request: report["network_failures"].append(
                        {"url": request.url, "failure": request.failure}
                    ),
                )
                origin = urlsplit(url)

                # Verify or perform authentication if required
                if authentication and (auth_mode == "credentials" or getattr(authentication, "get_identifier", None) or (isinstance(authentication, dict) and authentication.get("password"))):
                    try:
                        await self._navigate_with_retries(page, url)
                        auth_evidence = await self._authenticate_if_required(page, authentication, url)
                        if auth_evidence.get("required") and not auth_evidence.get("succeeded"):
                            report["status"] = "crawl_blocked"
                            report["failure_reason"] = f"Authentication verification failed for URL {url}."
                            report["recommended_corrective_action"] = "Check credentials and application login form, then retry."
                            return None, []
                        report["auth_state"] = await context.storage_state()
                    except PlaywrightAuthenticationError as auth_err:
                        report["status"] = "crawl_blocked"
                        report["failure_reason"] = f"Authentication Failed: {auth_err}"
                        report["recommended_corrective_action"] = "Check generic identifier and password, then retry."
                        return None, []
                elif authentication and auth_mode == "existing_session":
                    try:
                        await self._navigate_with_retries(page, url)
                        password_elem = page.locator("input[type='password']").first
                        if await password_elem.count() and await password_elem.is_visible():
                            report["status"] = "crawl_blocked"
                            report["failure_reason"] = "Authentication Failed: Provided session state is expired or invalid (login page displayed)."
                            report["recommended_corrective_action"] = "Provide a fresh authenticated session state."
                            return None, []
                    except Exception as sess_err:
                        report["status"] = "crawl_blocked"
                        report["failure_reason"] = f"Authentication Failed: Existing session verification failed: {sess_err}"
                        return None, []

                async def explore_control(
                    source_url: str, control: dict[str, Any]
                ) -> dict[str, Any]:
                    worker_page = await context.new_page()
                    last_error: Exception | None = None
                    try:
                        for attempt in range(
                            settings.automation_navigation_retry_limit + 1
                        ):
                            try:
                                await self._navigate_with_retries(
                                    worker_page, source_url
                                )
                                before = _canonical_page_url(worker_page.url)
                                candidates = self._alternate_locators(
                                    worker_page, control
                                )
                                if not candidates:
                                    break
                                locator = candidates[
                                    min(attempt, len(candidates) - 1)
                                ].first
                                if not await locator.is_visible():
                                    continue
                                await locator.click(
                                    timeout=int(
                                        settings.automation_action_timeout_seconds
                                        * 1000
                                    )
                                )
                                try:
                                    await worker_page.wait_for_url(
                                        lambda value: _canonical_page_url(str(value))
                                        != before,
                                        timeout=int(
                                            settings.automation_navigation_settle_timeout_seconds
                                            * 1000
                                        ),
                                    )
                                except Exception:
                                    pass
                                await self._crawl_wait(worker_page)
                                after = _canonical_page_url(worker_page.url)
                                refreshed = await self._capture_interactive_elements(
                                    worker_page
                                )
                                return {
                                    "success": True,
                                    "before": before,
                                    "after": after,
                                    "elements": refreshed,
                                }
                            except Exception as exc:
                                last_error = exc
                        return {
                            "success": False,
                            "error": str(last_error or "no visible alternate locator"),
                        }
                    finally:
                        await worker_page.close()

                if testing_scope == "specific_page":
                    verified_candidates = []
                else:
                    seacrawl_urls = await self.seacrawl.discover_urls(
                        url=url,
                        page_limit=settings.automation_crawl_page_limit,
                        depth_limit=settings.automation_crawl_depth_limit,
                    )
                    verified_candidates = [
                        candidate
                        for candidate in seacrawl_urls
                        if urlsplit(candidate).scheme in {"http", "https"}
                        and urlsplit(candidate).netloc == origin.netloc
                    ]
                pending = [(url, 0), *[(candidate, 1) for candidate in verified_candidates]]
                visited: set[str] = set()
                queued: set[str] = {_canonical_page_url(candidate) for candidate, _ in pending}
                raw: list[dict[str, Any]] = []
                title = None
                state_counts: dict[str, int] = {}
                report["status"] = "crawl_in_progress"
                report["events"].append("crawl_in_progress")
                while pending and len(report["page_inventory"]) < settings.automation_crawl_page_limit:
                    if cancel_event is not None and cancel_event.is_set():
                        report["failure_reason"] = "Crawl stopped by user."
                        report["stop_requested"] = True
                        report["remaining_crawl_queue"] = [item[0] for item in pending]
                        report["events"].append("crawl_stopped")
                        break
                    now = time.monotonic()
                    elapsed = now - started_at
                    completed = len(report["page_inventory"])
                    average_page_seconds = elapsed / completed if completed else 0
                    progress = {
                        "pages_discovered": len(queued),
                        "pages_completed": completed,
                        "pages_remaining": len(pending),
                        "current_crawl_depth": pending[0][1] if pending else 0,
                        "elapsed_seconds": round(elapsed, 2),
                        "estimated_completion_seconds": (
                            round(average_page_seconds * len(pending), 2)
                            if completed else None
                        ),
                    }
                    report["progress"] = progress
                    report["progress_history"].append(progress)
                    logger.info(
                        "Crawl progress url=%s discovered=%s completed=%s remaining=%s "
                        "depth=%s elapsed_seconds=%s estimated_completion_seconds=%s",
                        url,
                        progress["pages_discovered"],
                        progress["pages_completed"],
                        progress["pages_remaining"],
                        progress["current_crawl_depth"],
                        progress["elapsed_seconds"],
                        progress["estimated_completion_seconds"],
                    )
                    if now >= deadline:
                        report["failure_reason"] = "Configurable hard crawl timeout was reached."
                        break
                    page_url, depth = pending.pop(0)
                    canonical_requested = _canonical_page_url(page_url)
                    if canonical_requested in visited:
                        continue
                    report["events"].append("page_discovered")
                    try:
                        navigation_response = await self._navigate_with_retries(
                            page, page_url
                        )
                        if authentication and (auth_mode == "credentials" or getattr(authentication, "get_identifier", None) or (isinstance(authentication, dict) and authentication.get("password"))):
                            auth_evidence = await self._authenticate_if_required(page, authentication, page_url)
                            if auth_evidence.get("required") and auth_evidence.get("succeeded"):
                                report["auth_state"] = await context.storage_state()
                    except Exception as navigation_error:
                        report["pages_skipped"].append({
                            "url": page_url,
                            "reason": f"navigation_failed: {type(navigation_error).__name__}: {navigation_error}",
                        })
                        continue
                    current_url = _canonical_page_url(page.url)
                    if urlsplit(current_url).netloc != origin.netloc:
                        report["pages_skipped"].append({
                            "url": page_url, "reason": "redirected_to_external_domain",
                        })
                        continue
                    discovered = await self._capture_interactive_elements(page)
                    page_title = await page.title()
                    visible_text = await page.locator("body").inner_text(timeout=5000)
                    challenge = _challenge_evidence(
                        title=page_title,
                        visible_text=visible_text,
                        status_code=navigation_response.status if navigation_response else None,
                        elements=discovered,
                    )
                    if (
                        challenge
                        and settings.automation_challenge_wait_seconds > 0
                        and not (cancel_event is not None and cancel_event.is_set())
                    ):
                        report["events"].append("challenge_resolution_wait_started")
                        challenge_deadline = min(
                            deadline,
                            time.monotonic()
                            + settings.automation_challenge_wait_seconds,
                        )
                        while (
                            challenge
                            and time.monotonic() < challenge_deadline
                            and not (
                                cancel_event is not None and cancel_event.is_set()
                            )
                        ):
                            remaining_ms = max(
                                1,
                                int((challenge_deadline - time.monotonic()) * 1000),
                            )
                            await page.wait_for_timeout(min(2000, remaining_ms))
                            discovered = await self._capture_interactive_elements(page)
                            page_title = await page.title()
                            visible_text = await page.locator("body").inner_text(
                                timeout=5000
                            )
                            challenge = _challenge_evidence(
                                title=page_title,
                                visible_text=visible_text,
                                # The original navigation response can remain 403
                                # after a JavaScript challenge replaces the page.
                                status_code=None,
                                elements=discovered,
                            )
                        report["events"].append(
                            "challenge_resolved"
                            if challenge is None
                            else "challenge_resolution_wait_expired"
                        )
                    if cancel_event is not None and cancel_event.is_set():
                        report["failure_reason"] = "Crawl stopped by user."
                        report["stop_requested"] = True
                        report["remaining_crawl_queue"] = [
                            current_url, *[item[0] for item in pending]
                        ]
                        report["events"].append("crawl_stopped")
                        break
                    if challenge:
                        screenshot_dir = self.artifact_root / "crawl-evidence"
                        screenshot_dir.mkdir(parents=True, exist_ok=True)
                        challenge_screenshot_path = (
                            screenshot_dir / f"challenge-{uuid.uuid4()}.png"
                        )
                        try:
                            await page.screenshot(
                                path=str(challenge_screenshot_path), full_page=True
                            )
                            challenge["screenshot"] = str(challenge_screenshot_path)
                        except Exception:
                            challenge["screenshot"] = None
                        report["remaining_crawl_queue"] = [
                            current_url, *[item[0] for item in pending]
                        ]
                        report.update({
                            "status": "crawl_blocked",
                            "blocked_url": current_url,
                            "failure_reason": challenge["reason"],
                            "last_successfully_loaded_page": (
                                report["page_inventory"][-1]["final_url"]
                                if report["page_inventory"] else None
                            ),
                            "recommended_corrective_action": (
                                "Resolve the challenge in the crawl environment, allow automated browser "
                                "access, or provide an authenticated session before retrying."
                            ),
                        })
                        report["challenge_evidence"].append(challenge)
                        report["events"].append("challenge_detected")
                        pending.clear()
                        break
                    visited.add(canonical_requested)
                    visited.add(current_url)
                    title = title or page_title
                    report["actual_application_reached"] = True
                    try:
                        await page.evaluate(
                            """async () => {
                              const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                              let previous = 0;
                              for (let i = 0; i < 12; i++) {
                                window.scrollTo(0, document.body.scrollHeight);
                                await delay(150);
                                const height = document.body.scrollHeight;
                                if (height === previous) break;
                                previous = height;
                              }
                              window.scrollTo(0, 0);
                            }"""
                        )
                    except Exception:
                        logger.debug("Lazy-content scrolling failed url=%s", current_url)
                    expanded_selectors: list[str] = []
                    for selector in (
                        "[aria-expanded='false']",
                        "[aria-haspopup='menu']",
                        "[aria-haspopup='dialog']",
                        "[data-bs-toggle='dropdown']",
                        "[data-bs-toggle='collapse']",
                        "[data-bs-toggle='modal']",
                        "[data-toggle='dropdown']",
                        "[data-toggle='collapse']",
                        "[data-toggle='modal']",
                        "details:not([open]) > summary",
                        "[role='tab'][aria-selected='false']",
                    ):
                        for expandable in (await page.locator(selector).all())[:30]:
                            try:
                                if await expandable.is_visible():
                                    await expandable.click(
                                        timeout=int(settings.automation_action_timeout_seconds * 1000)
                                    )
                                    stable_expander = await expandable.evaluate(
                                        """el => {
                                          const q = value => JSON.stringify(value);
                                          if (el.getAttribute('data-testid'))
                                            return `[data-testid=${q(el.getAttribute('data-testid'))}]`;
                                          if (el.id) return `[id=${q(el.id)}]`;
                                          if (el.getAttribute('name'))
                                            return `[name=${q(el.getAttribute('name'))}]`;
                                          if (el.getAttribute('aria-label'))
                                            return `[aria-label=${q(el.getAttribute('aria-label'))}]`;
                                          return null;
                                        }"""
                                    )
                                    if stable_expander:
                                        expanded_selectors.append(stable_expander)
                            except Exception:
                                logger.debug(
                                    "Non-destructive hidden-state expansion failed selector=%s",
                                    selector,
                                )
                    expanded = await self._capture_interactive_elements(page)
                    discovered.extend(
                        item for item in expanded
                        if (
                            item.get("test_id"),
                            item.get("element_id"),
                            item.get("css_selector"),
                        ) not in {
                            (
                                existing.get("test_id"),
                                existing.get("element_id"),
                                existing.get("css_selector"),
                            )
                            for existing in discovered
                        }
                    )
                    for item in discovered:
                        item["page_url"] = current_url
                    raw.extend(discovered)
                    try:
                        dom = await page.content()
                    except Exception:
                        dom = ""
                    state_fingerprint = hashlib.sha256(
                        re.sub(r"\s+", " ", dom).encode("utf-8", errors="ignore")
                    ).hexdigest()[:16]
                    state_counts[state_fingerprint] = state_counts.get(state_fingerprint, 0) + 1
                    if state_counts[state_fingerprint] > settings.automation_crawl_repeated_state_limit:
                        report["pages_skipped"].append({
                            "url": current_url,
                            "reason": "repeated_application_state_limit_reached",
                            "state_fingerprint": state_fingerprint,
                        })
                        continue
                    snapshot_dir = self.artifact_root / "crawl-evidence" / "dom"
                    snapshot_dir.mkdir(parents=True, exist_ok=True)
                    dom_snapshot_path = snapshot_dir / f"{state_fingerprint}.html"
                    if not dom_snapshot_path.is_file():
                        dom_snapshot_path.write_text(dom, encoding="utf-8")
                    discovered_at = datetime.now(timezone.utc).isoformat()
                    form_state = await page.locator(
                        "input:not([type='password']),select,textarea"
                    ).evaluate_all(
                        """els => els.slice(0, 200).map(el => ({
                          test_id: el.getAttribute('data-testid'),
                          element_id: el.id || null,
                          name: el.getAttribute('name'),
                          value: el.value,
                          checked: typeof el.checked === 'boolean' ? el.checked : null,
                          selected_values: el.tagName.toLowerCase() === 'select'
                            ? [...el.selectedOptions].map(option => option.value) : []
                        })).filter(item => item.test_id || item.element_id || item.name)"""
                    )
                    for item in discovered:
                        item.update({
                            "page_title": page_title,
                            "dom_snapshot": str(dom_snapshot_path),
                            "application_state": {
                                "route": urlsplit(current_url).path or "/",
                                "state_fingerprint": state_fingerprint,
                                "expanded_selectors": list(dict.fromkeys(expanded_selectors)),
                                "form_values": form_state,
                                "scroll_restoration": "top",
                            },
                            "discovery_timestamp": discovered_at,
                        })
                    try:
                        accessibility_tree = await page.locator("body").aria_snapshot(timeout=5000)
                    except Exception:
                        accessibility_tree = ""
                    try:
                        structured_regions = await page.locator(
                            "table,[role='table'],[role='list'],ul,ol,[role='tablist'],"
                            "[role='dialog'],dialog,[role='alert'],.card,.validation-summary-errors,"
                            ".field-validation-error"
                        ).evaluate_all(
                            """els => els.slice(0, 250).map(el => ({
                              tag: el.tagName.toLowerCase(),
                              role: el.getAttribute('role'),
                              id: el.id || null,
                              test_id: el.getAttribute('data-testid'),
                              text: (el.innerText || el.textContent || '').trim().slice(0, 4000)
                            }))"""
                        )
                    except Exception:
                        structured_regions = []
                    screenshot_dir = self.artifact_root / "crawl-evidence"
                    screenshot = None
                    if settings.automation_crawl_screenshot_mode == "all":
                        screenshot_dir.mkdir(parents=True, exist_ok=True)
                        screenshot_path = screenshot_dir / f"{uuid.uuid4()}.png"
                        try:
                            await page.screenshot(path=str(screenshot_path), full_page=True)
                            screenshot = str(screenshot_path)
                        except Exception:
                            screenshot = None
                    report["page_inventory"].append({
                        "url": current_url,
                        "requested_url": page_url,
                        "final_url": current_url,
                        "route": urlsplit(current_url).path or "/",
                        "depth": depth,
                        "state_fingerprint": state_fingerprint,
                        "application_state": {
                            "expanded_selectors": list(dict.fromkeys(expanded_selectors)),
                            "scroll_restoration": "top",
                        },
                        "discovery_timestamp": discovered_at,
                        "http_status": navigation_response.status if navigation_response else None,
                        "title": page_title,
                        "visible_text": visible_text[:50000],
                        "dom": dom[:250000],
                        "dom_snapshot": str(dom_snapshot_path),
                        "accessibility_tree": accessibility_tree[:100000],
                        "elements": discovered,
                        "forms": [item for item in discovered if item.get("tag") in {"input", "select", "textarea"}],
                        "links": [item for item in discovered if item.get("href")],
                        "buttons": [item for item in discovered if item.get("role") == "button"],
                        "structured_regions": structured_regions,
                        "validation_messages": [
                            item for item in structured_regions
                            if item.get("role") == "alert"
                            or "validation" in str(item.get("id") or "").lower()
                        ],
                        "screenshot": screenshot,
                    })
                    report["events"].append("page_scanned")
                    if testing_scope != "specific_page":
                        for item in discovered:
                            href = item.get("href")
                            parsed = urlsplit(href) if href else None
                            skip_reason = _link_skip_reason(str(href), origin.netloc) if href else None
                            if href and skip_reason:
                                report["pages_skipped"].append({
                                    "url": str(href), "reason": skip_reason,
                                    "discovered_from": current_url,
                                })
                            if parsed and not skip_reason:
                                clean_href = _canonical_page_url(href)
                                if (
                                    depth < settings.automation_crawl_depth_limit
                                    and clean_href not in visited
                                    and clean_href not in queued
                                ):
                                    pending.append((clean_href, depth + 1))
                                    queued.add(clean_href)
                                    report["navigation_relationships"].append({
                                        "from": current_url, "to": clean_href,
                                        "via": item.get("name") or item.get("visible_text") or "link",
                                    })
                                elif depth >= settings.automation_crawl_depth_limit:
                                    report["pages_skipped"].append({
                                        "url": clean_href,
                                        "reason": "maximum_crawl_depth_reached",
                                        "discovered_from": current_url,
                                    })
                        if depth < settings.automation_crawl_depth_limit:
                            controls = [
                                item for item in discovered
                                if item.get("navigation_candidate") and not item.get("href")
                                and item.get("css_selector")
                            ][:settings.automation_navigation_controls_per_page]
                            crawl_concurrency = max(
                                1, settings.automation_crawl_concurrency
                            )
                            for offset in range(0, len(controls), crawl_concurrency):
                                control_batch = controls[
                                    offset : offset + crawl_concurrency
                                ]
                                results = await asyncio.gather(
                                    *[
                                        explore_control(current_url, control)
                                        for control in control_batch
                                    ]
                                )
                                for control, result in zip(control_batch, results):
                                    if not result["success"]:
                                        report["unprocessed_navigation_states"].append({
                                            "page_url": current_url,
                                            "control": control.get("name") or control.get("css_selector"),
                                            "reason": (
                                                "safe_navigation_exploration_failed_after_"
                                                f"{settings.automation_navigation_retry_limit + 1}_attempts"
                                            ),
                                            "error": result.get("error"),
                                        })
                                        continue
                                    before = result["before"]
                                    after = result["after"]
                                    if urlsplit(after).netloc != origin.netloc:
                                        continue
                                    refreshed = result["elements"]
                                    for refreshed_item in refreshed:
                                        refreshed_item["page_url"] = after
                                    raw.extend(refreshed)
                                    for refreshed_item in refreshed:
                                        refreshed_href = refreshed_item.get("href")
                                        if not refreshed_href:
                                            continue
                                        skip_reason = _link_skip_reason(
                                            str(refreshed_href), origin.netloc
                                        )
                                        if skip_reason:
                                            report["pages_skipped"].append({
                                                "url": str(refreshed_href),
                                                "reason": skip_reason,
                                                "discovered_from": after,
                                            })
                                            continue
                                        clean_refreshed_href = _canonical_page_url(
                                            str(refreshed_href)
                                        )
                                        if (
                                            clean_refreshed_href not in visited
                                            and clean_refreshed_href not in queued
                                        ):
                                            pending.append((clean_refreshed_href, depth + 1))
                                            queued.add(clean_refreshed_href)
                                            report["navigation_relationships"].append({
                                                "from": after,
                                                "to": clean_refreshed_href,
                                                "via": (
                                                    refreshed_item.get("name")
                                                    or refreshed_item.get("visible_text")
                                                    or "dynamic_navigation"
                                                ),
                                            })
                                    if after != before and after not in visited and after not in queued:
                                        pending.append((after, depth + 1))
                                        queued.add(after)

                await browser.close()
            report["pages_discovered"] = len(queued)
            report["pages_completed"] = len(report["page_inventory"])
            report["remaining_crawl_queue"] = (
                report.get("remaining_crawl_queue") or [item[0] for item in pending]
            )
            elapsed = time.monotonic() - started_at
            report["progress"] = {
                "pages_discovered": len(queued),
                "pages_completed": len(report["page_inventory"]),
                "pages_remaining": len(report["remaining_crawl_queue"]),
                "current_crawl_depth": max(
                    (item.get("depth", 0) for item in report["page_inventory"]),
                    default=0,
                ),
                "elapsed_seconds": round(elapsed, 2),
                "estimated_completion_seconds": (
                    0 if not report["remaining_crawl_queue"] else report["progress"].get(
                        "estimated_completion_seconds"
                    )
                ),
            }
            report["progress_history"].append(report["progress"])
            limit_reached = (
                bool(pending)
                and len(report["page_inventory"]) >= settings.automation_crawl_page_limit
            )
            blocking_skips = [
                item for item in report["pages_skipped"]
                if str(item.get("reason", "")).startswith("navigation_failed")
                or item.get("reason") == "maximum_crawl_depth_reached"
            ]
            if report["status"] != "crawl_blocked":
                if (
                    report["actual_application_reached"]
                    and not pending
                    and not limit_reached
                    and not report.get("failure_reason")
                    and not report["unprocessed_navigation_states"]
                    and not blocking_skips
                ):
                    report["status"] = "crawl_completed"
                    report["events"].append("crawl_completed")
                else:
                    report["status"] = "crawl_incomplete"
                    report["failure_reason"] = report.get("failure_reason") or (
                        "The page limit was reached before the crawl queue was empty."
                        if limit_reached else
                        "One or more discovered navigation states could not be processed."
                        if report["unprocessed_navigation_states"] else
                        "One or more reachable pages could not be processed within the configured limits."
                        if blocking_skips else
                        "The application crawl did not reach a complete state."
                    )
                    report["recommended_corrective_action"] = (
                        "Review and execute the scripts generated from pages scanned before the stop."
                        if report.get("stop_requested")
                        else "Increase crawl page/depth/time limits or fix skipped navigation failures, then retry."
                    )
                    report["events"].append("crawl_incomplete")
            self._crawl_reports[report_key] = report
            if report["status"] != "crawl_completed":
                raise AutomationError(_crawl_failure_message(report))
            if testing_scope == "specific_page":
                canonical_target = _canonical_page_url(url)
                report["page_inventory"] = [
                    item for item in report["page_inventory"]
                    if _canonical_page_url(str(item.get("url") or item.get("final_url") or "")) == canonical_target
                ]
                raw = [
                    item for item in raw
                    if _canonical_page_url(str(item.get("page_url") or url)) == canonical_target
                ]
                report["navigation_relationships"] = []
                report["pages_discovered"] = len(report["page_inventory"])
                report["pages_completed"] = len(report["page_inventory"])
            _attach_navigation_context(
                url,
                report["navigation_relationships"],
                raw,
                report["page_inventory"],
            )
            unique = {
                (
                    str(item.get("page_url") or url),
                    str(item.get("test_id") or item.get("element_id") or item.get("css_selector")),
                ): item
                for item in raw
            }
            elements = [DiscoveredElement.model_validate(item) for item in unique.values()]
            await cache.set_json(
                discovery_cache_key,
                {
                    "page_title": title,
                    "crawl_report": report,
                    "discovered_elements": [
                        item.model_dump(mode="json") for item in elements
                    ],
                },
                settings.redis_script_ttl_seconds,
            )
            logger.info(
                "DOM discovery complete url=%s pages_visited=%d elements_found=%d",
                url, len(visited), len(elements),
            )
            return title, elements
        except Exception as exc:
            if report.get("status") not in {"crawl_completed", "crawl_incomplete", "crawl_blocked"}:
                report["status"] = (
                    report["status"] if report["status"] in {"crawl_blocked", "crawl_incomplete"}
                    else "crawl_incomplete"
                )
                report["failure_reason"] = report.get("failure_reason") or (
                    f"{type(exc).__name__}: {exc}"
                )
                report["remaining_crawl_queue"] = report.get("remaining_crawl_queue", [])
                report["recommended_corrective_action"] = report.get(
                    "recommended_corrective_action"
                ) or "Verify Playwright browser availability and application access, then retry."
                self._crawl_reports[report_key] = report
            if report.get("status") == "crawl_incomplete":
                logger.warning(
                    "DOM discovery returned partial results url=%s pages_completed=%s "
                    "remaining=%s reason=%s",
                    url,
                    report.get("pages_completed", 0),
                    len(report.get("remaining_crawl_queue", [])),
                    report.get("failure_reason"),
                )
            else:
                logger.error(
                    "DOM discovery failed url=%s error=%s: %s",
                    url, type(exc).__name__, exc, exc_info=exc,
                )
            if isinstance(exc, AutomationError):
                raise
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
        crawl = self._crawls.get(request.crawl_id)
        if crawl is None:
            crawl_path = self.artifact_root / _safe_name(request.crawl_id) / "crawl-analysis.json"
            if crawl_path.is_file():
                crawl = json.loads(crawl_path.read_text(encoding="utf-8"))
                self._crawls[request.crawl_id] = crawl
        if crawl is None:
            crawl = await cache.get_json(cache.key("crawl", request.crawl_id))
            if crawl:
                self._crawls[request.crawl_id] = crawl
        if crawl is None:
            raise AutomationError(
                "A completed application crawl is required before script generation."
            )
        if str(crawl.get("workflow_id")) != str(request.workflow_id):
            raise AutomationError("The selected crawl belongs to a different workflow.")
        if _canonical_page_url(str(crawl.get("application_url"))) != _canonical_page_url(url):
            raise AutomationError("The selected crawl belongs to a different application URL.")
        crawl_report = dict(crawl.get("crawl_report") or {})
        usable_partial_crawl = bool(
            crawl.get("application_map", {}).get("pages")
            or crawl.get("discovered_elements")
            or int(crawl_report.get("pages_completed") or 0) > 0
        )
        if (
            crawl_report.get("status") == "crawl_blocked"
            or (
                crawl_report.get("status") != "crawl_completed"
                and not usable_partial_crawl
            )
        ):
            raise AutomationError(_crawl_failure_message(crawl_report))
        title = crawl.get("page_title")
        elements = [
            DiscoveredElement.model_validate(item)
            for item in crawl.get("discovered_elements", [])
        ]
        script_cache_key = cache.fingerprint(
            "scripts",
            {
                "generator_version": 9,
                "application_url": url,
                "requirement_version": requirement_version,
                "crawl_id": request.crawl_id,
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
                crawl_status="script_generation_completed",
                crawl_report=cached.get("crawl_report", {
                    "status": "crawl_completed",
                    "actual_application_reached": True,
                    "remaining_crawl_queue": [],
                }),
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
        logger.info(
            "Discovery complete: %d elements found. Building scripts for %d test cases.",
            len(elements), len(state.get("test_cases", [])),
        )
        generation_id = f"gen-{uuid.uuid4()}"
        directory = self.artifact_root / generation_id
        directory.mkdir(parents=True, exist_ok=False)
        element_dicts = [element.model_dump(mode="json") for element in elements]
        application_map = _application_map(url, title, element_dicts)
        stored_application_map = crawl.get("application_map") or {}
        application_map.update({
            "crawl_status": crawl_report["status"],
            "pages": (
                crawl_report.get("page_inventory")
                or stored_application_map.get("pages")
                or application_map["pages"]
            ),
            "relationships": (
                crawl_report.get("navigation_relationships")
                or stored_application_map.get("relationships")
                or application_map["relationships"]
            ),
            "page_count": (
                crawl_report.get("pages_completed")
                or stored_application_map.get("page_count")
                or application_map["page_count"]
            ),
            "pages_skipped": crawl_report.get("pages_skipped", []),
            "crawl_events": crawl_report.get("events", []),
        })
        application_map_version = _stable_version(application_map)
        self._mark_prior_script_lifecycle(
            request.workflow_id,
            requirement_version,
            application_map_version,
            {str(item.get("test_case_id")) for item in state.get("test_cases", [])},
        )
        crawl_report["events"].append("script_generation_started")
        scripts = []
        skipped_count = 0
        unsupported_requirements: list[dict[str, Any]] = []
        scenarios_by_id = {
            str(item.get("scenario_id")): item for item in state.get("scenarios", [])
        }
        configuration_terms = {
            "discount": "discount codes depend on configured promotions",
            "guest checkout": "guest checkout depends on store configuration",
            "review": "product reviews may be disabled or moderated",
            "filter": "product filters depend on catalog attributes",
            "email": "email delivery requires an external mailbox",
            "breadcrumb": "breadcrumbs depend on the active theme",
        }
        destructive_terms = {"delete account", "place order", "pay", "purchase", "logout"}
        for index, test_case in enumerate(state.get("test_cases", []), start=1):
            test_text = " ".join([
                str(test_case.get("title") or ""),
                str(test_case.get("description") or ""),
                *[
                    f"{step.get('action', '')} {step.get('expected_result', '')}"
                    for step in test_case.get("steps", [])
                ],
            ]).lower()
            scenario_obj = scenarios_by_id.get(str(test_case.get("scenario_id")), {})
            page_url, evidence_elements, has_matching_evidence = _select_ac_page_url(
                test_case=test_case,
                scenario=scenario_obj,
                base_url=url,
                elements=element_dicts,
            )

            if not has_matching_evidence:
                unsupported_requirements.append({
                    "test_case_id": str(test_case.get("test_case_id")),
                    "scenario_id": str(test_case.get("scenario_id")),
                    "classification": "blocked",
                    "reason": (
                        f"No matching crawl evidence directly associated with acceptance criteria "
                        f"was found for test case '{test_case.get('title')}'. Marked as BLOCKED."
                    ),
                })
                skipped_count += 1
                continue

            if _is_unsupported_post_registration_behavior(test_case, scenario_obj, evidence_elements):
                script_id = f"pw-{index:03d}-{_safe_name(str(test_case.get('test_case_id')))}"
                unsupported_reason = f"Post-registration expected behavior is not supported by acceptance criteria or page evidence for '{test_case.get('title')}'."
                scripts.append(
                    GeneratedScript(
                        script_id=script_id,
                        workflow_id=request.workflow_id,
                        test_case_id=str(test_case["test_case_id"]),
                        scenario_id=str(test_case["scenario_id"]),
                        name=test_case["title"],
                        application_url=url,
                        source=f"# Script BLOCKED: {unsupported_reason}",
                        download_path=f"/api/v1/automation/scripts/{generation_id}/{script_id}/download",
                        application_map_version=application_map_version,
                        requirement_version=requirement_version,
                        lifecycle_status="Blocked",
                        page_url=page_url,
                        page_elements=evidence_elements,
                        executable_steps=test_case.get("steps", []),
                        requirement_ids=[
                            str(item) for item in test_case.get("requirement_ids", [])
                        ],
                        user_story_ids=[
                            str(item)
                            for item in scenarios_by_id.get(
                                str(test_case.get("scenario_id")), {}
                            ).get("user_story_ids", [])
                        ],
                    )
                )
                unsupported_requirements.append({
                    "test_case_id": str(test_case.get("test_case_id")),
                    "scenario_id": str(test_case.get("scenario_id")),
                    "classification": "blocked",
                    "reason": f"{unsupported_reason} Marked as BLOCKED.",
                })
                continue
            dependency = next(
                (reason for term, reason in configuration_terms.items() if term in test_text),
                None,
            )
            destructive = next(
                (term for term in destructive_terms if term in test_text),
                None,
            )
            if destructive:
                unsupported_requirements.append({
                    "test_case_id": str(test_case.get("test_case_id")),
                    "classification": "unsupported_or_destructive_workflow",
                    "reason": f"Workflow contains destructive action: {destructive}",
                })
                skipped_count += 1
                continue
            invalid_steps = _invalid_test_steps(test_case, evidence_elements)
            invalid_step_numbers = {
                item.get("step_number") for item in invalid_steps
            }
            executable_steps = [
                step
                for step in test_case.get("steps", [])
                if step.get("step_number") not in invalid_step_numbers
                and _step_execution_kind(str(step.get("action") or "")) != "invalid"
            ]
            if invalid_steps:
                unsupported_requirements.append({
                    "test_case_id": str(test_case.get("test_case_id")),
                    "classification": (
                        "not_testable_due_to_configuration"
                        if dependency else "invalid_test_step"
                    ),
                    "reason": dependency or (
                        "One or more steps are not executable with crawl-verified "
                        "Playwright actions or assertions."
                    ),
                    "invalid_steps": invalid_steps,
                })
            if not executable_steps:
                skipped_count += 1
                continue
            executable_test_case = {
                **test_case,
                "steps": executable_steps,
            }
            script_id = f"pw-{index:03d}-{_safe_name(str(test_case.get('test_case_id')))}"
            path = directory / f"{script_id}{SCRIPT_ARTIFACT_SUFFIX}"
            try:
                source = _python_source(
                    executable_test_case, page_url, evidence_elements
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
                    application_map_version=application_map_version,
                    requirement_version=requirement_version,
                    lifecycle_status="Valid",
                    page_url=page_url,
                    page_elements=evidence_elements,
                    executable_steps=executable_steps,
                    requirement_ids=[
                        str(item) for item in test_case.get("requirement_ids", [])
                    ],
                    user_story_ids=[
                        str(item)
                        for item in scenarios_by_id.get(
                            str(test_case.get("scenario_id")), {}
                        ).get("user_story_ids", [])
                    ],
                )
            )
        if crawl_report.get("status") == "crawl_incomplete":
            represented_pages = {
                _canonical_page_url(str(script.page_url))
                for script in scripts
                if script.page_url
            }
            for page_index, page_info in enumerate(
                application_map.get("pages", []), start=1
            ):
                page_url = _canonical_page_url(
                    str(page_info.get("final_url") or page_info.get("url") or url)
                )
                if page_url in represented_pages:
                    continue
                page_elements = list(page_info.get("elements") or [])
                page_name = (
                    str(page_info.get("title") or "").strip()
                    or urlsplit(page_url).path.strip("/")
                    or "home"
                )
                script_id = (
                    f"partial-page-{page_index:03d}-{_safe_name(page_name)}"
                )
                source = _page_script_source(
                    f"Successfully crawled page {page_name}",
                    page_url,
                    page_elements,
                )
                try:
                    _validate_generated_source(source)
                except (SyntaxError, ValueError) as source_err:
                    logger.warning(
                        "Partial page script skipped page_url=%s error=%s: %s",
                        page_url,
                        type(source_err).__name__,
                        source_err,
                    )
                    skipped_count += 1
                    continue
                (
                    directory / f"{script_id}{SCRIPT_ARTIFACT_SUFFIX}"
                ).write_text(source, encoding="utf-8")
                scripts.append(
                    GeneratedScript(
                        script_id=script_id,
                        workflow_id=request.workflow_id,
                        test_case_id=f"CRAWL-{page_index:03d}",
                        scenario_id="URL-CRAWL",
                        name=f"Successfully crawled page: {page_name}",
                        application_url=url,
                        source=source,
                        download_path=(
                            f"/api/v1/automation/scripts/{generation_id}/"
                            f"{script_id}/download"
                        ),
                        application_map_version=application_map_version,
                        requirement_version=requirement_version,
                        lifecycle_status="Valid",
                        page_url=page_url,
                        page_elements=page_elements,
                        executable_steps=[{
                            "step_number": 1,
                            "action": f"Open {page_url}",
                            "expected_result": "The successfully crawled page is visible",
                        }],
                    )
                )
                represented_pages.add(page_url)
        crawl_report["requirement_evidence"] = {
            "supported_test_cases": [script.test_case_id for script in scripts],
            "unsupported_test_cases": unsupported_requirements,
        }
        crawl_report["events"].append("script_generation_completed")
        logger.info(
            "generate() complete: %d scripts built, %d skipped. generation_id=%s",
            len(scripts), skipped_count, generation_id,
        )
        if not scripts:
            crawl_report["script_generation_message"] = (
                "No scripts available: the backend confirmed that zero valid scripts "
                "could be generated from the preserved crawl data."
            )
        response = ScriptGenerationResponse(
            generation_id=generation_id,
            application_url=url,
            reachable=True,
            page_title=title,
            discovered_elements=elements,
            application_map=application_map,
            application_map_version=application_map_version,
            requirement_version=requirement_version,
            crawl_status="script_generation_completed",
            crawl_report=crawl_report,
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
                "crawl_status": "crawl_completed",
                "crawl_report": crawl_report,
                "scripts": [item.model_dump(mode="json") for item in scripts],
            },
            settings.redis_script_ttl_seconds,
        )
        return response
    async def analyze_application(
        self,
        request: CrawlApplicationRequest,
        *,
        _dedicated_loop: bool = False,
        cancel_event: Event | None = None,
    ) -> CrawlAnalysisResponse:
        if sys.platform == "win32" and not settings.app_mock_mode and not _dedicated_loop:
            return await _on_playwright_loop(
                lambda: self.analyze_application(
                    request,
                    _dedicated_loop=True,
                    cancel_event=cancel_event,
                )
            )
        state = workflow_service.get(request.workflow_id)
        if state.get("status") != "completed":
            raise AutomationError("Application crawling requires a completed workflow.")
        url = str(request.application_url)
        await self._validate_url(url)
        testing_scope = request.testing_scope
        page_limit = 1 if testing_scope == "specific_page" else request.page_limit
        depth_limit = 0 if testing_scope == "specific_page" else request.depth_limit
        original_limits = (
            settings.automation_crawl_page_limit,
            settings.automation_crawl_depth_limit,
            settings.automation_crawl_timeout_seconds,
            settings.automation_crawl_repeated_state_limit,
        )
        settings.automation_crawl_page_limit = page_limit
        settings.automation_crawl_depth_limit = depth_limit
        settings.automation_crawl_timeout_seconds = request.max_execution_time_seconds
        settings.automation_crawl_repeated_state_limit = request.repeated_state_limit
        title: str | None = None
        elements: list[DiscoveredElement] = []
        try:
            try:
                try:
                    title, elements = await self._discover(
                        url,
                        cancel_event=cancel_event,
                        authentication=request.authentication,
                        testing_scope=testing_scope,
                    )
                except TypeError:
                    title, elements = await self._discover(url)
                report = self._completed_crawl_report(url, title, elements)
            except AutomationError:
                report = self._crawl_reports.get(_canonical_page_url(url), {})
                for page_info in report.get("page_inventory", []):
                    elements.extend(
                        DiscoveredElement.model_validate(item)
                        for item in page_info.get("elements", [])
                    )
                title = (
                    report.get("page_inventory", [{}])[0].get("title")
                    if report.get("page_inventory") else None
                )
            report = report or self._crawl_reports.get(_canonical_page_url(url), {})
        finally:
            (
                settings.automation_crawl_page_limit,
                settings.automation_crawl_depth_limit,
                settings.automation_crawl_timeout_seconds,
                settings.automation_crawl_repeated_state_limit,
            ) = original_limits
        crawl_id = f"crawl-{uuid.uuid4()}"
        directory = self.artifact_root / crawl_id
        directory.mkdir(parents=True, exist_ok=False)
        element_dicts = [item.model_dump(mode="json") for item in elements]
        application_map = _application_map(url, title, element_dicts)
        application_map.update({
            "crawl_status": report.get("status", "crawl_incomplete"),
            "pages": report.get("page_inventory") or application_map["pages"],
            "relationships": (
                report.get("navigation_relationships")
                or application_map["relationships"]
            ),
            "page_count": report.get("pages_completed", application_map["page_count"]),
            "pages_skipped": report.get("pages_skipped", []),
            "crawl_events": report.get("events", []),
        })
        stored = {
            "crawl_id": crawl_id,
            "workflow_id": str(request.workflow_id),
            "application_url": url,
            "page_title": title,
            "crawl_report": report,
            "application_map": application_map,
            "discovered_elements": element_dicts,
        }
        self._crawls[crawl_id] = stored
        (directory / "crawl-analysis.json").write_text(
            json.dumps(stored, default=str, indent=2), encoding="utf-8"
        )
        await cache.set_json(
            cache.key("crawl", crawl_id),
            stored,
            settings.redis_crawl_ttl_seconds,
        )
        return CrawlAnalysisResponse(
            crawl_id=crawl_id,
            application_url=url,
            crawl_status=report.get("status", "crawl_incomplete"),
            page_title=title,
            pages_crawled=int(report.get("pages_completed", 0)),
            elements_found=len(elements),
            crawl_report=report,
            application_map=application_map,
            discovered_elements=elements,
        )

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

    async def crawl_and_generate(
        self,
        request: CrawlAndGenerateRequest,
        *,
        _dedicated_loop: bool = False,
        cancel_event: Event | None = None,
    ) -> CrawlGenerationResponse:
        """Standalone URL crawl → Playwright script generation.

        Validates the URL, uses Playwright to crawl all same-origin pages up to
        the configured limits, then generates one verified test script per page.
        No workflow_id or pre-existing test cases are required.
        """
        if sys.platform == "win32" and not settings.app_mock_mode and not _dedicated_loop:
            return await _on_playwright_loop(
                lambda: self.crawl_and_generate(
                    request,
                    _dedicated_loop=True,
                    cancel_event=cancel_event,
                )
            )

        url = str(request.url)
        testing_scope = request.testing_scope
        page_limit = 1 if testing_scope == "specific_page" else request.page_limit
        depth_limit = 0 if testing_scope == "specific_page" else request.depth_limit

        logger.info("crawl_and_generate() start url=%s page_limit=%d depth_limit=%d testing_scope=%s", url, page_limit, depth_limit, testing_scope)

        await self._validate_url(url)

        # Temporarily override crawl limits for this request
        original_page_limit = settings.automation_crawl_page_limit
        original_depth_limit = settings.automation_crawl_depth_limit
        original_timeout = settings.automation_crawl_timeout_seconds
        original_repeated_state_limit = settings.automation_crawl_repeated_state_limit
        settings.automation_crawl_page_limit = page_limit
        settings.automation_crawl_depth_limit = depth_limit
        settings.automation_crawl_timeout_seconds = request.max_execution_time_seconds
        settings.automation_crawl_repeated_state_limit = request.repeated_state_limit
        title: str | None = None
        elements: list[DiscoveredElement] = []
        try:
            try:
                try:
                    title, elements = await self._discover(
                        url,
                        cancel_event=cancel_event,
                        authentication=request.authentication,
                        testing_scope=testing_scope,
                    )
                except TypeError:
                    title, elements = await self._discover(url)
                crawl_report = self._completed_crawl_report(url, title, elements)
            except AutomationError:
                crawl_report = self._crawl_reports.get(_canonical_page_url(url), {})
                if not crawl_report:
                    raise
                inventory = crawl_report.get("page_inventory", [])
                title = inventory[0].get("title") if inventory else None
                captured_elements = [
                    item
                    for page_info in inventory
                    for item in page_info.get("elements", [])
                ]
                unique_elements = {
                    (
                        str(item.get("page_url") or url),
                        str(
                            item.get("test_id")
                            or item.get("element_id")
                            or item.get("css_selector")
                        ),
                    ): item
                    for item in captured_elements
                }
                elements = [
                    DiscoveredElement.model_validate(item)
                    for item in unique_elements.values()
                ]
        finally:
            settings.automation_crawl_page_limit = original_page_limit
            settings.automation_crawl_depth_limit = original_depth_limit
            settings.automation_crawl_timeout_seconds = original_timeout
            settings.automation_crawl_repeated_state_limit = original_repeated_state_limit

        crawl_id = f"crawl-{uuid.uuid4()}"
        directory = self.artifact_root / crawl_id
        directory.mkdir(parents=True, exist_ok=True)

        element_dicts = [item.model_dump(mode="json") for item in elements]
        application_map = _application_map(url, title, element_dicts)
        application_map.update({
            "crawl_status": crawl_report.get("status", "crawl_incomplete"),
            "pages": crawl_report.get("page_inventory") or application_map["pages"],
            "relationships": (
                crawl_report.get("navigation_relationships")
                or application_map["relationships"]
            ),
            "page_count": crawl_report.get("pages_completed", application_map["page_count"]),
            "pages_skipped": crawl_report.get("pages_skipped", []),
            "crawl_events": crawl_report.get("events", []),
        })
        if crawl_report.get("status") == "crawl_blocked":
            response = CrawlGenerationResponse(
                crawl_id=crawl_id,
                url=url,
                page_title=title,
                pages_crawled=0,
                elements_found=0,
                crawl_status="crawl_blocked",
                crawl_report=crawl_report,
                scripts=[],
                discovered_elements=[],
                application_map=application_map,
            )
            (directory / "crawl.json").write_text(
                json.dumps(response.model_dump(mode="json"), default=str, indent=2),
                encoding="utf-8",
            )
            return response
        if crawl_report.get("status") == "crawl_incomplete":
            crawl_report["events"].append("partial_script_generation_started")
        crawl_report["events"].append("script_generation_started")

        scripts: list[GeneratedScript] = []
        skipped_count = 0

        for index, page_info in enumerate(application_map.get("pages", []), start=1):
            page_url = str(page_info.get("url") or url)
            page_elements = list(page_info.get("elements") or [])
            page_name = urlsplit(page_url).path.strip("/") or title or "home"
            script_id = f"crawl-page-{index:03d}-{_safe_name(page_name)}"
            path = directory / f"{script_id}{SCRIPT_ARTIFACT_SUFFIX}"
            test_case_label = f"Page: {page_name}"
            try:
                source = _page_script_source(test_case_label, page_url, page_elements)
                _validate_generated_source(source)
            except (SyntaxError, ValueError) as source_err:
                logger.warning(
                    "Crawl script skipped – validation failed script_id=%s error=%s: %s",
                    script_id, type(source_err).__name__, source_err,
                )
                skipped_count += 1
                continue
            path.write_text(source, encoding="utf-8")
            scripts.append(
                GeneratedScript(
                    script_id=script_id,
                    workflow_id=uuid.UUID(int=0),  # sentinel — no workflow
                    test_case_id=f"CRAWL-{index:03d}",
                    scenario_id="URL-CRAWL",
                    name=test_case_label,
                    application_url=url,
                    source=source,
                    download_path=f"/api/v1/automation/url-crawl/{crawl_id}/{script_id}/download",
                    page_url=page_url,
                    page_elements=page_elements,
                )
            )

        logger.info(
            "crawl_and_generate() complete crawl_id=%s scripts=%d skipped=%d",
            crawl_id, len(scripts), skipped_count,
        )

        if not scripts and not crawl_report.get("stop_requested"):
            raise AutomationError(
                "No scripts could be generated from the crawled URL. "
                "Ensure the URL loads a real UI and is not behind a login wall."
            )
        crawl_report["events"].append("script_generation_completed")
        if crawl_report.get("status") == "crawl_incomplete":
            crawl_report["events"].append("partial_script_generation_completed")

        response = CrawlGenerationResponse(
            crawl_id=crawl_id,
            url=url,
            page_title=title,
            pages_crawled=len(application_map.get("pages", [])),
            elements_found=len(elements),
            crawl_status=crawl_report["status"],
            crawl_report=crawl_report,
            scripts=scripts,
            discovered_elements=elements,
            application_map=application_map,
        )

        # Persist manifest for download route
        (directory / "crawl.json").write_text(
            json.dumps(response.model_dump(mode="json"), default=str, indent=2),
            encoding="utf-8",
        )

        # Cache the crawl generation keyed by crawl_id
        self._generations[crawl_id] = {
            "response": response,
            "workflow": {},
            "directory": directory,
            "learned_locators": {},
        }
        await cache.set_json(
            cache.key("crawl-generation", crawl_id),
            {"response": response.model_dump(mode="json")},
            settings.redis_crawl_ttl_seconds,
        )

        return response

    async def crawl_script_path(self, crawl_id: str, script_id: str) -> Path:
        """Resolve the .pwscript file for a URL-crawl download."""
        safe_crawl = _safe_name(crawl_id)
        safe_script = _safe_name(script_id)
        path = self.artifact_root / safe_crawl / f"{safe_script}{SCRIPT_ARTIFACT_SUFFIX}"
        if not path.is_file():
            cached = await cache.get_json(cache.key("crawl-generation", crawl_id))
            scripts = (cached or {}).get("response", {}).get("scripts", [])
            stored = next(
                (item for item in scripts if item.get("script_id") == script_id),
                None,
            )
            if not stored or not stored.get("source"):
                raise AutomationNotFound(f"Crawl script not found: {crawl_id}/{script_id}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(stored["source"]), encoding="utf-8")
        return path

    def evidence_artifact_path(self, artifact_path: str) -> Path:
        """Resolve a report artifact without allowing access outside the artifact root."""
        root = self.artifact_root.resolve()
        candidate = Path(artifact_path)
        candidates = [candidate.resolve()] if candidate.is_absolute() else [
            candidate.resolve(),
            (root / candidate).resolve(),
        ]
        for resolved in candidates:
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            if resolved.is_file():
                return resolved
        raise AutomationNotFound("Evidence artifact was not found.")

    def evidence_artifact_pdf(self, artifact_path: str) -> tuple[io.BytesIO, str]:
        """Convert a supported screenshot artifact to a downloadable PDF."""
        from PIL import Image

        path = self.evidence_artifact_path(artifact_path)
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            raise AutomationError("Only screenshot image artifacts can be converted to PDF.")
        with Image.open(path) as source:
            frame = source.convert("RGBA")
            background = Image.new("RGB", frame.size, "white")
            background.paste(frame, mask=frame.getchannel("A"))
            output = io.BytesIO()
            background.save(output, format="PDF", resolution=144.0)
        output.seek(0)
        return output, f"{path.stem}.pdf"

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
        # The full source is stored in the Redis generation manifest. Rebuild
        # the download artifact after a restart or local artifact cleanup.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(script.source, encoding="utf-8")
        return path

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
            if element.get("aria_label") and hasattr(page, "locator"):
                candidates.append(
                    page.locator(
                        f"[aria-label={json.dumps(str(element['aria_label']))}]"
                    )
                )
            if element.get("role") and element.get("name"):
                candidates.append(
                    page.get_by_role(element["role"], name=element["name"], exact=True)
                )
            if element.get("label"):
                candidates.append(page.get_by_label(element["label"], exact=True))
            if element.get("placeholder"):
                candidates.append(
                    page.get_by_placeholder(element["placeholder"], exact=True)
                )
            if element.get("element_id") and hasattr(page, "locator"):
                candidates.append(page.locator(f"[id={json.dumps(str(element['element_id']))}]"))
            if element.get("name") and hasattr(page, "locator"):
                candidates.append(page.locator(f"[name={json.dumps(str(element['name']))}]"))
            if (
                element.get("css_selector")
                and element.get("locator_validated")
                and hasattr(page, "locator")
            ):
                candidates.append(page.locator(element["css_selector"]))
            if element.get("visible_text"):
                candidates.append(
                    page.get_by_text(element["visible_text"], exact=True)
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
        # With crawl evidence, never invent broad selectors. Every candidate
        # must be one of the alternate locators verified during discovery.
        if not discovered_elements or not any(
            element.get("locator_validated") for element in discovered_elements
        ):
            # Compatibility for legacy/injected catalogues created before
            # crawl-time locator verification was recorded. New crawls never
            # enter this branch.
            for role in roles:
                candidates.append(page.get_by_role(role, name=pattern))
            candidates.extend([
                page.get_by_label(pattern),
                page.get_by_placeholder(pattern),
                page.get_by_test_id(phrase),
                page.get_by_text(phrase, exact=True),
            ])
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

    @staticmethod
    def _context_element(
        action: str, elements: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        words = _meaningful_words(AutomationService._locator_phrase(action))
        ranked: list[tuple[int, dict[str, Any]]] = []
        for element in elements:
            identity = " ".join(
                str(element.get(key) or "")
                for key in (
                    "test_id", "aria_label", "role", "name", "label",
                    "placeholder", "element_id", "visible_text", "href",
                )
            )
            score = len(words & _meaningful_words(identity))
            if score:
                ranked.append((score, element))
        return max(ranked, key=lambda item: item[0])[1] if ranked else None

    @staticmethod
    def _locator_evidence(
        element: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if not element:
            return {}, []
        details = {
            "xpath": element.get("xpath"),
            "css_selector": element.get("css_selector"),
            "role": element.get("role"),
            "accessible_name": element.get("name"),
            "aria_label": element.get("aria_label"),
            "label": element.get("label"),
            "placeholder": element.get("placeholder"),
            "test_id": element.get("test_id"),
            "stable_id": element.get("element_id"),
            "stable_name": element.get("name"),
            "verified_during_crawl": bool(element.get("locator_validated")),
            "discovered_page_url": element.get("page_url"),
        }
        ordered = (
            ("test_id", element.get("test_id")),
            ("aria_label", element.get("aria_label")),
            (
                "role_and_accessible_name",
                (
                    f"{element.get('role')}:{element.get('name')}"
                    if element.get("role") and element.get("name")
                    else None
                ),
            ),
            ("label", element.get("label")),
            ("placeholder", element.get("placeholder")),
            ("stable_id", element.get("element_id")),
            ("stable_name", element.get("name")),
            (
                "verified_css",
                element.get("css_selector")
                if element.get("locator_validated")
                else None,
            ),
            ("exact_visible_text", element.get("visible_text")),
        )
        attempts = [
            {
                "strategy": strategy,
                "locator": str(value),
                "source": "crawl_evidence",
                "attempted": True,
            }
            for strategy, value in ordered
            if value
        ]
        return details, attempts

    @staticmethod
    def _failure_stage(action: str, category: str) -> str:
        lowered = action.lower()
        if category in {"Generated Script Defect", "Invalid Test Step"}:
            return "generated_test_step"
        if category in {"Navigation Failure", "Blocked Page"}:
            return "navigation"
        if category == "Page Load Timeout":
            return "page_loading"
        if category == "Assertion Failure":
            return "assertion_validation"
        if category == "Application State Failure":
            return "application_state_setup"
        if category == "API Failure":
            return "api_response"
        if category == "Authentication Failure":
            return "authentication"
        if any(token in lowered for token in ("enter", "type", "fill")):
            return "entering_data"
        if any(token in lowered for token in ("select", "choose")):
            return "selecting_option"
        if any(token in lowered for token in ("click", "press", "check", "uncheck")):
            return "clicking"
        if "wait" in lowered:
            return "waiting_for_dynamic_content"
        return "locating_element"

    @staticmethod
    def _locator_diagnosis(
        element: dict[str, Any] | None, current_url: str
    ) -> str | None:
        if not element:
            return "No crawl-verified locator was linked to the generated action."
        discovered_url = str(element.get("page_url") or "")
        if (
            discovered_url
            and current_url
            and _canonical_page_url(discovered_url)
            != _canonical_page_url(current_url)
        ):
            return (
                f"The element belongs to {discovered_url}, but execution was on "
                f"{current_url}."
            )
        css = str(element.get("css_selector") or "").strip()
        if css in {"a", "div", "span", "button", "input"}:
            return f"The CSS selector {css!r} is too generic."
        if "nth-of-type" in css or "nth-child" in css:
            return f"The CSS selector {css!r} is structurally unstable."
        if css and not element.get("locator_validated"):
            return f"The CSS selector {css!r} was not verified during crawling."
        return None

    @staticmethod
    def _masked_input_value(action: str) -> str | None:
        values = re.findall(r"['\"]([^'\"]+)['\"]", action)
        if not values:
            return None
        if re.search(r"password|token|secret|api.?key|otp|card|cvv", action, re.I):
            return "********"
        return values[-1]

    async def _restore_crawl_context(
        self,
        page: Any,
        element: dict[str, Any],
        fallback_url: str,
        credentials: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        expected_url = _canonical_page_url(
            str(element.get("page_url") or fallback_url)
        )
        path = [
            _canonical_page_url(str(url))
            for url in (element.get("navigation_path") or [expected_url])
            if url
        ]
        if expected_url not in path:
            path.append(expected_url)

        # Replay the recorded route in order. Direct navigation is used because
        # every URL was already verified as reachable by the crawler.
        for target in path:
            if _canonical_page_url(page.url) == target:
                continue
            await page.goto(
                target,
                wait_until="domcontentloaded",
                timeout=int(settings.automation_navigation_timeout_seconds * 1000),
            )
            await self._crawl_wait(page)
            await self._authenticate_if_required(page, credentials, target)
        if _canonical_page_url(page.url) != expected_url:
            await page.goto(
                expected_url,
                wait_until="domcontentloaded",
                timeout=int(settings.automation_navigation_timeout_seconds * 1000),
            )
            await self._crawl_wait(page)
            await self._authenticate_if_required(page, credentials, expected_url)
        await self._validate_navigation(page, expected_url)

        expected_title = str(element.get("page_title") or "").strip()
        if expected_title:
            current_title = (await page.title()).strip()
            if current_title.casefold() != expected_title.casefold():
                raise LookupError(
                    f"Page title differs from crawl evidence: expected "
                    f"{expected_title!r}, got {current_title!r}"
                )

        state = element.get("application_state") or {}
        for field in state.get("form_values", []):
            selector = None
            if field.get("test_id"):
                selector = f"[data-testid={json.dumps(str(field['test_id']))}]"
            elif field.get("element_id"):
                selector = f"[id={json.dumps(str(field['element_id']))}]"
            elif field.get("name"):
                selector = f"[name={json.dumps(str(field['name']))}]"
            if not selector:
                continue
            try:
                control = page.locator(selector).first
                if not await control.count() or not await control.is_visible():
                    continue
                tag = await control.evaluate("el => el.tagName.toLowerCase()")
                input_type = await control.get_attribute("type")
                if tag == "select":
                    values = field.get("selected_values") or []
                    if values:
                        await control.select_option(values)
                elif input_type in {"checkbox", "radio"}:
                    await control.set_checked(bool(field.get("checked")))
                elif field.get("value") is not None:
                    await control.fill(str(field["value"]))
            except Exception:
                continue
        for selector in state.get("expanded_selectors", []):
            try:
                control = page.locator(selector).first
                if await control.count() and await control.is_visible():
                    expanded = await control.get_attribute("aria-expanded")
                    if expanded != "true":
                        await control.scroll_into_view_if_needed()
                        await control.click()
            except Exception:
                # A recorded expansion is best-effort; alternate verified
                # locators for the actual action are still attempted below.
                continue
        await page.evaluate(
            """async () => {
              const step = Math.max(300, Math.floor(innerHeight * .8));
              for (let y=0; y<document.body.scrollHeight; y+=step) {
                scrollTo(0, y); await new Promise(r => setTimeout(r, 30));
              }
              scrollTo(0, 0);
            }"""
        )
        await self._crawl_wait(page)
        title = await page.title()
        now = datetime.now(timezone.utc).isoformat()
        return [
            {
                **item,
                "page_url": _canonical_page_url(page.url),
                "page_title": title,
                "parent_page": element.get("parent_page"),
                "navigation_path": path,
                "application_state": state,
                "discovery_timestamp": now,
            }
            for item in await self._capture_interactive_elements(page)
        ]

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
        values = re.findall(r"['\"]([^'\"]*)['\"]", action)
        desired = values[-1] if values else None
        roles: tuple[str, ...]
        interactive_tokens = (
            "click", "press", "select", "choose", "check", "uncheck",
            "enter", "type", "fill", "radio", "hover", "wait for", "wait until",
        )
        if not any(token in lowered for token in interactive_tokens):
            raise InvalidGeneratedStepError(
                f"Invalid generated test step: {action!r} has no executable "
                "action or explicit interaction value."
            )
        if any(token in lowered for token in ("select", "choose")):
            roles = ("combobox", "radio")
        elif any(token in lowered for token in ("check", "uncheck", "radio")):
            roles = ("checkbox", "radio")
        elif any(token in lowered for token in ("click", "press")):
            roles = ("button", "link")
        elif "hover" in lowered or "wait " in lowered:
            roles = ()
        elif any(token in lowered for token in ("enter", "type", "fill")):
            if desired is None:
                if any(term in lowered for term in ("empty", "blank", "clear")):
                    desired = ""
                elif "email" in lowered:
                    desired = "user@example.com"
                elif "password" in lowered:
                    desired = "Password123!"
                elif "name" in lowered:
                    desired = "John Doe"
                elif "phone" in lowered or "mobile" in lowered:
                    desired = "1234567890"
                else:
                    desired = "TestInput123"
            roles = ("textbox", "spinbutton")

        else:
            roles = ("button", "link")

        locators = await self._resolve_locators(
            page, phrase, roles, discovered_elements
        )
        last_error: Exception | None = None
        for locator, description in locators:
            try:
                if hasattr(locator, "scroll_into_view_if_needed"):
                    await locator.scroll_into_view_if_needed(
                        timeout=int(settings.automation_action_timeout_seconds * 1000)
                    )
                if "wait for" in lowered or "wait until" in lowered:
                    await locator.wait_for(
                        state="visible",
                        timeout=int(settings.automation_action_timeout_seconds * 1000),
                    )
                elif "hover" in lowered:
                    await locator.hover(
                        timeout=int(settings.automation_action_timeout_seconds * 1000)
                    )
                elif "press" in lowered:
                    key_match = re.search(
                        r"\b(Enter|Escape|Tab|Space|Arrow(?:Up|Down|Left|Right))\b",
                        action,
                        re.I,
                    )
                    if not key_match:
                        raise InvalidGeneratedStepError(
                            f"Press action has no supported key: {action!r}"
                        )
                    await locator.press(
                        key_match.group(1),
                        timeout=int(settings.automation_action_timeout_seconds * 1000),
                    )
                elif any(token in lowered for token in ("select", "choose")):
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
            "seacrawl-locator",
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

    async def _authenticate_if_required(
        self,
        page: Any,
        credentials: Any,
        protected_url: str,
    ) -> dict[str, Any]:
        evidence = {
            "required": False,
            "attempted": False,
            "succeeded": False,
            "redirected_url": page.url,
            "expected_protected_url": protected_url,
        }
        auth_mode = getattr(credentials, "auth_mode", None) if credentials else None
        if isinstance(credentials, dict):
            auth_mode = credentials.get("auth_mode", auth_mode)

        ident_val = None
        pass_val = None
        if credentials:
            if hasattr(credentials, "get_identifier") and credentials.get_identifier:
                ident_val = credentials.get_identifier
            elif isinstance(credentials, dict):
                ident_val = credentials.get("identifier") or credentials.get("email") or credentials.get("username")
            if hasattr(credentials, "password") and credentials.password:
                pass_val = credentials.password.get_secret_value() if hasattr(credentials.password, "get_secret_value") else str(credentials.password)
            elif isinstance(credentials, dict):
                p = credentials.get("password")
                pass_val = p.get_secret_value() if hasattr(p, "get_secret_value") else (str(p) if p else None)

        if auth_mode == "no_auth" or not credentials or (auth_mode != "credentials" and not (ident_val and pass_val)):
            return evidence

        password = page.locator("input[type='password']").first
        login_url = bool(
            re.search(r"/(?:login|signin|sign-in|log-in|auth)(?:/|$|\?)", page.url, re.I)
        )
        password_visible = bool(
            await password.count() and await password.is_visible()
        )
        evidence["required"] = login_url or password_visible
        if not evidence["required"]:
            return evidence

        if not ident_val or not pass_val:
            raise PlaywrightAuthenticationError(
                f"Authentication Failed: {protected_url} redirected to {page.url}, "
                "but Identifier and Password were not provided."
            )
        evidence["attempted"] = True

        email_candidates = [
            page.get_by_label(re.compile(r"email|username|identifier|user|login|id", re.I)),
            page.get_by_placeholder(re.compile(r"email|username|identifier|user|login|id", re.I)),
            page.locator("input[type='email']"),
            page.locator("input[name='email'],input[name='username'],input[name='identifier'],input[name='user'],input[name='login']"),
            page.locator("input[type='text']"),
        ]
        email = None
        for candidate in email_candidates:
            if await candidate.count() and await candidate.first.is_visible():
                email = candidate.first
                break
        if email is None or not password_visible:
            raise PlaywrightAuthenticationError(
                "Authentication Failed: the login page did not expose visible "
                "identifier and password fields."
            )
        await email.fill(
            str(ident_val),
            timeout=int(settings.automation_action_timeout_seconds * 1000),
        )
        await password.fill(
            str(pass_val),
            timeout=int(settings.automation_action_timeout_seconds * 1000),
        )
        submit_candidates = [
            page.get_by_role(
                "button",
                name=re.compile(r"log\s*in|sign\s*in|continue|submit", re.I),
            ),
            page.locator("button[type='submit'],input[type='submit']"),
        ]
        submitted = False
        for candidate in submit_candidates:
            if await candidate.count() and await candidate.first.is_visible():
                await candidate.first.click(
                    timeout=int(settings.automation_action_timeout_seconds * 1000)
                )
                submitted = True
                break
        if not submitted:
            raise PlaywrightAuthenticationError(
                "Authentication Failed: no visible login submit control was found."
            )
        # Wait for navigation / state settlement after form submit
        try:
            await page.wait_for_load_state(
                "domcontentloaded",
                timeout=int(settings.automation_navigation_timeout_seconds * 1000),
            )
        except Exception:
            pass

        # Give navigation a brief moment to settle if URL change or async redirect is in progress
        for _ in range(10):
            await page.wait_for_timeout(300)
            cur_url = page.url
            pw_count = await page.locator("input[type='password']").count()
            pw_vis = bool(pw_count and await page.locator("input[type='password']").first.is_visible())
            is_login_path = bool(re.search(r"/(?:login|signin|sign-in|log-in|auth)(?:/|$|\?)", cur_url, re.I))
            if not is_login_path or not pw_vis:
                break

        await self._crawl_wait(page)
        password_visible = bool(
            await page.locator("input[type='password']").count() and await page.locator("input[type='password']").first.is_visible()
        )
        is_login_page = bool(re.search(r"/(?:login|signin|sign-in|log-in|auth)(?:/|$|\?)", page.url, re.I))

        page_content = await page.content() if hasattr(page, "content") else ""
        has_success_text = bool(re.search(r"logged in|logged-in|secure area|welcome|dashboard|logout", page_content, re.I))
        has_success_banner = bool(await page.locator("#flash.success,.flash.success,.alert-success,.success").count())
        has_logout_link = bool(await page.locator("a[href*='logout'],button:has-text('Logout'),button:has-text('Log out')").count())
        is_authenticated_state = (not is_login_page and not password_visible) or has_success_text or has_success_banner or has_logout_link

        if not is_authenticated_state and (password_visible or is_login_page):
            messages = await page.locator(
                "[role='alert'],#flash,.flash.error,.validation-summary-errors,.field-validation-error"
            ).all_inner_texts()
            msg_str = " ".join([m.strip() for m in messages if m.strip()])
            raise PlaywrightAuthenticationError(
                "Authentication Failed: login was submitted but the application "
                f"remained on {page.url}. Message: {msg_str[:1000] or 'none'}"
            )

        is_protected_login = bool(re.search(r"/(?:login|signin|sign-in|log-in)(?:/|$|\?)", protected_url, re.I))
        if not is_protected_login and _canonical_page_url(page.url) != _canonical_page_url(protected_url):
            await page.goto(
                protected_url,
                wait_until="domcontentloaded",
                timeout=int(settings.automation_navigation_timeout_seconds * 1000),
            )
            await self._crawl_wait(page)
            if await page.locator("input[type='password']").count():
                visible_password = page.locator("input[type='password']").first
                if await visible_password.is_visible():
                    raise PlaywrightAuthenticationError(
                        "Authentication Failed: protected page still displays a password field."
                    )

        evidence.update({"succeeded": True, "redirected_url": page.url})
        return evidence

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
        if expected_url_prefix and (
            _canonical_page_url(page.url)
            != _canonical_page_url(expected_url_prefix)
        ):
            raise AutomationError(
                "Navigation failure: current URL does not match the crawl page; "
                f"expected={expected_url_prefix!r} current={page.url!r}"
            )

    async def _expected_page_evidence_present(
        self,
        page: Any,
        expected_url: str,
        elements: list[dict[str, Any]],
    ) -> bool:
        expected = _canonical_page_url(expected_url)
        page_elements = [
            item
            for item in elements
            if _canonical_page_url(str(item.get("page_url") or expected)) == expected
        ]
        if not page_elements:
            return True
        for item in page_elements[:50]:
            identity = str(
                item.get("test_id")
                or item.get("aria_label")
                or item.get("label")
                or item.get("name")
                or item.get("visible_text")
                or ""
            )
            if not identity:
                continue
            for candidate in self._discovered_locator_candidates(
                page, identity, [item]
            ):
                try:
                    if await candidate.count() and await candidate.first.is_visible():
                        return True
                except Exception:
                    continue
        return False

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
        if not expected_result.strip():
            raise InvalidGeneratedStepError(
                "Expected result is empty; no verifiable assertion can be executed."
            )
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", expected_result)
        if quoted and any(
            word in expected_result.lower() for word in ("visible", "displayed", "shown")
        ):
            await page.get_by_text(quoted[-1], exact=False).first.wait_for(
                state="visible", timeout=int(settings.automation_action_timeout_seconds * 1000)
            )
        else:
            await page.locator("body").wait_for(state="visible")

    async def _assert_step(
        self,
        page: Any,
        action: str,
        discovered_elements: list[dict[str, Any]],
    ) -> str:
        lowered = action.lower()
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", action)
        expected_value = quoted[-1] if quoted else None
        if "url" in lowered:
            if not expected_value:
                raise InvalidGeneratedStepError(
                    f"URL assertion has no explicit expected value: {action!r}"
                )
            if expected_value not in page.url:
                raise AssertionError(
                    f"Expected URL to contain {expected_value!r}, got {page.url!r}"
                )
            return f"URL assertion: {expected_value}"
        if "title" in lowered:
            if not expected_value:
                raise InvalidGeneratedStepError(
                    f"Title assertion has no explicit expected value: {action!r}"
                )
            actual_title = await page.title()
            if expected_value.casefold() not in actual_title.casefold():
                raise AssertionError(
                    f"Expected title to contain {expected_value!r}, got {actual_title!r}"
                )
            return f"Title assertion: {expected_value}"

        phrase = self._locator_phrase(action)
        resolved = await self._resolve_locators(
            page, phrase, (), discovered_elements
        )
        locator, description = resolved[0]
        await locator.scroll_into_view_if_needed()
        if "hidden" in lowered:
            if await locator.is_visible():
                raise AssertionError(f"Expected hidden element, but it is visible: {description}")
        elif "checked" in lowered and "unchecked" not in lowered:
            if not await locator.is_checked():
                raise AssertionError(f"Expected checked element: {description}")
        elif "unchecked" in lowered:
            if await locator.is_checked():
                raise AssertionError(f"Expected unchecked element: {description}")
        elif "value" in lowered:
            if expected_value is None:
                raise InvalidGeneratedStepError(
                    f"Value assertion has no explicit expected value: {action!r}"
                )
            actual_value = await locator.input_value()
            if actual_value != expected_value:
                raise AssertionError(
                    f"Expected value {expected_value!r}, got {actual_value!r}"
                )
        elif "text" in lowered or "contain" in lowered or "match" in lowered:
            if expected_value is None:
                raise InvalidGeneratedStepError(
                    f"Text assertion has no explicit expected value: {action!r}"
                )
            actual_text = (await locator.inner_text()).strip()
            if expected_value.casefold() not in actual_text.casefold():
                raise AssertionError(
                    f"Expected text containing {expected_value!r}, got {actual_text!r}"
                )
        elif not await locator.is_visible():
            raise AssertionError(f"Expected visible element: {description}")
        return description

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
        self, request: ExecuteScriptsRequest, *, _dedicated_loop: bool = False,
        _parallel_child: bool = False,
    ) -> ExecutionReport:
        if sys.platform == "win32" and not settings.app_mock_mode and not _dedicated_loop:
            return await _on_playwright_loop(
                lambda: self.execute(request, _dedicated_loop=True, _parallel_child=_parallel_child)
            )
        generation = await self.generation(request.generation_id)
        response: ScriptGenerationResponse = generation["response"]
        worker_count = max(1, min(settings.automation_execution_workers, len(response.scripts)))
        if request.mode == "automated" and not settings.app_mock_mode and not _parallel_child and worker_count > 1:
            started = time.perf_counter()
            chunks = [response.scripts[index::worker_count] for index in range(worker_count)]

            async def run_chunk(index: int, scripts: list[GeneratedScript]) -> ExecutionReport:
                child_id = f"{request.generation_id}-worker-{index}-{uuid.uuid4()}"
                self._generations[child_id] = {
                    **generation,
                    "response": response.model_copy(update={"scripts": scripts}),
                }
                try:
                    return await self.execute(
                        request.model_copy(update={"generation_id": child_id}),
                        _dedicated_loop=True,
                        _parallel_child=True,
                    )
                finally:
                    self._generations.pop(child_id, None)

            worker_reports = await asyncio.gather(*(
                run_chunk(index, scripts) for index, scripts in enumerate(chunks) if scripts
            ))
            by_script = {result.script_id: result for report in worker_reports for result in report.results}
            ordered_results = [by_script[script.script_id] for script in response.scripts if script.script_id in by_script]
            return self._save_report(
                request, ordered_results, time.perf_counter() - started,
                generation["directory"], generation,
            )
        authentication_token = f"playwright-{uuid.uuid4()}"
        playwright_test_config.clear()
        authentication: dict[str, str] | None = None
        if request.authentication and request.authentication.email:
            password = request.authentication.password
            playwright_test_config.overwrite(
                authentication_token,
                request.authentication.email,
                password.get_secret_value() if password else "",
            )
            authentication = playwright_test_config.read(authentication_token)
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
            playwright_test_config.clear(authentication_token)
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
            playwright_test_config.clear(authentication_token)
            return self._save_report(request, results, 0.01 * len(results), generation["directory"], generation)

        started = time.perf_counter()
        results: list[ScriptExecutionResult] = []
        fast_execution = request.execution_profile == "fast"
        diagnostic_execution = request.execution_profile == "diagnostic"
        saved_auth_state = response.crawl_report.get("auth_state")
        worker_storage_state: dict[str, Any] | None = saved_auth_state if saved_auth_state else None
        state = generation["workflow"]
        cases = {str(item["test_case_id"]): item for item in state.get("test_cases", [])}
        run_seacrawl_calls = 0
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            all_discovered = [
                item.model_dump(mode="json") for item in response.discovered_elements
            ]
            for script in response.scripts:
                if script.lifecycle_status == "Blocked":
                    results.append(
                        ScriptExecutionResult(
                            script_id=script.script_id,
                            script_name=script.name,
                            test_case_id=script.test_case_id,
                            scenario_id=script.scenario_id,
                            status="blocked",
                            duration_seconds=0.0,
                            error_message="BLOCKED: No matching crawl evidence directly associated with acceptance criteria was found.",
                            traceability=self._traceability(script),
                        )
                    )
                    continue

                disc_dicts = [
                    dict(item)
                    for item in (script.page_elements or all_discovered)
                ]
                test_started = time.perf_counter()
                console_logs: list[str] = []
                network_errors: list[str] = []
                # Determine if this script requires a fresh unauthenticated context
                use_auth_state = True
                test_case = cases.get(script.test_case_id, {"steps": []})
                tc_title = str(test_case.get("title") or "").lower()
                
                # Check for login/auth/register keywords in title, while ignoring logout/signout
                is_logout = any(token in tc_title for token in ("logout", "signout", "sign-out", "log-out"))
                is_login_tc = any(token in tc_title for token in ("login", "signin", "sign-in", "log-in", "register", "signup", "sign-up", "credential", "auth")) and not is_logout
                
                # Check steps for password input
                has_password_step = False
                for step in test_case.get("steps", []):
                    step_action = str(step.get("action") or "").lower()
                    if "password" in step_action and not any(token in step_action for token in ("logout", "signout", "sign-out", "log-out")):
                        has_password_step = True
                        break
                
                if is_login_tc or has_password_step:
                    use_auth_state = False
                
                script_storage_state = worker_storage_state if use_auth_state else None

                # ---- Use a browser context so we can capture traces (req 11) ----
                context = await browser.new_context(
                    storage_state=script_storage_state,
                )
                if fast_execution:
                    async def block_heavy_resources(route: Any) -> None:
                        if route.request.resource_type in {"font", "media"}:
                            await route.abort()
                        else:
                            await route.continue_()
                    await context.route("**/*", block_heavy_resources)
                trace_started = not fast_execution
                if trace_started:
                    await context.tracing.start(
                        screenshots=True,
                        snapshots=True,
                        sources=diagnostic_execution,
                    )
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
                action = ""
                context_element: dict[str, Any] | None = None
                expected_page = ""
                locator_details: dict[str, Any] = {}
                locator_attempts: list[dict[str, Any]] = []
                input_details: dict[str, Any] = {}
                navigation_details: dict[str, Any] = {}
                assertion_details: dict[str, Any] = {}
                http_response_status: int | None = None
                authentication_evidence: dict[str, Any] = {}
                seacrawl_attempted = False
                seacrawl_succeeded = False
                failure_category = "Script Generation"
                try:
                    test_case = cases.get(script.test_case_id, {"steps": []})
                    target_url = script.page_url or _best_page_url(
                        test_case, response.application_url, disc_dicts
                    )
                    # ---- Navigation with explicit wait + validation (req 4, 7) ----
                    failure_category = "Navigation Failure"
                    try:
                        source_url = page.url
                        navigation_response = await page.goto(
                            target_url,
                            wait_until="domcontentloaded",
                            timeout=int(settings.automation_navigation_timeout_seconds * 1000),
                        )
                        http_response_status = (
                            navigation_response.status if navigation_response else None
                        )
                        redirect_chain: list[str] = []
                        if navigation_response:
                            request_cursor = navigation_response.request
                            while request_cursor:
                                redirect_chain.append(request_cursor.url)
                                request_cursor = request_cursor.redirected_from
                            redirect_chain.reverse()
                        navigation_details = {
                            "source_url": source_url,
                            "intended_destination": target_url,
                            "actual_destination": page.url,
                            "redirect_chain": redirect_chain,
                            "response_status": http_response_status,
                            "expected_page_elements_appeared": None,
                        }
                    except PlaywrightTimeoutError as nav_timeout:
                        failure_category = "Page Load Timeout"
                        raise nav_timeout
                    if script.page_url:
                        await self._crawl_wait(page)
                    else:
                        await self._wait_for_page_stable(page)
                    failure_category = "Authentication Failure"
                    if not use_auth_state:
                        # Skip auto-login for login/auth/credential-validation test cases
                        authentication_evidence = {
                            "required": False,
                            "attempted": False,
                            "succeeded": False,
                            "redirected_url": page.url,
                            "expected_protected_url": target_url,
                        }
                    elif authentication and script_storage_state is not None:
                        authentication_evidence = {
                            "required": True,
                            "attempted": False,
                            "succeeded": True,
                            "session_reused": True,
                            "redirected_url": page.url,
                            "expected_protected_url": target_url,
                        }
                    else:
                        authentication_evidence = await self._authenticate_if_required(
                            page, authentication, target_url
                        )
                        if authentication and authentication_evidence.get("succeeded"):
                            worker_storage_state = await context.storage_state()
                    navigation_details["actual_destination"] = page.url
                    navigation_details["redirected_url"] = (
                        authentication_evidence.get("redirected_url")
                    )
                    failure_category = "Navigation Failure"
                    await self._validate_navigation(
                        page,
                        authentication_evidence.get("redirected_url")
                        if authentication_evidence.get("succeeded")
                        else target_url,
                    )
                    expected_elements_present = await self._expected_page_evidence_present(
                        page, target_url, disc_dicts
                    )
                    navigation_details["expected_page_elements_appeared"] = (
                        expected_elements_present
                    )
                    if not expected_elements_present:
                        if authentication_evidence.get("required"):
                            failure_category = "Authentication Failure"
                            raise PlaywrightAuthenticationError(
                                "Authentication Failed: the expected protected page "
                                f"{target_url} loaded without its crawl-verified elements."
                            )
                        raise AutomationError(
                            "Navigation failure: expected crawl-verified page elements "
                            f"did not appear on {target_url}."
                        )
                    # ---- Auto-dismiss overlays once after landing (req 8) ----
                    await self._dismiss_overlays(page)
                    last_overlay_url = page.url

                    per_test_calls = 0
                    for step in (
                        script.executable_steps
                        or test_case.get("steps", [])
                    ):
                        failed_step = step.get("step_number")
                        expected = step.get("expected_result")
                        action = step.get("action", "")
                        step_kind = _step_execution_kind(action)
                        if step_kind == "invalid":
                            failure_category = "Invalid Test Step"
                            raise InvalidGeneratedStepError(
                                f"Invalid Test Step: {action!r} has no concrete "
                                "Playwright action or verifiable assertion."
                            )
                        phrase = self._locator_phrase(action)
                        element = f"Requested target: {phrase}"

                        # ---- Pre-step overlay dismissal (req 8) ----
                        if not fast_execution or page.url != last_overlay_url:
                            await self._dismiss_overlays(page)
                            last_overlay_url = page.url
                        failure_category = "Locator Failure"
                        try:
                            context_element = self._context_element(action, disc_dicts)
                            locator_details, locator_attempts = self._locator_evidence(
                                context_element
                            )
                            if context_element:
                                failure_category = "Application State Failure"
                                fresh_elements = await self._restore_crawl_context(
                                    page,
                                    context_element,
                                    script.page_url or response.application_url,
                                    credentials=None if not use_auth_state else authentication,
                                )
                                expected_page = _canonical_page_url(
                                    str(
                                        context_element.get("page_url")
                                        or script.page_url
                                        or response.application_url
                                    )
                                )
                                recorded = [
                                    item
                                    for item in disc_dicts
                                    if _canonical_page_url(
                                        str(item.get("page_url") or expected_page)
                                    )
                                    == expected_page
                                ]
                                page_elements = [*recorded, *fresh_elements]
                                failure_category = "Locator Failure"
                                navigation_details.update({
                                    "intended_destination": expected_page,
                                    "actual_destination": page.url,
                                    "expected_page_elements_appeared": bool(recorded),
                                })
                            else:
                                page_elements = [
                                    el for el in disc_dicts
                                    if not el.get("page_url")
                                    or _canonical_page_url(str(el["page_url"]))
                                    == _canonical_page_url(page.url)
                                ]
                            if _canonical_page_url(page.url) != _canonical_page_url(
                                expected_page or target_url
                            ):
                                failure_category = "Navigation Failure"
                                raise LookupError(
                                    f"Current URL {page.url} does not match expected "
                                    f"page {expected_page or target_url}."
                                )
                            if step_kind == "assertion":
                                failure_category = "Assertion Failure"
                                element = await self._assert_step(
                                    page, action, page_elements
                                )
                            else:
                                element = await self._perform(
                                    page, action, page_elements
                                )
                        except (LookupError, PlaywrightError, PlaywrightTimeoutError) as action_error:
                            # Classify timeout separately
                            if isinstance(action_error, PlaywrightTimeoutError):
                                failure_category = (
                                    "Dynamic Content Timeout"
                                    if "wait" in action.lower()
                                    else "Locator Failure"
                                )
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
                            # ---- Seacrawl fallback – only after all Playwright strategies fail (req 6) ----
                            if (
                                not action_recovered
                                and self.seacrawl.enabled
                                and per_test_calls < settings.seacrawl_max_calls_per_test
                                and run_seacrawl_calls < settings.seacrawl_max_calls_per_run
                            ):
                                per_test_calls += 1
                                run_seacrawl_calls += 1
                                recovery = await self.seacrawl.recover(
                                    url=page.url,
                                    action=action,
                                    expected_result=expected or "",
                                )
                                seacrawl_attempted = recovery.attempted
                                seacrawl_succeeded = recovery.succeeded
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
                                        element = f"Seacrawl locator: {recovery.locator}"
                                        seacrawl_succeeded = True
                                    except (LookupError, ValueError, PlaywrightError):
                                        seacrawl_succeeded = False
                                action_recovered = seacrawl_succeeded
                            if not action_recovered:
                                raise action_error

                        # ---- Post-action assertion (req 4) ----
                        if step_kind == "action":
                            failure_category = "Assertion Failure"
                            assertion_details = {
                                "expected_value": expected,
                                "actual_value": None,
                                "comparison_type": "expected-result assertion",
                            }
                            await self._assert_expected(page, expected or "")

                    if fast_execution:
                        quality_checks = {
                            "accessibility": {"checked": False, "potential_violations": []},
                            "visual_regression": {"checked": False, "changed": False},
                            "api_contract": {"checked": True, "failed_responses": list(network_errors)},
                            "backend_observability": {"console_and_failed_request_capture": True},
                            "execution_profile": "fast",
                        }
                    else:
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
                        if trace_started:
                            await context.tracing.stop()
                    except Exception:
                        pass

                except Exception as exc:
                    # ---- Classify environment errors (req 10) ----
                    if isinstance(exc, (ImportError, OSError, PermissionError, EnvironmentError)):
                        failure_category = "Environment Issue"
                    elif (
                        isinstance(exc, AssertionError)
                        and failure_category != "Assertion Failure"
                    ):
                        failure_category = "Application Failure"
                    elif isinstance(exc, InvalidGeneratedStepError):
                        failure_category = "Invalid Test Step"
                    elif isinstance(exc, PlaywrightAuthenticationError):
                        failure_category = "Authentication Failure"

                    captured_dom_text: str | None = None
                    captured_page_title: str | None = None
                    try:
                        captured_dom_text = (
                            await page.locator("body").inner_text(timeout=3000)
                        )[:5000]
                    except Exception:
                        pass
                    try:
                        captured_page_title = await page.title()
                    except Exception:
                        pass
                    api_failures = [
                        entry
                        for entry in network_errors
                        if re.search(r"HTTP (?:4|5)\d\d", entry)
                        and any(token in entry.lower() for token in ("/api/", "graphql"))
                    ]
                    if any(re.search(r"HTTP (?:401|403)", entry) for entry in api_failures):
                        failure_category = "Authentication Failure"
                    elif api_failures:
                        failure_category = "API Failure"
                    elif captured_dom_text and any(
                        token in captured_dom_text.lower()
                        for token in ("access denied", "just a moment", "captcha")
                    ):
                        failure_category = "Blocked Page"
                    assertion_details["actual_value"] = str(exc)
                    if captured_dom_text:
                        assertion_details["captured_dom_text"] = captured_dom_text

                    if self._failure_stage(action, failure_category) == "entering_data":
                        input_details = {
                            "field_name": (
                                locator_details.get("label")
                                or locator_details.get("accessible_name")
                                or locator_details.get("placeholder")
                            ),
                            "attempted_value": self._masked_input_value(action),
                            "visible": None,
                            "enabled": None,
                            "editable": None,
                            "focused": None,
                            "validation_or_timeout_message": str(exc),
                        }
                        if context_element:
                            for candidate in self._discovered_locator_candidates(
                                page,
                                self._locator_phrase(action),
                                [context_element],
                            ):
                                try:
                                    if await candidate.count():
                                        target = candidate.first
                                        input_details.update({
                                            "visible": await target.is_visible(),
                                            "enabled": await target.is_enabled(),
                                            "editable": await target.is_editable(),
                                            "focused": await target.evaluate(
                                                "el => document.activeElement === el"
                                            ),
                                        })
                                        break
                                except Exception:
                                    continue

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
                        if trace_started:
                            trace_path = generation["directory"] / f"{script.script_id}-failure-trace.zip"
                            await context.tracing.stop(path=str(trace_path))
                    except Exception:
                        trace_path = None

                    failure = FailureAnalysis(
                        test_case_id=script.test_case_id,
                        issue_title=f"{failure_category}: {script.name}",
                        test_case_title=str(test_case.get("title") or script.name),
                        failed_step=failed_step,
                        failed_action=action or None,
                        failure_stage=self._failure_stage(action, failure_category),
                        expected_result=expected,
                        actual_result=str(exc),
                        failure_reason=type(exc).__name__,
                        failure_category=failure_category,
                        page_url=page.url,
                        expected_page_url=expected_page or target_url,
                        page_title=captured_page_title,
                        http_response_status=http_response_status,
                        ui_element=element,
                        exact_locator=(
                            locator_attempts[0]["locator"] if locator_attempts else None
                        ),
                        locator_details=locator_details,
                        alternate_locators_attempted=locator_attempts,
                        locator_diagnosis=(
                            self._locator_diagnosis(context_element, page.url)
                        ),
                        input_details=input_details,
                        navigation_details=navigation_details,
                        assertion_details=assertion_details,
                        api_details={
                            "http_response_status": http_response_status,
                            "failed_responses": network_errors,
                        },
                        application_state_details=(
                            {
                                **(
                                    context_element.get("application_state", {})
                                    if context_element else {}
                                ),
                                "authentication": {
                                    **authentication_evidence,
                                    "credentials_provided": bool(authentication),
                                },
                            }
                        ),
                        captured_dom_text=captured_dom_text,
                        reproduction_steps=[
                            f"Open {target_url}.",
                            *(
                                [
                                    f"Navigate through: {' -> '.join(context_element.get('navigation_path') or [])}."
                                ]
                                if context_element
                                and context_element.get("navigation_path")
                                else []
                            ),
                            f"Execute step {failed_step}: {action}.",
                            f"Verify: {expected}.",
                        ],
                        screenshot=str(screenshot_path) if screenshot_path else None,
                        dom_snapshot=str(dom_snapshot_path) if dom_snapshot_path else None,
                        trace_path=str(trace_path) if trace_path else None,
                        console_logs=console_logs,
                        network_errors=network_errors,
                        stack_trace=traceback.format_exc(),
                        seacrawl_attempted=seacrawl_attempted,
                        seacrawl_succeeded=seacrawl_succeeded,
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
        playwright_test_config.clear(authentication_token)
        return self._save_report(request, results, time.perf_counter() - started, generation["directory"], generation)

    @staticmethod
    def _traceability(script: GeneratedScript) -> dict[str, Any]:
        return {
            "requirements": script.requirement_ids,
            "user_stories": script.user_story_ids,
            "scenario_id": script.scenario_id,
            "test_case_id": script.test_case_id,
            "script_id": script.script_id,
            "page_url": script.page_url,
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
        def normalize(value: str) -> str:
            return re.sub(r"[^a-z0-9]", "", value.lower()).lstrip("0")
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
        if failure.failure_category in {"Generated Script Defect", "Invalid Test Step"}:
            return (
                "AUTOMATION_DEFECT",
                "Locator or automation issue",
                0.99,
                False,
                "The generated step contains an observation but no executable "
                "action or explicit interaction value.",
            )
        if failure.failure_category == "Application State Failure":
            return (
                "AUTOMATION_DEFECT",
                "Locator or automation issue",
                0.9,
                False,
                "The script did not successfully recreate the page, form, modal, "
                "cart, or authentication state captured during crawling.",
            )
        if failure.failure_category == "Test Data Failure":
            return (
                "TEST_DATA_FAILURE",
                "Environment or configuration issue",
                0.92,
                False,
                "The required test input, account, fixture, or application record is unavailable.",
            )
        if failure.failure_category == "API Failure":
            return (
                "APPLICATION_DEFECT",
                "API/Backend failure",
                0.92,
                True,
                "The application API returned an unsuccessful response.",
            )
        if failure.failure_category in {"Blocked Page", "Authentication Failure"}:
            return (
                "ENVIRONMENT_FAILURE",
                "Environment or configuration issue",
                0.9,
                False,
                "The expected page could not be reached because access was blocked or authentication state was unavailable.",
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
        if failure.failure_category in {"Environment Issue", "Page Load Timeout", "Page Failure"}:
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
        if failure.failure_category in {"Assertion Failure", "Application", "Application Failure"}:
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
        confidence_threshold = float(
            workflow.get("confidence_threshold", settings.validation_pass_threshold)
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
            >= confidence_threshold,
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
                "threshold": confidence_threshold,
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
        blocked = sum(result.status == "blocked" for result in results)
        workflow = generation.get("workflow", {})
        for result in results:
            if result.status == "failed" and result.failure:
                result.failure.intelligence = self._failure_intelligence(
                    request.generation_id, workflow, result
                )
                mapping, scenario, test_case = self._map_failure_requirements(
                    workflow, result
                )
                intelligence = result.failure.intelligence
                result.failure.confidence_score = intelligence.confidence
                result.failure.affected_feature = (
                    mapping.feature[0]["title"]
                    if mapping.feature
                    else result.script_name
                )
                result.failure.mapped_user_stories = mapping.user_story
                result.failure.mapped_acceptance_criteria = (
                    mapping.acceptance_criteria
                )
                result.failure.test_scenario = scenario or {
                    "scenario_id": result.scenario_id,
                    "mapping_status": "not_found",
                }
                result.failure.test_case_title = str(
                    (test_case or {}).get("title")
                    or result.failure.test_case_title
                    or result.script_name
                )
                missing_mappings = [
                    name
                    for name, values in (
                        ("user story", mapping.user_story),
                        ("acceptance criterion", mapping.acceptance_criteria),
                        ("scenario", mapping.scenario),
                        ("test case", mapping.test_case),
                    )
                    if not values
                ]
                result.failure.mapping_explanation = (
                    "Mapped using generated workflow IDs."
                    if not missing_mappings
                    else "Mapping unavailable for "
                    + ", ".join(missing_mappings)
                    + "; the workflow did not contain matching IDs."
                )
                result.failure.developer_issue_recommended = bool(
                    intelligence.developer_implementation_plan
                )
                result.failure.severity = (
                    intelligence.developer_implementation_plan.priority
                    if intelligence.developer_implementation_plan
                    else (
                        "High"
                        if intelligence.classification
                        in {"APPLICATION_DEFECT", "MISSING_FEATURE"}
                        else "Medium"
                    )
                )
                result.failure.priority = result.failure.severity
                result.failure.issue_title = (
                    intelligence.developer_implementation_plan.ticket_title
                    if intelligence.developer_implementation_plan
                    else f"{result.failure.failure_category}: "
                    f"{result.failure.test_case_title}"
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
                        "severity": result.failure.severity,
                        "classification": intelligence.classification,
                        "confidence": intelligence.confidence,
                        "developer_issue_created": bool(plan),
                        "technical_failure_details": result.failure.model_dump(
                            mode="json", exclude={"intelligence"}
                        ),
                        "root_cause_analysis": intelligence.root_cause_analysis,
                        "reproduction_steps": result.failure.reproduction_steps,
                        "recommended_script_correction": (
                            (
                                intelligence.automation_recommendation.script_changes
                                + intelligence.automation_recommendation.locator_strategy
                                + intelligence.automation_recommendation.wait_strategy
                                + intelligence.automation_recommendation.assertion_strategy
                                + intelligence.automation_recommendation.navigation_strategy
                            )
                            if intelligence.automation_recommendation
                            else []
                        ),
                        "recommended_application_fix": (
                            plan.suggested_implementation_steps
                            if plan else intelligence.recommended_fix
                        ),
                        "mapping_explanation": result.failure.mapping_explanation,
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
            blocked_scripts=blocked,
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
                "blocked": blocked,
                "rejected": rejected,
                "pass_rate": round((passed / overall_total * 100) if overall_total else 0, 2),
                "pages_discovered": len(
                    (generation.get("response").application_map or {}).get("pages", [])
                ) if generation.get("response") else 0,
                "page_failures": sum(
                    bool(result.failure and result.failure.failure_category in {
                        "Page Failure", "Navigation Failure", "Page Load Timeout"
                    }) for result in results
                ),
                "locator_failures": sum(
                    bool(result.failure and result.failure.failure_category == "Locator Failure")
                    for result in results
                ),
                "environment_failures": sum(
                    bool(result.failure and result.failure.failure_category == "Environment Issue")
                    for result in results
                ),
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

    async def compare(self, execution_id: str) -> TraceabilityComparisonReport:
        execution = self.report(execution_id)
        generation = await self.generation(execution.generation_id)
        workflow = generation["workflow"]
        response: ScriptGenerationResponse = generation["response"]
        crawl_report = response.crawl_report or {}
        unsupported = {
            str(item.get("test_case_id")): item
            for item in crawl_report.get("requirement_evidence", {}).get(
                "unsupported_test_cases", []
            )
        }
        generated_test_case_ids = {
            str(script.test_case_id) for script in response.scripts
        }
        statuses = {result.script_id: result.status for result in execution.results}
        missing_threshold = settings.automation_coverage_missing_threshold
        covered_threshold = settings.automation_coverage_covered_threshold
        evidence: dict[str, set[str]] = {}
        for script in response.scripts:
            words = _meaningful_words(" ".join([
                script.name, script.page_url or "", script.source,
                *[" ".join(str(element.get(key) or "") for key in (
                    "name", "label", "placeholder", "visible_text", "href", "role"
                )) for element in script.page_elements],
            ]))
            evidence[script.script_id] = words

        def coverage(item: dict[str, Any], id_key: str) -> dict[str, Any]:
            text = " ".join([
                str(item.get("title") or ""), str(item.get("description") or ""),
                *[f"{step.get('action', '')} {step.get('expected_result', '')}"
                  for step in item.get("steps", [])],
            ])
            expected = _meaningful_words(text)
            item_id = str(item.get(id_key) or "")
            matching_scripts = [
                script for script in response.scripts
                if str(script.test_case_id if id_key == "test_case_id" else script.scenario_id) == item_id
                and statuses.get(script.script_id) in {"passed", "failed"}
            ]
            executed_words = set().union(*(evidence[script.script_id] for script in matching_scripts)) if matching_scripts else set()
            overlap = expected & executed_words
            percentage = round(len(overlap) / len(expected) * 100, 2) if expected else 0
            unsupported_item = unsupported.get(item_id)
            evidence_issue = None
            if crawl_report.get("status") == "crawl_blocked":
                evidence_issue = "crawl_blocked"
            elif crawl_report.get("status") != "crawl_completed":
                evidence_issue = "crawl_incomplete"
            elif unsupported_item:
                evidence_issue = unsupported_item["classification"]
            elif id_key == "test_case_id" and item_id not in generated_test_case_ids:
                evidence_issue = "missing_from_generated_script"
            status = _coverage_status(percentage, missing_threshold, covered_threshold)
            classification = {"missing": "missing_evidence", "partial": "partially_covered", "covered": "covered"}[status]
            return {
                "id": item_id, "title": str(item.get("title") or ""),
                "status": status,
                "classification": classification,
                "evidence_issue": evidence_issue,
                "coverage_percentage": percentage,
                "matched_scripts": [script.script_id for script in matching_scripts if expected & evidence[script.script_id]],
                "missing_terms": sorted(expected - executed_words),
            }

        scenarios = [coverage(item, "scenario_id") for item in workflow.get("scenarios", [])]
        cases = [coverage(item, "test_case_id") for item in workflow.get("test_cases", [])]
        artifacts = scenarios + cases
        gaps = [{
            "artifact_id": item["id"],
            "artifact_title": item["title"],
            "status": item["status"],
            "gap_type": item["classification"],
            "coverage_percentage": item["coverage_percentage"],
            "details": f"Missing UI evidence: {', '.join(item['missing_terms'][:12])}" if item["missing_terms"] else "No missing terms",
        } for item in artifacts if item["status"] != "covered"]
        inconsistencies = [{
            "script_id": result.script_id, "type": "execution_failure",
            "details": result.error_message or "Page execution failed.",
        } for result in execution.results if result.status == "failed"]
        covered = sum(item["status"] == "covered" for item in artifacts)
        partial = sum(item["status"] == "partial" for item in artifacts)
        missing = sum(item["status"] == "missing" for item in artifacts)
        report = TraceabilityComparisonReport(
            comparison_id=f"cmp-{uuid.uuid4()}", execution_id=execution_id,
            generation_id=execution.generation_id,
            summary={"total_artifacts": len(artifacts), "covered": covered,
                     "partial": partial, "missing": missing,
                     "coverage_percentage": round(sum(item["coverage_percentage"] for item in artifacts) / len(artifacts), 2) if artifacts else 0,
                     "thresholds": {"missing_below": missing_threshold, "covered_above": covered_threshold}},
            scenario_coverage=scenarios, test_case_coverage=cases,
            gaps=gaps, inconsistencies=inconsistencies,
        )
        (generation["directory"] / f"{report.comparison_id}.json").write_text(
            json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        return report

    async def health(self, *, _dedicated_loop: bool = False) -> AutomationHealth:
        if settings.app_mock_mode:
            return AutomationHealth(
                status="healthy",
                playwright_available=True,
                browser_available=True,
                seacrawl_enabled=False,
                seacrawl_api_reachable=None,
                seacrawl_configuration_valid=True,
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
        seacrawl_reachable = await self.seacrawl.health() if self.seacrawl.enabled else None
        healthy = playwright_available and browser_available
        return AutomationHealth(
            status="healthy" if healthy else "degraded",
            playwright_available=playwright_available,
            browser_available=browser_available,
            seacrawl_enabled=self.seacrawl.enabled,
            seacrawl_api_reachable=seacrawl_reachable,
            seacrawl_configuration_valid=self.seacrawl.configuration_valid,
            details=details,
        )


automation_service = AutomationService()
