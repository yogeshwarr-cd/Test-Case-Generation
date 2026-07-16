from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import json
import re
from typing import Any

from pydantic import BaseModel


@dataclass
class ProviderResponse:
    content: str
    provider: str
    model: str
    token_usage: dict[str, int] | None = None


class ProviderError(RuntimeError):
    def __init__(
        self,
        category: str,
        *,
        recoverable: bool = False,
        status_code: int | None = None,
        provider_message: str = "",
        retry_after: float | None = None,
    ):
        self.category = category
        self.recoverable = recoverable
        self.status_code = status_code
        self.provider_message = provider_message
        self.retry_after = retry_after
        super().__init__(category)


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        timeout: float,
        temperature: float,
        max_output_tokens: int,
    ) -> ProviderResponse: ...


def _status_code(exc: Exception) -> int | None:
    raw = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _safe_message(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    message = re.sub(r"(?i)(authorization|api[_ -]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", message)
    message = re.sub(r"\b(?:sk|gsk)[-_][A-Za-z0-9_-]+", "[REDACTED]", message)
    message = re.sub(r"\bAQ\.[A-Za-z0-9_-]+", "[REDACTED]", message)
    return message[:500]


def _retry_after(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    value = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        match = re.search(
            r"(?:try again|retry) in\s+([0-9.]+)s",
            str(exc),
            flags=re.I,
        )
        return float(match.group(1)) if match else None


def _classify_error(exc: Exception) -> ProviderError:
    name = type(exc).__name__.lower()
    provider_message = _safe_message(exc)
    message = provider_message.lower()
    status = _status_code(exc)
    details = {"status_code": status, "provider_message": provider_message}
    if "request_quota_exceeded" in message:
        return ProviderError("quota_exceeded", **details)
    if "queue_exceeded" in message:
        return ProviderError("queue_exceeded", recoverable=True, **details)
    if "timeout" in name or "timeout" in message:
        return ProviderError("timeout", **details)
    if status == 401 or "authentication" in name or "unauthorized" in message or "invalid api key" in message:
        return ProviderError("authentication", **details)
    retry_after = _retry_after(exc)
    if status == 429 and retry_after is not None:
        return ProviderError(
            "rate_limited",
            recoverable=True,
            retry_after=retry_after,
            **details,
        )
    if "insufficient_quota" in message or "quota" in message or "resource_exhausted" in name:
        return ProviderError("quota_exceeded", **details)
    if (
        status == 429
        or (status == 413 and ("tokens per minute" in message or "request too large" in message))
        or "ratelimit" in name
        or "rate limit" in message
        or "rate_limit_exceeded" in message
    ):
        return ProviderError(
            "rate_limited", recoverable=True, retry_after=_retry_after(exc), **details
        )
    if status in {408, 409, 500, 502, 503, 504} or "connection" in name:
        return ProviderError("temporary_provider_error", **details)
    if status == 403:
        return ProviderError("permission_denied", **details)
    if "model" in message and any(
        marker in message for marker in ("unsupported", "not found", "no longer available")
    ):
        return ProviderError("unsupported_model", **details)
    if status == 404:
        return ProviderError("not_found", **details)
    return ProviderError("provider_error", **details)


def _schema(response_model: type[BaseModel]) -> dict[str, Any]:
    return response_model.model_json_schema()


def _gemini_schema(response_model: type[BaseModel]) -> dict[str, Any]:
    """Return Gemini's supported JSON Schema subset without weakening validation."""
    unsupported = {
        "$schema",
        "additionalProperties",
        "patternProperties",
        "unevaluatedProperties",
    }

    def sanitize(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: sanitize(item)
                for key, item in value.items()
                if key not in unsupported
            }
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        return value

    return sanitize(response_model.model_json_schema())


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(
        self, api_key: str, model: str, client: Any = None, max_output_tokens: int = 1500,
        structured_output: bool = True,
    ):
        self.api_key, self.model, self._client = api_key, model, client
        self.max_output_tokens = max_output_tokens
        self.structured_output = structured_output

    async def generate(self, **kwargs: Any) -> ProviderResponse:
        if not self.api_key or not self.model:
            raise ProviderError("missing_configuration")
        try:
            if self._client is None:
                from groq import AsyncGroq
                self._client = AsyncGroq(api_key=self.api_key, max_retries=0)
            response_format = (
                {
                    "type": "json_schema",
                    "json_schema": {
                        "name": kwargs["response_model"].__name__,
                        "strict": False,
                        "schema": _schema(kwargs["response_model"]),
                    },
                }
                if self.structured_output
                else {"type": "json_object"}
            )
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": kwargs["system_prompt"]},
                    {"role": "user", "content": kwargs["user_prompt"]},
                ],
                temperature=kwargs["temperature"],
                max_completion_tokens=min(
                    kwargs["max_output_tokens"], self.max_output_tokens
                ),
                response_format=response_format,
                timeout=kwargs["timeout"],
            )
            content = completion.choices[0].message.content or ""
            if not content.strip():
                raise ProviderError("empty_response")
            usage = getattr(completion, "usage", None)
            token_usage = None if usage is None else {
                "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            }
            return ProviderResponse(content, self.name, self.model, token_usage)
        except ProviderError:
            raise
        except Exception as exc:
            raise _classify_error(exc) from exc


class CerebrasProvider(LLMProvider):
    name = "cerebras"

    def __init__(self, api_key: str, model: str, client: Any = None):
        self.api_key, self.model, self._client = api_key, model, client

    async def generate(self, **kwargs: Any) -> ProviderResponse:
        if not self.api_key or not self.model:
            raise ProviderError("missing_configuration")
        try:
            if self._client is None:
                from cerebras.cloud.sdk import AsyncCerebras

                self._client = AsyncCerebras(
                    api_key=self.api_key, max_retries=0, timeout=kwargs["timeout"]
                )
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": kwargs["system_prompt"]},
                    {"role": "user", "content": kwargs["user_prompt"]},
                ],
                temperature=kwargs["temperature"],
                max_completion_tokens=kwargs["max_output_tokens"],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": kwargs["response_model"].__name__,
                        "strict": False,
                        "schema": _schema(kwargs["response_model"]),
                    },
                },
            )
            content = completion.choices[0].message.content or ""
            if not content.strip():
                raise ProviderError("empty_response")
            usage = getattr(completion, "usage", None)
            token_usage = None if usage is None else {
                "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            }
            return ProviderResponse(content, self.name, self.model, token_usage)
        except ProviderError:
            raise
        except Exception as exc:
            raise _classify_error(exc) from exc


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str,
        client: Any = None,
        *,
        provider_name: str = "gemini",
        thinking_level: str = "low",
        min_output_tokens: int = 4096,
    ):
        self.api_key, self.model, self._client = api_key, model, client
        self.name = provider_name
        self.thinking_level = thinking_level
        self.min_output_tokens = min_output_tokens

    async def generate(self, **kwargs: Any) -> ProviderResponse:
        if not self.api_key or not self.model:
            raise ProviderError("missing_configuration")
        try:
            from google.genai import types
            if self._client is None:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            thinking_config = (
                types.ThinkingConfig(thinking_budget=0)
                if self.model.startswith("gemini-2.5")
                else types.ThinkingConfig(thinking_level=self.thinking_level)
            )
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=kwargs["user_prompt"],
                config=types.GenerateContentConfig(
                    system_instruction=kwargs["system_prompt"],
                    temperature=kwargs["temperature"],
                    max_output_tokens=max(
                        kwargs["max_output_tokens"], self.min_output_tokens
                    ),
                    response_mime_type="application/json",
                    response_json_schema=_gemini_schema(kwargs["response_model"]),
                    thinking_config=thinking_config,
                    http_options=types.HttpOptions(timeout=int(kwargs["timeout"] * 1000)),
                ),
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, BaseModel):
                content = parsed.model_dump_json()
            elif parsed is not None:
                content = json.dumps(parsed, separators=(",", ":"))
            else:
                content = response.text or ""
            if not content.strip():
                raise ProviderError("empty_response")
            usage = getattr(response, "usage_metadata", None)
            token_usage = None if usage is None else {
                "input_tokens": int(getattr(usage, "prompt_token_count", 0) or 0),
                "output_tokens": int(getattr(usage, "candidates_token_count", 0) or 0),
            }
            return ProviderResponse(content, self.name, self.model, token_usage)
        except ProviderError:
            raise
        except Exception as exc:
            raise _classify_error(exc) from exc


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, client: Any = None):
        self.api_key, self.model, self._client = api_key, model, client

    async def generate(self, **kwargs: Any) -> ProviderResponse:
        if not self.api_key or not self.model:
            raise ProviderError("missing_configuration")
        try:
            if self._client is None:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key, max_retries=0, timeout=kwargs["timeout"])
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": kwargs["system_prompt"]},
                    {"role": "user", "content": kwargs["user_prompt"]},
                ],
                temperature=kwargs["temperature"],
                max_completion_tokens=kwargs["max_output_tokens"],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": kwargs["response_model"].__name__,
                        "strict": False,
                        "schema": _schema(kwargs["response_model"]),
                    },
                },
            )
            content = completion.choices[0].message.content or ""
            if not content.strip():
                raise ProviderError("empty_response")
            usage = getattr(completion, "usage", None)
            token_usage = None if usage is None else {
                "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
                "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            }
            return ProviderResponse(content, self.name, self.model, token_usage)
        except ProviderError:
            raise
        except Exception as exc:
            raise _classify_error(exc) from exc
