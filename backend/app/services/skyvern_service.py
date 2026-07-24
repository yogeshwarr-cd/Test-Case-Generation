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
    attempts: int = 0


class SkyvernAdapter:
    """Optional, bounded execution recovery client; never participates in generation."""

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
        # Recovery is deliberately bounded.  A recovery provider must never
        # turn a single failed action into an unbounded execution loop.
        max_attempts = min(2, max(1, int(settings.skyvern_max_attempts)))
        attempts = 0
        for _ in range(max_attempts):
            attempts += 1
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
                        attempts,
                    )
                last_message = f"Skyvern returned HTTP {response.status_code}"
            except (httpx.HTTPError, ValueError) as exc:
                last_message = type(exc).__name__
        return SkyvernRecovery(True, False, message=last_message, attempts=attempts)
