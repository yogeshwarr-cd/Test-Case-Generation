import asyncio
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.core.exceptions import AllLLMProvidersFailed
from app.llm.client import LLMClient
from app.llm.providers import (
    CerebrasProvider,
    LLMProvider,
    ProviderError,
    ProviderResponse,
    _classify_error,
)


class Output(BaseModel):
    value: str


class StubProvider(LLMProvider):
    def __init__(self, name, outcomes, model="test-model"):
        self.name, self.model, self.outcomes = name, model, list(outcomes)
        self.calls = 0

    async def generate(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return ProviderResponse(outcome, self.name, self.model)


async def generate(client):
    return await client.generate_structured_output(
        system_prompt="system", user_prompt="user", response_model=Output, request_id="request-1"
    )


@pytest.mark.asyncio
async def test_groq_success_stops_fallback_chain():
    groq, gemini = StubProvider("groq", ['{"value":"groq"}']), StubProvider("gemini", ['{"value":"gemini"}'])
    result = await generate(LLMClient([groq, gemini]))
    assert result.value == "groq" and gemini.calls == 0


@pytest.mark.asyncio
async def test_groq_auth_failure_falls_back_to_gemini():
    groq = StubProvider("groq", [ProviderError("authentication")])
    gemini = StubProvider("gemini", ['{"value":"gemini"}'])
    assert (await generate(LLMClient([groq, gemini]))).value == "gemini"
    assert groq.calls == 1


@pytest.mark.asyncio
async def test_gemini_quota_failure_falls_back_to_openai():
    providers = [
        StubProvider("groq", [ProviderError("provider_error")]),
        StubProvider("gemini", [ProviderError("quota_exceeded")]),
        StubProvider("openai", ['{"value":"openai"}']),
    ]
    assert (await generate(LLMClient(providers))).value == "openai"


@pytest.mark.asyncio
async def test_rate_limit_is_retried_once(monkeypatch):
    delays = []
    async def record_sleep(delay):
        delays.append(delay)
    monkeypatch.setattr("app.llm.client.asyncio.sleep", record_sleep)
    groq = StubProvider(
        "groq",
        [ProviderError("rate_limited", recoverable=True, status_code=429, retry_after=2), '{"value":"ok"}'],
    )
    assert (
        await generate(
            LLMClient(
                [groq], provider_retry_count=1, rate_limit_backoff_seconds=1,
                rate_limit_jitter_seconds=0,
            )
        )
    ).value == "ok"
    assert groq.calls == 2
    assert delays == [2]


@pytest.mark.asyncio
async def test_long_retry_after_falls_back_without_sleep(monkeypatch):
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.llm.client.asyncio.sleep", record_sleep)
    groq = StubProvider(
        "groq",
        [ProviderError("rate_limited", status_code=429, retry_after=11)],
    )
    gemini = StubProvider("gemini", ['{"value":"gemini"}'])
    client = LLMClient(
        [groq, gemini], provider_retry_count=1,
        rate_limit_fallback_threshold_seconds=10,
    )
    assert (await generate(client)).value == "gemini"
    assert delays == []
    assert groq.calls == 1


@pytest.mark.asyncio
async def test_cerebras_queue_exceeded_retries_once_then_succeeds(monkeypatch):
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.llm.client.asyncio.sleep", record_sleep)
    cerebras = StubProvider(
        "cerebras",
        [ProviderError("queue_exceeded", recoverable=True), '{"value":"ok"}'],
    )
    client = LLMClient(
        [cerebras],
        cerebras_provider_retry_count=1,
        cerebras_initial_backoff_seconds=2,
        cerebras_max_backoff_seconds=10,
        rate_limit_jitter_seconds=0,
    )
    assert (await generate(client)).value == "ok"
    assert cerebras.calls == 2
    assert delays == [2]


@pytest.mark.asyncio
async def test_cerebras_request_quota_immediately_falls_back(monkeypatch):
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.llm.client.asyncio.sleep", record_sleep)
    cerebras = StubProvider("cerebras", [ProviderError("quota_exceeded")])
    openai = StubProvider("openai", ['{"value":"openai"}'])
    client = LLMClient([cerebras, openai], cerebras_provider_retry_count=1)
    assert (await generate(client)).value == "openai"
    assert cerebras.calls == 1
    assert delays == []


@pytest.mark.asyncio
async def test_cerebras_concurrency_is_limited_to_one():
    class ConcurrentProvider(LLMProvider):
        name = "cerebras"
        model = "test-model"

        def __init__(self):
            self.active = 0
            self.max_active = 0

        async def generate(self, **kwargs):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            await asyncio.sleep(0.01)
            self.active -= 1
            return ProviderResponse('{"value":"ok"}', self.name, self.model)

    provider = ConcurrentProvider()
    client = LLMClient(
        [provider],
        provider_concurrency={"cerebras": 1},
        provider_min_request_interval={"cerebras": 0},
    )
    await asyncio.gather(generate(client), generate(client))
    assert provider.max_active == 1


@pytest.mark.asyncio
async def test_cerebras_sdk_retries_are_disabled(monkeypatch):
    constructor_options = {}

    class Completions:
        async def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"value":"ok"}'))],
                usage=None,
            )

    class FakeClient:
        def __init__(self, **kwargs):
            constructor_options.update(kwargs)
            self.chat = SimpleNamespace(completions=Completions())

    monkeypatch.setattr("cerebras.cloud.sdk.AsyncCerebras", FakeClient)
    provider = CerebrasProvider("test-key", "test-model")
    response = await provider.generate(
        system_prompt="system",
        user_prompt="user",
        response_model=Output,
        timeout=5,
        temperature=0,
        max_output_tokens=20,
    )
    assert response.content == '{"value":"ok"}'
    assert constructor_options["max_retries"] == 0


