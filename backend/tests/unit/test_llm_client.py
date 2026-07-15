import pytest
from pydantic import BaseModel

from app.core.exceptions import AllLLMProvidersFailed
from app.llm.client import LLMClient
from app.llm.providers import LLMProvider, ProviderError, ProviderResponse, _classify_error


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
async def test_temporary_error_is_retried_once():
    groq = StubProvider("groq", [ProviderError("timeout", recoverable=True), '{"value":"ok"}'])
    assert (await generate(LLMClient([groq], provider_retry_count=1))).value == "ok"
    assert groq.calls == 2


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
        (TimeoutError("request timed out"), "timeout", True),
    ],
)
def test_provider_sdk_errors_are_safely_classified(error, category, recoverable):
    classified = _classify_error(error)
    assert (classified.category, classified.recoverable) == (category, recoverable)
