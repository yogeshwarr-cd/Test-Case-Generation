from __future__ import annotations

import json
import re
import time
import traceback
import uuid
from pathlib import Path
from pprint import pformat
from typing import Any

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
)
from app.services.skyvern_service import SkyvernAdapter
from app.services.workflow_service import workflow_service


class AutomationError(AppError):
    error_code = "AUTOMATION_ERROR"


class AutomationNotFound(AppError):
    status_code = 404
    error_code = "AUTOMATION_NOT_FOUND"


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")[:80] or "test"


def _python_source(
    test_case: dict[str, Any],
    application_url: str,
    discovered_elements: list[dict[str, Any]] | None = None,
) -> str:
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

    def stable_locator(self, instruction: str):
        words = [word for word in re.findall(r"[A-Za-z0-9]+", instruction) if len(word) > 2]
        name = " ".join(words[-4:])
        instruction_words = {{word.lower() for word in words}}
        for element in DISCOVERED_ELEMENTS:
            identity = " ".join(str(element.get(key) or "") for key in ("name", "label", "test_id"))
            if instruction_words.intersection(re.findall(r"[a-z0-9]+", identity.lower())):
                if element.get("test_id"):
                    return self.page.get_by_test_id(element["test_id"])
                if element.get("label"):
                    return self.page.get_by_label(element["label"])
                if element.get("role") and element.get("name"):
                    return self.page.get_by_role(element["role"], name=element["name"])
        candidates = [
            self.page.get_by_role("button", name=re.compile(name, re.I)),
            self.page.get_by_label(re.compile(name, re.I)),
            self.page.get_by_test_id(name),
            self.page.get_by_text(re.compile(name, re.I)),
        ]
        for candidate in candidates:
            if candidate.count():
                return candidate.first
        raise AssertionError(f"No stable locator found for: {{instruction}}")

    def perform(self, instruction: str):
        lowered = instruction.lower()
        if any(token in lowered for token in ("navigate", "open", "visit", "go to")):
            self.page.goto(BASE_URL, wait_until="domcontentloaded")
        elif any(token in lowered for token in ("click", "press", "select", "choose")):
            self.stable_locator(instruction).click()
        elif any(token in lowered for token in ("enter", "type", "fill")):
            values = re.findall(r"['\"]([^'\"]+)['\"]", instruction)
            self.stable_locator(instruction).fill(values[-1] if values else "test")
        else:
            expect(self.page.locator("body")).to_be_visible()

    def assert_expected(self, expected_result: str):
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", expected_result)
        if quoted and any(word in expected_result.lower() for word in ("visible", "displayed", "shown")):
            expect(self.page.get_by_text(quoted[-1], exact=False).first).to_be_visible()
        else:
            expect(self.page.locator("body")).to_be_visible()


