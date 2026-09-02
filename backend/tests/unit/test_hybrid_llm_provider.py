import json
import pytest
from pydantic import BaseModel, Field

from app.core.exceptions import AllLLMProvidersFailed
from app.llm.client import LLMClient, build_llm_client
from app.llm.providers import GroqProvider, LLMProvider, MockLLMProvider, ProviderError, ProviderResponse


class SimpleResponse(BaseModel):
    value: str = Field(..., min_length=1)
    status: str = Field("ok")


class StubProvider(LLMProvider):
    def __init__(self, name: str, responses: list[object], model: str = "groq-test-model"):
        self.name = name
        self.model = model
        self.responses = list(responses)
        self.calls = 0

    async def generate(self, **kwargs) -> ProviderResponse:
        self.calls += 1
        if not self.responses:
            raise ProviderError("exhausted")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return ProviderResponse(str(item), self.name, self.model)


@pytest.mark.asyncio
async def test_groq_primary_success_does_not_call_fallbacks():
    primary = StubProvider("groq", ['{"value": "from_primary", "status": "ok"}'])
    fallback_1 = StubProvider("groq_fallback_1", ['{"value": "from_fallback_1", "status": "ok"}'])
    fallback_2 = StubProvider("groq_fallback_2", ['{"value": "from_fallback_2", "status": "ok"}'])

    client = LLMClient([primary, fallback_1, fallback_2], provider_retry_count=0)
    result = await client.generate_structured_output(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SimpleResponse,
    )

    assert result.value == "from_primary"
    assert primary.calls == 1
    assert fallback_1.calls == 0, "Fallback 1 must NOT be called when Primary succeeds"
    assert fallback_2.calls == 0, "Fallback 2 must NOT be called when Primary succeeds"


@pytest.mark.asyncio
async def test_groq_fallback_1_success_when_primary_fails():
    primary = StubProvider("groq", [ProviderError("temporary_provider_error")])
    fallback_1 = StubProvider("groq_fallback_1", ['{"value": "from_fallback_1", "status": "ok"}'])
    fallback_2 = StubProvider("groq_fallback_2", ['{"value": "from_fallback_2", "status": "ok"}'])

    client = LLMClient([primary, fallback_1, fallback_2], provider_retry_count=0)
    result = await client.generate_structured_output(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SimpleResponse,
    )

    assert result.value == "from_fallback_1"
    assert primary.calls == 1
    assert fallback_1.calls == 1
    assert fallback_2.calls == 0, "Fallback 2 must NOT be called when Fallback 1 succeeds"


@pytest.mark.asyncio
async def test_groq_fallback_2_success_when_primary_and_fallback_1_fail():
    primary = StubProvider("groq", [ProviderError("rate_limited", retry_after=0.01)])
    fallback_1 = StubProvider("groq_fallback_1", [ProviderError("temporary_provider_error")])
    fallback_2 = StubProvider("groq_fallback_2", ['{"value": "from_fallback_2", "status": "ok"}'])

    client = LLMClient([primary, fallback_1, fallback_2], provider_retry_count=0)
    result = await client.generate_structured_output(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SimpleResponse,
    )

    assert result.value == "from_fallback_2"
    assert primary.calls == 1
    assert fallback_1.calls == 1
    assert fallback_2.calls == 1


@pytest.mark.asyncio
async def test_all_three_groq_providers_fail_raises_clear_error():
    primary = StubProvider("groq", [ProviderError("temporary_provider_error")])
    fallback_1 = StubProvider("groq_fallback_1", [ProviderError("rate_limited", retry_after=0.01)])
    fallback_2 = StubProvider("groq_fallback_2", [ProviderError("timeout")])

    client = LLMClient([primary, fallback_1, fallback_2], provider_retry_count=0)
    with pytest.raises(AllLLMProvidersFailed) as exc_info:
        await client.generate_structured_output(
            system_prompt="Test system",
            user_prompt="Test user",
            response_model=SimpleResponse,
        )

    attempted = exc_info.value.details.get("providers_attempted", [])
    assert attempted == ["groq", "groq_fallback_1", "groq_fallback_2"]
    assert primary.calls == 1
    assert fallback_1.calls == 1
    assert fallback_2.calls == 1
    assert exc_info.value.error_code == "ALL_LLM_PROVIDERS_FAILED"


