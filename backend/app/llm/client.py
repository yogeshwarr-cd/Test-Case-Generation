from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Iterable, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.exceptions import AllLLMProvidersFailed
from app.llm.parser import InvalidJSONResponse, parse_json, parse_model
from app.llm.providers import (
    CerebrasProvider,
    LLMProvider,
    MockLLMProvider,
    ProviderError,
)

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)
_provider_semaphores: dict[tuple[int, str, int], asyncio.Semaphore] = {}
_provider_last_request: dict[str, float] = {}
_provider_unavailable_until: dict[str, float] = {}


def _provider_lane(provider: str) -> str:
    """Pace each configured credential independently."""
    return provider


def _field_path(location: tuple[object, ...]) -> str:
    return ".".join(str(part) for part in location)


def _validation_details(error: ValidationError) -> tuple[list[dict[str, object]], list[str]]:
    details = [
        {"field": _field_path(item["loc"]), "type": item["type"]}
        for item in error.errors()[:20]
    ]
    mandatory = [
        str(item["field"])
        for item in details
        if item["type"] == "missing"
        or (
            item["type"] == "too_short"
            and str(item["field"]).endswith(("steps", "test_cases", "scenarios"))
        )
        or (
            item["type"] in {"model_type", "dict_type"}
            and ".steps." in f".{item['field']}."
        )
    ]
    return details, mandatory


def _salvage_valid_collection(
    content: str, response_model: type[T], error: ValidationError
) -> tuple[T, list[str]] | None:
    """Keep valid generated items when only some batch entries are malformed."""
    invalid: dict[str, set[int]] = {}
    removed_fields: list[str] = []
    for item in error.errors():
        location = item["loc"]
        if (
            len(location) >= 2
            and location[0] in {"test_cases", "scenarios"}
            and isinstance(location[1], int)
            and item["type"] in {"missing", "too_short", "model_type", "dict_type"}
        ):
            invalid.setdefault(str(location[0]), set()).add(location[1])
            removed_fields.append(_field_path(location))
        else:
            return None
    if len(invalid) != 1:
        return None
    payload = parse_json(content)
    collection, indexes = next(iter(invalid.items()))
    items = payload.get(collection)
    if not isinstance(items, list):
        return None
    kept = [item for index, item in enumerate(items) if index not in indexes]
    if not kept:
        return None
    payload[collection] = kept
    try:
        return response_model.model_validate(payload), removed_fields
    except ValidationError:
        return None


def _repair_incomplete_test_case_steps(
    content: str, response_model: type[T], error: ValidationError
) -> tuple[T, list[str]] | None:
    payload = parse_json(content)
    cases = payload.get("test_cases")
    if not isinstance(cases, list):
        return None
    repaired: list[str] = []
    for problem in error.errors():
        loc, kind = problem["loc"], problem["type"]
        if len(loc) == 3 and loc[0] == "test_cases" and loc[2] == "steps" and kind in {"missing", "too_short"}:
            case = cases[loc[1]]
            title = str(case.get("title") or "the described functionality")
            case["steps"] = [{"step_number": 1, "action": f"Verify {title}", "expected_result": f"{title} behaves as described"}]
        elif (
            len(loc) == 5 and loc[0] == "test_cases" and loc[2] == "steps"
            and loc[4] in {"step_number", "action", "expected_result"}
            and kind in {"missing", "string_too_short", "greater_than_equal", "int_parsing"}
        ):
            case, step = cases[loc[1]], cases[loc[1]]["steps"][loc[3]]
            title = str(case.get("title") or "the described functionality")
            step.setdefault("step_number", loc[3] + 1)
            if not str(step.get("action") or "").strip():
                step["action"] = f"Verify {title}"
            if not str(step.get("expected_result") or "").strip():
                step["expected_result"] = f"{title} behaves as described"
        else:
            return None
        repaired.append(_field_path(loc))
    try:
        return response_model.model_validate(payload), repaired
    except (ValidationError, IndexError, KeyError, TypeError):
        return None