def test_{_safe_name(test_case["test_case_id"]).replace("-", "_")}(page: Page):
    app = {class_name}(page)
    page.goto(BASE_URL, wait_until="domcontentloaded")
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

    async def _validate_url(self, url: str) -> None:
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
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=int(settings.automation_navigation_timeout_seconds * 1000),
                )
                title = await page.title()
                raw = await page.locator("button,input,select,textarea,a,[role],[data-testid]").evaluate_all(
                    """els => els.slice(0, 250).map(el => ({
                      role: el.getAttribute('role'), name: el.getAttribute('aria-label') || el.innerText?.trim(),
                      label: el.labels?.[0]?.innerText?.trim() || null,
                      test_id: el.getAttribute('data-testid'), tag: el.tagName.toLowerCase(),
                      input_type: el.getAttribute('type')
                    }))"""
                )
                await browser.close()
            return title, [DiscoveredElement.model_validate(item) for item in raw]
        except Exception as exc:
            raise AutomationError(
                "The URL responded, but Chromium could not inspect it. Run `playwright install chromium`."
            ) from exc

    async def generate(self, request: GenerateScriptsRequest) -> ScriptGenerationResponse:
        state = workflow_service.get(request.workflow_id)
        if state.get("status") != "completed":
            raise AutomationError("Test scripts can only be generated for a completed workflow")
        url = str(request.application_url)
        await self._validate_url(url)
        title, elements = await self._discover(url)
        generation_id = f"gen-{uuid.uuid4()}"
        directory = self.artifact_root / generation_id
        directory.mkdir(parents=True, exist_ok=False)
        scenarios = {str(item["scenario_id"]): item for item in state.get("scenarios", [])}
        scripts = []
        for index, test_case in enumerate(state.get("test_cases", []), start=1):
            script_id = f"pw-{index:03d}-{_safe_name(str(test_case['test_case_id']))}"
            path = directory / f"{script_id}.py"
            source = _python_source(
                test_case,
                url,
                [element.model_dump(mode="json") for element in elements],
            )
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
                )
            )
        response = ScriptGenerationResponse(
            generation_id=generation_id,
            application_url=url,
            reachable=True,
            page_title=title,
            discovered_elements=elements,
            scripts=scripts,
        )
        self._generations[generation_id] = {
            "response": response,
            "workflow": state,
            "directory": directory,
        }
        return response

    def generation(self, generation_id: str) -> dict[str, Any]:
        try:
            return self._generations[generation_id]
        except KeyError as exc:
            raise AutomationNotFound("Script generation was not found") from exc

    def script_path(self, generation_id: str, script_id: str) -> Path:
        generation = self.generation(generation_id)
        script = next(
            (item for item in generation["response"].scripts if item.script_id == script_id), None
        )
        if not script:
            raise AutomationNotFound("Generated script was not found")
        return generation["directory"] / f"{script_id}.py"

    @staticmethod
    def _locator_phrase(action: str) -> str:
        ignored = {"click", "press", "select", "choose", "the", "button", "link", "on"}
        words = [word for word in re.findall(r"[A-Za-z0-9]+", action) if word.lower() not in ignored]
        return " ".join(words[-5:]) or action

    async def _perform(self, page: Any, action: str) -> str | None:
        lowered = action.lower()
        if any(token in lowered for token in ("navigate", "open", "visit", "go to")):
            return None
        phrase = self._locator_phrase(action)
        if any(token in lowered for token in ("click", "press", "select", "choose")):
            candidates = [
                page.get_by_role("button", name=re.compile(phrase, re.I)),
                page.get_by_label(re.compile(phrase, re.I)),
                page.get_by_text(re.compile(phrase, re.I)),
                page.locator(f'[data-testid="{phrase}"]'),
            ]
            for locator in candidates:
                if await locator.count():
                    await locator.first.click(timeout=int(settings.automation_action_timeout_seconds * 1000))
                    return phrase
            raise LookupError(f"No stable locator found for '{phrase}'")
        if any(token in lowered for token in ("enter", "type", "fill")):
            values = re.findall(r"['\"]([^'\"]+)['\"]", action)
            value = values[-1] if values else "test"
            locator = page.get_by_label(re.compile(phrase, re.I))
            if not await locator.count():
                locator = page.locator("input:visible, textarea:visible").first
            await locator.fill(value, timeout=int(settings.automation_action_timeout_seconds * 1000))
            return phrase
        return None

    async def _retry_recovered(self, page: Any, locator_value: str, action: str) -> None:
        locator = page.locator(locator_value).first
        lowered = action.lower()
        if any(token in lowered for token in ("enter", "type", "fill")):
            values = re.findall(r"['\"]([^'\"]+)['\"]", action)
            await locator.fill(
                values[-1] if values else "test",
                timeout=int(settings.automation_action_timeout_seconds * 1000),
            )
        else:
            await locator.click(timeout=int(settings.automation_action_timeout_seconds * 1000))

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

    async def execute(self, request: ExecuteScriptsRequest) -> ExecutionReport:
        generation = self.generation(request.generation_id)
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
            return self._save_report(request, results, 0)

        started = time.perf_counter()
        results: list[ScriptExecutionResult] = []
        state = generation["workflow"]
        cases = {str(item["test_case_id"]): item for item in state.get("test_cases", [])}
        run_skyvern_calls = 0
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            for script in response.scripts:
                test_started = time.perf_counter()
                console_logs: list[str] = []
                network_errors: list[str] = []
                page = await browser.new_page()
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
                try:
                    await page.goto(
                        response.application_url,
                        wait_until="domcontentloaded",
                        timeout=int(settings.automation_navigation_timeout_seconds * 1000),
                    )
                    per_test_calls = 0
                    for step in cases[script.test_case_id].get("steps", []):
                        failed_step = step.get("step_number")
                        expected = step.get("expected_result")
                        try:
                            element = await self._perform(page, step.get("action", ""))
                        except (LookupError, PlaywrightTimeoutError) as action_error:
                            if (
                                self.skyvern.enabled
                                and per_test_calls < settings.skyvern_max_calls_per_test
                                and run_skyvern_calls < settings.skyvern_max_calls_per_run
                            ):
                                per_test_calls += 1
                                run_skyvern_calls += 1
                                recovery = await self.skyvern.recover(
                                    url=page.url,
                                    action=step.get("action", ""),
                                    expected_result=expected or "",
                                )
                                skyvern_attempted = recovery.attempted
                                skyvern_succeeded = recovery.succeeded
                                if recovery.locator:
                                    await self._retry_recovered(
                                        page, recovery.locator, step.get("action", "")
                                    )
                                    skyvern_succeeded = True
                                if skyvern_succeeded:
                                    continue
                            raise action_error
                        await self._assert_expected(page, expected or "")
                    results.append(
                        ScriptExecutionResult(
                            script_id=script.script_id,
                            script_name=script.name,
                            test_case_id=script.test_case_id,
                            scenario_id=script.scenario_id,
                            status="passed",
                            duration_seconds=round(time.perf_counter() - test_started, 3),
                            traceability=self._traceability(script),
                        )
                    )
                except Exception as exc:
                    screenshot = generation["directory"] / f"{script.script_id}-failure.png"
                    try:
                        await page.screenshot(path=str(screenshot), full_page=True)
                    except Exception:
                        screenshot = None
                    failure = FailureAnalysis(
                        test_case_id=script.test_case_id,
                        failed_step=failed_step,
                        expected_result=expected,
                        actual_result=str(exc),
                        failure_reason=type(exc).__name__,
                        page_url=page.url,
                        ui_element=element,
                        screenshot=str(screenshot) if screenshot else None,
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
                    await page.close()
            await browser.close()
        return self._save_report(request, results, time.perf_counter() - started)

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
        self, request: ExecuteScriptsRequest, results: list[ScriptExecutionResult], duration: float
    ) -> ExecutionReport:
        execution_id = f"exec-{uuid.uuid4()}"
        passed = sum(result.status == "passed" for result in results)
        failed = sum(result.status == "failed" for result in results)
        skipped = sum(result.status == "skipped" for result in results)
        report = ExecutionReport(
            execution_id=execution_id,
            generation_id=request.generation_id,
            mode=request.mode,
            total_scripts=len(results),
            passed_scripts=passed,
            failed_scripts=failed,
            skipped_scripts=skipped,
            execution_time_seconds=round(duration, 3),
            success_percentage=round((passed / len(results) * 100) if results else 0, 2),
            results=results,
        )
        self._reports[execution_id] = report
        path = self.generation(request.generation_id)["directory"] / f"{execution_id}.json"
        path.write_text(json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8")
        return report

    def report(self, execution_id: str) -> ExecutionReport:
        try:
            return self._reports[execution_id]
        except KeyError as exc:
            raise AutomationNotFound("Execution report was not found") from exc

    async def health(self) -> AutomationHealth:
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
