from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass
class ProviderResponse:
    content: str
    provider: str
    model: str
    token_usage: dict[str, int] | None = None


class ProviderError(RuntimeError):
    def __init__(self, category: str, *, recoverable: bool = False):
        self.category = category
        self.recoverable = recoverable
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


def _classify_error(exc: Exception) -> ProviderError:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if "timeout" in name or "timeout" in message:
        return ProviderError("timeout", recoverable=True)
    if status in {401, 403} or "authentication" in name or "unauthorized" in message or "api key" in message:
        return ProviderError("authentication")
    if "quota" in message or "resource_exhausted" in name:
        return ProviderError("quota_exceeded")
    if status == 429 or "ratelimit" in name or "rate limit" in message:
        return ProviderError("rate_limited", recoverable=True)
    if status in {408, 409, 500, 502, 503, 504} or "connection" in name:
        return ProviderError("temporary_provider_error", recoverable=True)
    if status == 404 or "model" in message and ("unsupported" in message or "not found" in message):
        return ProviderError("unsupported_model")
    return ProviderError("provider_error")


def _schema(response_model: type[BaseModel]) -> dict[str, Any]:
    return response_model.model_json_schema()


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str, client: Any = None):
        self.api_key, self.model, self._client = api_key, model, client

    async def generate(self, **kwargs: Any) -> ProviderResponse:
        if not self.api_key or not self.model:
            raise ProviderError("missing_configuration")
        try:
            if self._client is None:
                from groq import AsyncGroq
                self._client = AsyncGroq(api_key=self.api_key, max_retries=0)
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


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, client: Any = None):
        self.api_key, self.model, self._client = api_key, model, client

    async def generate(self, **kwargs: Any) -> ProviderResponse:
        if not self.api_key or not self.model:
            raise ProviderError("missing_configuration")
        try:
            from google.genai import types
            if self._client is None:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=kwargs["user_prompt"],
                config=types.GenerateContentConfig(
                    system_instruction=kwargs["system_prompt"],
                    temperature=kwargs["temperature"],
                    max_output_tokens=kwargs["max_output_tokens"],
                    response_mime_type="application/json",
                    response_json_schema=_schema(kwargs["response_model"]),
                    http_options=types.HttpOptions(timeout=int(kwargs["timeout"] * 1000)),
                ),
            )
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
