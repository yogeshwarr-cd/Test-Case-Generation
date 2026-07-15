from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Iterable, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import AllLLMProvidersFailed
from app.llm.parser import parse_model
from app.llm.providers import (
    CerebrasProvider,
    GeminiProvider,
    GroqProvider,
    LLMProvider,
    OpenAIProvider,
    ProviderError,
)

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)
_provider_semaphores: dict[tuple[int, str, int], asyncio.Semaphore] = {}
_provider_last_request: dict[str, float] = {}


def _provider_semaphore(provider: str, concurrency: int) -> asyncio.Semaphore:
    key = (id(asyncio.get_running_loop()), provider, max(1, concurrency))
    if key not in _provider_semaphores:
        _provider_semaphores[key] = asyncio.Semaphore(key[2])
    return _provider_semaphores[key]


class LLMClient:
    def __init__(
        self,
        providers: Iterable[LLMProvider],
        *,
        timeout: float = 60,
        temperature: float = 0.2,
        max_output_tokens: int = 6000,
        provider_retry_count: int = 1,
        rate_limit_backoff_seconds: float = 1.0,
        rate_limit_jitter_seconds: float = 0.25,
        rate_limit_fallback_threshold_seconds: float = 10.0,
        provider_concurrency: dict[str, int] | None = None,
        provider_min_request_interval: dict[str, float] | None = None,
        cerebras_provider_retry_count: int = 1,
        cerebras_initial_backoff_seconds: float = 2.0,
        cerebras_max_backoff_seconds: float = 10.0,
    ):
        self.providers = list(providers)
        self.timeout = timeout
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.provider_retry_count = provider_retry_count
        self.rate_limit_backoff_seconds = rate_limit_backoff_seconds
        self.rate_limit_jitter_seconds = rate_limit_jitter_seconds
        self.rate_limit_fallback_threshold_seconds = rate_limit_fallback_threshold_seconds
        self.provider_concurrency = provider_concurrency or {}
        self.provider_min_request_interval = provider_min_request_interval or {}
        self.cerebras_provider_retry_count = cerebras_provider_retry_count
        self.cerebras_initial_backoff_seconds = cerebras_initial_backoff_seconds
        self.cerebras_max_backoff_seconds = cerebras_max_backoff_seconds

    async def _call(
        self,
        provider: LLMProvider,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ):
        semaphore = _provider_semaphore(
            provider.name, self.provider_concurrency.get(provider.name, 1)
        )
        async with semaphore:
            interval = self.provider_min_request_interval.get(provider.name, 0)
            elapsed = time.monotonic() - _provider_last_request.get(provider.name, 0)
            if interval > 0 and elapsed < interval:
                delay = interval - elapsed
                logger.info(
                    "LLM provider request spacing provider=%s model=%s delay_seconds=%s",
                    provider.name, provider.model, round(delay, 3),
                )
                await asyncio.sleep(delay)
            _provider_last_request[provider.name] = time.monotonic()
            return await asyncio.wait_for(
                provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_model=response_model,
                    timeout=self.timeout,
                    temperature=self.temperature,
                    max_output_tokens=self.max_output_tokens,
                ),
                timeout=self.timeout,
            )

    @staticmethod
    def _record_metadata(result: T, provider: str, model: str) -> None:
        for collection_name in ("scenarios", "test_cases"):
            for item in getattr(result, collection_name, []):
                metadata = dict(getattr(item, "generation_metadata", {}) or {})
                metadata.update({"provider": provider, "model": model})
                item.generation_metadata = metadata

    async def generate_structured_output(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        request_id: str | None = None,
    ) -> T:
        attempted: list[str] = []
        for provider in self.providers:
            attempted.append(provider.name)
            repair_attempted = False
            retry_count = (
                self.cerebras_provider_retry_count
                if provider.name == "cerebras"
                else self.provider_retry_count
            )
            for attempt in range(retry_count + 1):
                started = time.perf_counter()
                try:
                    response = await self._call(provider, system_prompt, user_prompt, response_model)
                    try:
                        result = parse_model(response.content, response_model)
                    except (ValueError, ValidationError) as validation_error:
                        if repair_attempted:
                            raise ProviderError("invalid_structured_output") from validation_error
                        repair_attempted = True
                        repair_prompt = (
                            "Correct the invalid output below. Return corrected JSON only. Preserve the "
                            "business meaning and supplied IDs. Do not invent requirements or add unsupported "
                            f"fields. Validation errors: {validation_error}. Required schema: "
                            f"{response_model.model_json_schema()}. Invalid output: {response.content}"
                        )
                        repaired = await self._call(
                            provider,
                            "You repair JSON to match an exact schema. Return JSON only.",
                            repair_prompt,
                            response_model,
                        )
                        result = parse_model(repaired.content, response_model)
                        response = repaired
                    self._record_metadata(result, response.provider, response.model)
                    logger.info(
                        "LLM generation succeeded provider=%s model=%s request_id=%s attempt=%s retry_count=%s latency_ms=%s token_usage=%s",
                        response.provider, response.model, request_id, attempt + 1, attempt,
                        round((time.perf_counter() - started) * 1000), response.token_usage,
                    )
                    return result
                except asyncio.TimeoutError:
                    error = ProviderError("timeout")
                except ProviderError as exc:
                    error = exc
                except (ValueError, ValidationError):
                    error = ProviderError("invalid_structured_output")
                logger.warning(
                    "LLM generation failed provider=%s model=%s request_id=%s attempt=%s retry_count=%s failure_reason=%s http_status=%s provider_message=%s latency_ms=%s",
                    provider.name, provider.model, request_id, attempt + 1, attempt, error.category,
                    error.status_code, error.provider_message or "-",
                    round((time.perf_counter() - started) * 1000),
                )
                if provider.name == "cerebras" and error.category == "quota_exceeded":
                    logger.warning(
                        "LLM provider fallback provider=%s model=%s request_id=%s error_category=%s decision=immediate_fallback",
                        provider.name, provider.model, request_id, error.category,
                    )
                    break
                if provider.name == "cerebras" and error.category == "queue_exceeded":
                    if attempt >= retry_count:
                        logger.warning(
                            "LLM provider fallback provider=%s model=%s request_id=%s error_category=%s decision=retry_exhausted",
                            provider.name, provider.model, request_id, error.category,
                        )
                        break
                    delay = min(
                        self.cerebras_initial_backoff_seconds * (2**attempt),
                        self.cerebras_max_backoff_seconds,
                    ) + random.uniform(0, self.rate_limit_jitter_seconds)
                    logger.warning(
                        "LLM provider retry scheduled provider=%s model=%s request_id=%s error_category=%s retry_delay_seconds=%s next_attempt=%s",
                        provider.name, provider.model, request_id, error.category, delay,
                        attempt + 2,
                    )
                    await asyncio.sleep(delay)
                    continue
                if error.category != "rate_limited" or attempt >= retry_count:
                    break
                if (
                    error.retry_after is not None
                    and error.retry_after > self.rate_limit_fallback_threshold_seconds
                ):
                    logger.warning(
                        "LLM rate-limit fallback provider=%s model=%s request_id=%s retry_after_seconds=%s threshold_seconds=%s",
                        provider.name, provider.model, request_id, error.retry_after,
                        self.rate_limit_fallback_threshold_seconds,
                    )
                    break
                delay = self.rate_limit_backoff_seconds * (2**attempt)
                if error.retry_after is not None:
                    delay = max(delay, error.retry_after)
                delay += random.uniform(0, self.rate_limit_jitter_seconds)
                logger.warning(
                    "LLM rate-limit retry scheduled provider=%s model=%s request_id=%s next_attempt=%s backoff_seconds=%s http_status=%s",
                    provider.name, provider.model, request_id, attempt + 2, delay,
                    error.status_code,
                )
                await asyncio.sleep(delay)
        raise AllLLMProvidersFailed(attempted)


