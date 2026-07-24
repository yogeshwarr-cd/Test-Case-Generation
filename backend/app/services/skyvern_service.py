from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time

import httpx

from app.core.config import settings


@dataclass
class SkyvernRecovery:
    attempted: bool
    succeeded: bool
    locator: str | None = None
    message: str | None = None


class SkyvernAdapter:
    """Bounded discovery/navigation and failed-locator recovery client.

    Playwright remains the only source of verified DOM elements and the execution
    engine. Skyvern may suggest navigation targets, but never authors selectors or
    assertions used without Playwright verification.
    """

    def __init__(self) -> None:
        self.enabled = settings.skyvern_fallback_enabled and not settings.app_mock_mode
        self.base_url = settings.skyvern_base_url.rstrip("/")

    @property
    def configuration_valid(self) -> bool:
        return not self.enabled or bool(self.base_url and settings.skyvern_integration_mode)

    async def health(self) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=settings.skyvern_timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/health")
            return response.is_success
        except httpx.HTTPError:
            return False

    async def recover(self, *, url: str, action: str, expected_result: str) -> SkyvernRecovery:
        if not self.enabled:
            return SkyvernRecovery(False, False, message="Skyvern fallback is disabled")
        headers = {}
        if settings.skyvern_api_key:
            headers["x-api-key"] = settings.skyvern_api_key
        payload = {
            "url": url,
            "prompt": (
                "Identify the UI element needed for this action without performing the action: "
                f"{action}. Return a stable Playwright-compatible CSS selector in locator."
            ),
            "data_extraction_schema": {
                "type": "object",
                "properties": {"locator": {"type": "string"}},
                "required": ["locator"],
            },
            "max_steps": 5,
        }
        last_message = None
        for _ in range(max(1, settings.skyvern_max_attempts)):
            try:
                async with httpx.AsyncClient(timeout=settings.skyvern_timeout_seconds) as client:
                    response = await client.post(f"{self.base_url}/v1/run/tasks", json=payload, headers=headers)
                if response.is_success:
                    data = response.json()
                    run_id = data.get("run_id")
                    deadline = time.monotonic() + settings.skyvern_timeout_seconds
                    while run_id and time.monotonic() < deadline:
                        status = str(data.get("status", "")).lower()
                        if status in {"completed", "failed", "terminated", "canceled", "timed_out"}:
                            break
                        await asyncio.sleep(0.5)
                        async with httpx.AsyncClient(timeout=settings.skyvern_timeout_seconds) as client:
                            poll = await client.get(
                                f"{self.base_url}/v1/runs/{run_id}", headers=headers
                            )
                        poll.raise_for_status()
                        data = poll.json()
                    output = data.get("output") or {}
                    locator = output.get("locator") if isinstance(output, dict) else None
                    status = str(data.get("status", "")).lower()
                    return SkyvernRecovery(
                        True,
                        status == "completed" and bool(locator),
                        locator,
                        data.get("failure_reason"),
                    )
                last_message = f"Skyvern returned HTTP {response.status_code}"
            except (httpx.HTTPError, ValueError) as exc:
                last_message = type(exc).__name__
        return SkyvernRecovery(True, False, message=last_message)

    async def discover_urls(self, *, url: str, page_limit: int, depth_limit: int) -> list[str]:
        """Ask Skyvern to walk the application and return navigation candidates."""
        if not self.enabled:
            return []
        headers = {"x-api-key": settings.skyvern_api_key} if settings.skyvern_api_key else {}
        payload = {
            "url": url,
            "prompt": (
                "Walk through this application using menus, links, buttons, tabs, "
                "pagination, forms, dialogs and dropdowns. Return only reachable "
                "same-origin page URLs in urls. Do not infer or invent URLs."
            ),
            "data_extraction_schema": {
                "type": "object",
                "properties": {
                    "urls": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["urls"],
            },
            "max_steps": max(1, min(page_limit * max(1, depth_limit), 100)),
        }
        try:
            async with httpx.AsyncClient(timeout=settings.skyvern_timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/v1/run/tasks", json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
                run_id = data.get("run_id")
                deadline = time.monotonic() + settings.skyvern_timeout_seconds
                while run_id and time.monotonic() < deadline:
                    if str(data.get("status", "")).lower() in {
                        "completed", "failed", "terminated", "canceled", "timed_out"
                    }:
                        break
                    await asyncio.sleep(0.5)
                    poll = await client.get(f"{self.base_url}/v1/runs/{run_id}", headers=headers)
                    poll.raise_for_status()
                    data = poll.json()
            output = data.get("output") or {}
            urls = output.get("urls", []) if isinstance(output, dict) else []
            return [str(candidate) for candidate in urls[:page_limit]]
        except (httpx.HTTPError, ValueError, TypeError):
            return []