def _provider_semaphore(provider: str, concurrency: int) -> asyncio.Semaphore:
    key = (id(asyncio.get_running_loop()), _provider_lane(provider), max(1, concurrency))
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
        provider_cooldown_seconds: dict[str, float] | None = None,
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
        self.unavailable_providers: set[str] = set()
        self.provider_cooldown_seconds = provider_cooldown_seconds or {}

    def _globally_unavailable(self, provider: str) -> bool:
        unavailable_until = _provider_unavailable_until.get(provider, 0)
        if unavailable_until <= time.monotonic():
            _provider_unavailable_until.pop(provider, None)
            return False
        return True

    def _has_later_available_provider(self, current_index: int) -> bool:
        return any(
            provider.name not in self.unavailable_providers
            and not self._globally_unavailable(provider.name)
            for provider in self.providers[current_index + 1 :]
        )

    async def _call(
        self,
        provider: LLMProvider,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
    ):
        lane = _provider_lane(provider.name)
        semaphore = _provider_semaphore(
            provider.name, self.provider_concurrency.get(provider.name, 1)
        )
        async with semaphore:
            interval = self.provider_min_request_interval.get(
                provider.name, self.provider_min_request_interval.get(lane, 0)
            )
            elapsed = time.monotonic() - _provider_last_request.get(lane, 0)
            if interval > 0 and elapsed < interval:
                delay = interval - elapsed
                logger.info(
                    "LLM provider request spacing provider=%s model=%s delay_seconds=%s",
                    provider.name, provider.model, round(delay, 3),
                )
                await asyncio.sleep(delay)
            _provider_last_request[lane] = time.monotonic()
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
                if not hasattr(item, "generation_metadata"):
                    continue
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
        failures: dict[str, dict[str, object]] = {}
        compact_schema = json.dumps(response_model.model_json_schema(), separators=(",", ":"))
        schema_system_prompt = (
            f"{system_prompt}\nPopulate every required field in the JSON schema. Never omit required "
            "arrays or return them empty when minItems is 1. Every test_cases[].steps item must be a "
            "JSON object containing step_number, action, and expected_result. Never return steps as "
            f"strings and never omit the steps field. JSON schema:{compact_schema}"
        )
        for provider_index, provider in enumerate(self.providers):
            if provider.name in self.unavailable_providers or self._globally_unavailable(provider.name):
                logger.info(
                    "LLM provider skipped provider=%s model=%s request_id=%s reason=provider_cooldown_or_client_unavailable",
                    provider.name, provider.model, request_id,
                )
                continue
            attempted.append(provider.name)
            repair_attempted = False
            mandatory_regeneration_attempted = False
            retry_count = (
                self.cerebras_provider_retry_count
                if provider.name.startswith("cerebras")
                else self.provider_retry_count
            )
            for attempt in range(retry_count + 1):
                started = time.perf_counter()
                try:
                    response = await self._call(
                        provider, schema_system_prompt, user_prompt, response_model
                    )
                    if not response.content or not response.content.strip():
                        logger.warning(
                            "LLM response rejected provider=%s model=%s request_id=%s failure_type=empty_response",
                            provider.name, provider.model, request_id,
                        )
                        raise ProviderError("empty_response")
                    try:
                        result = parse_model(response.content, response_model)
                    except InvalidJSONResponse as invalid_json:
                        logger.warning(
                            "LLM response rejected provider=%s model=%s request_id=%s failure_type=invalid_json content_length=%s reason=%s",
                            provider.name, provider.model, request_id,
                            len(response.content), str(invalid_json),
                        )
                        if not settings.llm_structured_output_repair_enabled or repair_attempted:
                            raise ProviderError("invalid_json") from invalid_json
                        repair_attempted = True
                        repair_prompt = (
                            "Return a valid JSON object matching this schema. Preserve the original meaning "
                            f"and do not add unsupported fields. Schema:{compact_schema}\n"
                            f"Invalid output:{response.content[:12000]}"
                        )
                        repaired = await self._call(
                            provider,
                            "You repair invalid JSON. Return JSON only.",
                            repair_prompt,
                            response_model,
                        )
                        result = parse_model(repaired.content, response_model)
                        response = repaired
                    except ValidationError as validation_error:
                        validation_summary, missing_fields = _validation_details(validation_error)
                        failure_type = (
                            "missing_required_fields" if missing_fields else "schema_validation_error"
                        )
                        logger.warning(
                            "LLM response rejected provider=%s model=%s request_id=%s failure_type=%s content_length=%s missing_fields=%s validation_errors=%s",
                            provider.name, provider.model, request_id,
                            failure_type, len(response.content), missing_fields, validation_summary,
                        )
                        local_repair = _repair_incomplete_test_case_steps(
                            response.content, response_model, validation_error
                        )
                        if local_repair is not None:
                            result, repaired_fields = local_repair
                            self._record_metadata(result, response.provider, response.model)
                            logger.warning(
                                "LLM incomplete test-case steps repaired locally provider=%s model=%s request_id=%s repaired_fields=%s",
                                response.provider, response.model, request_id, repaired_fields,
                            )
                            return result
                        salvaged = _salvage_valid_collection(
                            response.content, response_model, validation_error
                        )
                        if missing_fields and salvaged is not None:
                            result, removed_fields = salvaged
                            self._record_metadata(result, response.provider, response.model)
                            logger.warning(
                                "LLM malformed batch items removed without full regeneration provider=%s model=%s request_id=%s removed_fields=%s",
                                response.provider, response.model, request_id, removed_fields,
                            )
                            return result
                        if missing_fields and not mandatory_regeneration_attempted:
                            mandatory_regeneration_attempted = True
                            regeneration_prompt = (
                                "Regenerate the complete JSON response. The prior response omitted or emptied "
                                f"mandatory fields: {missing_fields}. Populate every required field, especially "
                                "test_cases[].steps with at least one JSON object containing step_number, action, "
                                "and expected_result. Do not return steps as strings and never omit steps. "
                                f"Return JSON only. Schema:{compact_schema}\n"
                                f"Original request:{user_prompt}\nInvalid response:{response.content[:12000]}"
                            )
                            regenerated = await self._call(
                                provider,
                                schema_system_prompt,
                                regeneration_prompt,
                                response_model,
                            )
                            if not regenerated.content or not regenerated.content.strip():
                                raise ProviderError("empty_response")
                            try:
                                result = parse_model(regenerated.content, response_model)
                            except InvalidJSONResponse as regenerated_json_error:
                                logger.warning(
                                    "LLM mandatory-field regeneration failed provider=%s model=%s request_id=%s failure_type=invalid_json",
                                    provider.name, provider.model, request_id,
                                )
                                raise ProviderError("invalid_json") from regenerated_json_error
                            except ValidationError as regenerated_validation_error:
                                regenerated_details, regenerated_missing = _validation_details(
                                    regenerated_validation_error
                                )
                                salvaged = _salvage_valid_collection(
                                    regenerated.content,
                                    response_model,
                                    regenerated_validation_error,
                                )
                                if salvaged is not None:
                                    result, removed_fields = salvaged
                                    response = regenerated
                                    self._record_metadata(result, response.provider, response.model)
                                    logger.warning(
                                        "LLM malformed batch items removed provider=%s model=%s request_id=%s removed_fields=%s",
                                        response.provider, response.model, request_id, removed_fields,
                                    )
                                    return result
                                logger.warning(
                                    "LLM mandatory-field regeneration failed provider=%s model=%s request_id=%s failure_type=%s missing_fields=%s validation_errors=%s",
                                    provider.name, provider.model, request_id,
                                    "missing_required_fields" if regenerated_missing else "schema_validation_error",
                                    regenerated_missing, regenerated_details,
                                )
                                raise ProviderError(
                                    "missing_required_fields"
                                    if regenerated_missing
                                    else "schema_validation_error"
                                ) from regenerated_validation_error
                            response = regenerated
                            self._record_metadata(result, response.provider, response.model)
                            logger.info(
                                "LLM mandatory-field regeneration succeeded provider=%s model=%s request_id=%s",
                                response.provider, response.model, request_id,
                            )
                            return result
                        elif missing_fields:
                            raise ProviderError("missing_required_fields") from validation_error
                        if not settings.llm_structured_output_repair_enabled:
                            raise ProviderError("schema_validation_error") from validation_error
                        if repair_attempted:
                            raise ProviderError("schema_validation_error") from validation_error
                        repair_attempted = True
                        compact_error = str(validation_error)[:2000]
                        invalid_output = response.content[:12000]
                        repair_prompt = (
                            "Correct this output to match the schema. Return JSON only; preserve supplied IDs "
                            "and meaning; do not add unsupported fields.\n"
                            f"Schema:{compact_schema}\nErrors:{compact_error}\nOutput:{invalid_output}"
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
                except InvalidJSONResponse:
                    error = ProviderError("invalid_json")
                except ValidationError as validation_error:
                    _, missing_fields = _validation_details(validation_error)
                    error = ProviderError(
                        "missing_required_fields" if missing_fields else "schema_validation_error"
                    )
                logger.warning(
                    "LLM generation failed provider=%s model=%s request_id=%s attempt=%s retry_count=%s failure_reason=%s http_status=%s provider_message=%s latency_ms=%s",
                    provider.name, provider.model, request_id, attempt + 1, attempt, error.category,
                    error.status_code, error.provider_message or "-",
                    round((time.perf_counter() - started) * 1000),
                )
                failures[provider.name] = {
                    "category": error.category,
                    "status_code": error.status_code,
                    "retry_after": error.retry_after,
                }
                if error.category in {
                    "authentication",
                    "missing_configuration",
                    "permission_denied",
                    "quota_exceeded",
                    "unsupported_model",
                }:
                    self.unavailable_providers.add(provider.name)
                    cooldown = self.provider_cooldown_seconds.get(provider.name, 0)
                    if cooldown > 0:
                        _provider_unavailable_until[provider.name] = (
                            time.monotonic() + cooldown
                        )
                if provider.name.startswith("cerebras") and error.category == "quota_exceeded":
                    logger.warning(
                        "LLM provider fallback provider=%s model=%s request_id=%s error_category=%s decision=immediate_fallback",
                        provider.name, provider.model, request_id, error.category,
                    )
                    break
                if provider.name.startswith("cerebras") and error.category == "queue_exceeded":
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
                if error.category == "temporary_provider_error" and attempt < retry_count:
                    delay = self.rate_limit_backoff_seconds * (2**attempt)
                    delay += random.uniform(0, self.rate_limit_jitter_seconds)
                    logger.warning(
                        "LLM temporary-error retry scheduled provider=%s model=%s request_id=%s next_attempt=%s backoff_seconds=%s http_status=%s",
                        provider.name, provider.model, request_id, attempt + 2,
                        delay, error.status_code,
                    )
                    await asyncio.sleep(delay)
                    continue
                if error.category != "rate_limited" or attempt >= retry_count:
                    break
                if (
                    error.retry_after is not None
                    and error.retry_after > self.rate_limit_fallback_threshold_seconds
                    and self._has_later_available_provider(provider_index)
                ):
                    _provider_unavailable_until[provider.name] = (
                        time.monotonic() + error.retry_after
                    )
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
        raise AllLLMProvidersFailed(attempted, failures)


def build_llm_client(task: str = "generation", *, mock_mode: bool | None = None) -> LLMClient:
    task = task if task in {"generation", "validation", "regeneration"} else "generation"
    use_mock = settings.app_mock_mode if mock_mode is None else mock_mode
    if use_mock:
        return LLMClient(
            [MockLLMProvider()],
            timeout=settings.llm_request_timeout_seconds,
            temperature=0,
            max_output_tokens=getattr(settings, f"llm_{task}_max_output_tokens", settings.llm_max_output_tokens),
            provider_retry_count=0,
            cerebras_provider_retry_count=0,
        )
    model_by_provider = {
        "cerebras": getattr(settings, f"cerebras_{task}_model") or settings.cerebras_model,
        "cerebras_fallback": settings.cerebras_fallback_model or settings.cerebras_model,
    }
    max_output_tokens = getattr(settings, f"llm_{task}_max_output_tokens")
    provider_map = {
        "cerebras": CerebrasProvider(
            settings.cerebras_api_key, model_by_provider["cerebras"]
        ),
        "cerebras_fallback": CerebrasProvider(
            settings.cerebras_fallback_api_key,
            model_by_provider["cerebras_fallback"],
            provider_name="cerebras_fallback",
        ),
    }
    providers = [provider_map["cerebras"]]
    if settings.cerebras_fallback_api_key:
        providers.append(provider_map["cerebras_fallback"])
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
            "cerebras_fallback": settings.cerebras_max_concurrent_requests,
        },
        provider_min_request_interval={
            "cerebras": settings.cerebras_min_request_interval_seconds,
            "cerebras_fallback": settings.cerebras_min_request_interval_seconds,
        },
        cerebras_provider_retry_count=settings.cerebras_provider_retry_count,
        cerebras_initial_backoff_seconds=settings.cerebras_initial_backoff_seconds,
        cerebras_max_backoff_seconds=settings.cerebras_max_backoff_seconds,
        provider_cooldown_seconds={
            "cerebras": settings.cerebras_quota_cooldown_seconds,
            "cerebras_fallback": settings.cerebras_quota_cooldown_seconds,
        },
    )