def build_llm_client(task: str = "generation") -> LLMClient:
    task = task if task in {"generation", "validation", "regeneration"} else "generation"
    model_by_provider = {
        "cerebras": getattr(settings, f"cerebras_{task}_model") or settings.cerebras_model,
        "groq": getattr(settings, f"groq_{task}_model") or settings.groq_model,
        "gemini": getattr(settings, f"gemini_{task}_model") or settings.gemini_model,
        "openai": getattr(settings, f"openai_{task}_model") or settings.openai_model,
    }
    max_output_tokens = getattr(settings, f"llm_{task}_max_output_tokens")
    provider_map = {
        "cerebras": CerebrasProvider(
            settings.cerebras_api_key, model_by_provider["cerebras"]
        ),
        "groq": GroqProvider(
            settings.groq_api_key,
            model_by_provider["groq"],
            max_output_tokens=min(settings.groq_max_output_tokens, max_output_tokens),
            structured_output=getattr(settings, f"groq_{task}_structured_output"),
        ),
        "gemini": GeminiProvider(settings.gemini_api_key, model_by_provider["gemini"]),
        "openai": OpenAIProvider(settings.openai_api_key, model_by_provider["openai"]),
    }
    order = [settings.llm_primary_provider.lower(), *settings.llm_fallback_providers]
    providers = [provider_map[name] for name in order if name in provider_map]
    return LLMClient(
        providers,
        timeout=settings.llm_request_timeout_seconds,
        temperature=settings.llm_temperature,
        max_output_tokens=max_output_tokens,
        provider_retry_count=settings.llm_provider_retry_count,
        rate_limit_backoff_seconds=settings.llm_rate_limit_backoff_seconds,
        rate_limit_jitter_seconds=settings.llm_rate_limit_jitter_seconds,
        rate_limit_fallback_threshold_seconds=settings.llm_rate_limit_fallback_threshold_seconds,
        provider_concurrency={
            "cerebras": settings.cerebras_max_concurrent_requests,
            "groq": settings.groq_concurrency,
            "gemini": settings.gemini_concurrency,
            "openai": settings.openai_concurrency,
        },
        provider_min_request_interval={
            "cerebras": settings.cerebras_min_request_interval_seconds,
        },
        cerebras_provider_retry_count=settings.cerebras_provider_retry_count,
        cerebras_initial_backoff_seconds=settings.cerebras_initial_backoff_seconds,
        cerebras_max_backoff_seconds=settings.cerebras_max_backoff_seconds,
    )