@pytest.mark.asyncio
async def test_groq_rate_limit_moves_to_next_provider():
    primary = StubProvider("groq", [ProviderError("rate_limited", status_code=429, retry_after=15.0)])
    fallback_1 = StubProvider("groq_fallback_1", ['{"value": "rate_limit_recovered", "status": "ok"}'])
    fallback_2 = StubProvider("groq_fallback_2", ['{"value": "unused", "status": "ok"}'])

    client = LLMClient([primary, fallback_1, fallback_2], provider_retry_count=0, rate_limit_fallback_threshold_seconds=5.0)
    result = await client.generate_structured_output(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SimpleResponse,
    )

    assert result.value == "rate_limit_recovered"
    assert primary.calls == 1
    assert fallback_1.calls == 1
    assert fallback_2.calls == 0


@pytest.mark.asyncio
async def test_groq_timeout_moves_to_next_provider():
    primary = StubProvider("groq", [ProviderError("timeout")])
    fallback_1 = StubProvider("groq_fallback_1", ['{"value": "timeout_recovered", "status": "ok"}'])
    fallback_2 = StubProvider("groq_fallback_2", ['{"value": "unused", "status": "ok"}'])

    client = LLMClient([primary, fallback_1, fallback_2], provider_retry_count=0)
    result = await client.generate_structured_output(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SimpleResponse,
    )

    assert result.value == "timeout_recovered"
    assert primary.calls == 1
    assert fallback_1.calls == 1
    assert fallback_2.calls == 0


@pytest.mark.asyncio
async def test_groq_connection_error_moves_to_next_provider():
    primary = StubProvider("groq", [ProviderError("temporary_provider_error", status_code=503)])
    fallback_1 = StubProvider("groq_fallback_1", ['{"value": "connection_recovered", "status": "ok"}'])
    fallback_2 = StubProvider("groq_fallback_2", ['{"value": "unused", "status": "ok"}'])

    client = LLMClient([primary, fallback_1, fallback_2], provider_retry_count=0)
    result = await client.generate_structured_output(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SimpleResponse,
    )

    assert result.value == "connection_recovered"
    assert primary.calls == 1
    assert fallback_1.calls == 1
    assert fallback_2.calls == 0


@pytest.mark.asyncio
async def test_no_repeated_calls_to_same_provider_in_fallback_chain():
    primary = StubProvider("groq", [ProviderError("temporary_provider_error")])
    fallback_1 = StubProvider("groq_fallback_1", [ProviderError("temporary_provider_error")])
    fallback_2 = StubProvider("groq_fallback_2", ['{"value": "end_of_chain", "status": "ok"}'])

    client = LLMClient([primary, fallback_1, fallback_2], provider_retry_count=0)
    result = await client.generate_structured_output(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SimpleResponse,
    )

    assert result.value == "end_of_chain"
    # Verify each provider in the chain was called exactly once
    assert primary.calls == 1
    assert fallback_1.calls == 1
    assert fallback_2.calls == 1


def test_build_llm_client_three_groq_providers(monkeypatch):
    monkeypatch.setattr("app.llm.client.settings.llm_provider_mode", "groq")
    monkeypatch.setattr("app.llm.client.settings.groq_api_key", "gsk-key1")
    monkeypatch.setattr("app.llm.client.settings.groq_fallback_api_key", "gsk-key2")
    monkeypatch.setattr("app.llm.client.settings.groq_fallback_2_api_key", "gsk-key3")
    monkeypatch.setattr("app.llm.client.settings.groq_model", "openai/gpt-oss-120b")
    monkeypatch.setattr("app.llm.client.settings.groq_fallback_model", "openai/gpt-oss-120b")
    monkeypatch.setattr("app.llm.client.settings.groq_fallback_2_model", "openai/gpt-oss-120b")
    monkeypatch.setattr("app.llm.client.settings.app_mock_mode", False)

    client = build_llm_client("generation", mock_mode=False)
    provider_names = [p.name for p in client.providers]
    assert provider_names == ["groq", "groq_fallback_1", "groq_fallback_2"]
    assert len(client.providers) == 3


def test_build_llm_client_mock_mode():
    client = build_llm_client("generation", mock_mode=True)
    assert len(client.providers) == 1
    assert isinstance(client.providers[0], MockLLMProvider)