@pytest.mark.asyncio
async def test_timeout_is_not_retried_and_falls_back_immediately():
    groq = StubProvider("groq", [ProviderError("timeout"), '{"value":"unused"}'])
    gemini = StubProvider("gemini", ['{"value":"gemini"}'])
    assert (await generate(LLMClient([groq, gemini], provider_retry_count=1))).value == "gemini"
    assert groq.calls == 1


@pytest.mark.asyncio
async def test_invalid_json_gets_one_successful_repair():
    groq = StubProvider("groq", ["not json", '{"value":"repaired"}'])
    assert (await generate(LLMClient([groq]))).value == "repaired"
    assert groq.calls == 2


@pytest.mark.asyncio
async def test_failed_repair_moves_to_next_provider():
    groq = StubProvider("groq", ["not json", "still not json"])
    gemini = StubProvider("gemini", ['{"value":"gemini"}'])
    assert (await generate(LLMClient([groq, gemini]))).value == "gemini"
    assert groq.calls == 2


@pytest.mark.asyncio
async def test_all_providers_fail_without_static_output():
    providers = [StubProvider(name, [ProviderError("missing_configuration")]) for name in ("groq", "gemini", "openai")]
    with pytest.raises(AllLLMProvidersFailed) as caught:
        await generate(LLMClient(providers))
    assert caught.value.error_code == "ALL_LLM_PROVIDERS_FAILED"
    assert caught.value.details == {"providers_attempted": ["groq", "gemini", "openai"]}


@pytest.mark.asyncio
async def test_api_keys_are_not_written_to_logs(caplog):
    secret = "secret-key-must-not-appear"
    groq = StubProvider("groq", [ProviderError("authentication")], model="safe-model")
    with pytest.raises(AllLLMProvidersFailed):
        await generate(LLMClient([groq]))
    assert secret not in caplog.text


def test_pydantic_schema_still_rejects_malformed_output():
    with pytest.raises(Exception):
        Output.model_validate({})


@pytest.mark.parametrize(
    ("error", "category", "recoverable"),
    [
        (type("AuthenticationError", (Exception,), {"status_code": 401})("invalid"), "authentication", False),
        (Exception("RESOURCE_EXHAUSTED: quota exceeded"), "quota_exceeded", False),
        (TimeoutError("request timed out"), "timeout", False),
    ],
)
def test_provider_sdk_errors_are_safely_classified(error, category, recoverable):
    classified = _classify_error(error)
    assert (classified.category, classified.recoverable) == (category, recoverable)


def test_rate_limit_status_message_and_retry_after_are_preserved_safely():
    class Response:
        headers = {"retry-after": "3"}

    class RateLimitError(Exception):
        status_code = 429
        response = Response()

    classified = _classify_error(RateLimitError("rate limit for api_key=gsk_secret"))
    assert classified.status_code == 429
    assert classified.retry_after == 3
    assert "gsk_secret" not in classified.provider_message


def test_groq_message_retry_delay_is_used_when_header_is_missing():
    class RateLimitError(Exception):
        status_code = 429

    classified = _classify_error(
        RateLimitError("Rate limit reached. Please try again in 48.7275s.")
    )
    assert classified.retry_after == 48.7275


@pytest.mark.parametrize(
    ("message", "category", "recoverable"),
    [
        ("code=queue_exceeded model queue is full", "queue_exceeded", True),
        ("code=request_quota_exceeded RPM exceeded", "quota_exceeded", False),
    ],
)
def test_cerebras_429_codes_are_classified(message, category, recoverable):
    error = type("RateLimitError", (Exception,), {"status_code": 429})(message)
    classified = _classify_error(error)
    assert (classified.category, classified.recoverable) == (category, recoverable)
