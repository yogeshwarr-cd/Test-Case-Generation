from __future__ import annotations

import asyncio
import logging
import time
from typing import Iterable, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import AllLLMProvidersFailed
from app.llm.parser import parse_model
from app.llm.providers import (
    GeminiProvider,
    GroqProvider,
    LLMProvider,
    OpenAIProvider,
    ProviderError,
)

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(
        self,
        providers: Iterable[LLMProvider],
        *,
        timeout: float = 60,
        temperature: float = 0.2,
        max_output_tokens: int = 6000,
        provider_retry_count: int = 1,
    ):
        self.providers = list(providers)
        self.timeout = timeout
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.provider_retry_count = provider_retry_count

    async def _call(
        self,
        provider: LLMProvider,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ):
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
            for attempt in range(self.provider_retry_count + 1):
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
                        "LLM generation succeeded provider=%s model=%s request_id=%s attempt=%s latency_ms=%s token_usage=%s",
                        response.provider, response.model, request_id, attempt + 1,
                        round((time.perf_counter() - started) * 1000), response.token_usage,
                    )
                    return result
                except asyncio.TimeoutError:
                    error = ProviderError("timeout", recoverable=True)
                except ProviderError as exc:
                    error = exc
                except (ValueError, ValidationError):
                    error = ProviderError("invalid_structured_output")
                logger.warning(
                    "LLM generation failed provider=%s model=%s request_id=%s attempt=%s category=%s latency_ms=%s",
                    provider.name, provider.model, request_id, attempt + 1, error.category,
                    round((time.perf_counter() - started) * 1000),
                )
                if not error.recoverable or attempt >= self.provider_retry_count:
                    break
        raise AllLLMProvidersFailed(attempted)


def build_llm_client() -> LLMClient:
    provider_map = {
        "groq": GroqProvider(settings.groq_api_key, settings.groq_model),
        "gemini": GeminiProvider(settings.gemini_api_key, settings.gemini_model),
        "openai": OpenAIProvider(settings.openai_api_key, settings.openai_model),
    }
    order = [settings.llm_primary_provider.lower(), *settings.llm_fallback_providers]
    providers = [provider_map[name] for name in order if name in provider_map]
    return LLMClient(
        providers,
        timeout=settings.llm_request_timeout_seconds,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
        provider_retry_count=settings.llm_provider_retry_count,
    )
