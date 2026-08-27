import json
import pytest
from pydantic import BaseModel, Field

from app.core.exceptions import AllLLMProvidersFailed
from app.llm.client import LLMClient, build_llm_client
from app.llm.providers import LLMProvider, OllamaProvider, ProviderError, ProviderResponse


class SimpleResponse(BaseModel):
    value: str = Field(..., min_length=1)
    status: str = Field("ok")


class StubProvider(LLMProvider):
    def __init__(self, name: str, responses: list[object], model: str = "stub-v1"):
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
async def test_valid_ollama_result_groq_not_called():
    ollama = StubProvider("ollama", ['{"value": "from_ollama", "status": "ok"}'])
    groq = StubProvider("groq", ['{"value": "from_groq", "status": "ok"}'])

    client = LLMClient([ollama, groq])
    result = await client.generate_structured_output(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SimpleResponse,
    )

    assert result.value == "from_ollama"
    assert ollama.calls == 1
    assert groq.calls == 0, "Groq must NOT be called when Ollama produces a valid result"


@pytest.mark.asyncio
async def test_invalid_ollama_schema_triggers_groq_fallback():
    # Ollama returns malformed JSON or missing required fields
    ollama = StubProvider("ollama", ['{"unexpected_field": 123}', '{"unexpected_field": 456}'])
    groq = StubProvider("groq", ['{"value": "from_groq_fallback", "status": "ok"}'])

    client = LLMClient([ollama, groq], provider_retry_count=0)
    result = await client.generate_structured_output(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SimpleResponse,
    )

    assert result.value == "from_groq_fallback"
    assert ollama.calls >= 1
    assert groq.calls == 1


@pytest.mark.asyncio
async def test_ollama_unavailable_triggers_groq_fallback():
    ollama = StubProvider("ollama", [ProviderError("temporary_provider_error")])
    groq = StubProvider("groq", ['{"value": "recovered_by_groq", "status": "ok"}'])

    client = LLMClient([ollama, groq], provider_retry_count=0)
    result = await client.generate_structured_output(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SimpleResponse,
    )

    assert result.value == "recovered_by_groq"
    assert ollama.calls == 1
    assert groq.calls == 1


@pytest.mark.asyncio
async def test_both_providers_fail_raises_clear_error():
    ollama = StubProvider("ollama", [ProviderError("temporary_provider_error")])
    groq = StubProvider("groq", [ProviderError("temporary_provider_error")])

    client = LLMClient([ollama, groq], provider_retry_count=0)
    with pytest.raises(AllLLMProvidersFailed) as exc_info:
        await client.generate_structured_output(
            system_prompt="Test system",
            user_prompt="Test user",
            response_model=SimpleResponse,
        )

    attempted = exc_info.value.details.get("providers_attempted", [])
    assert "ollama" in attempted
    assert "groq" in attempted
    assert ollama.calls == 1
    assert groq.calls == 1


@pytest.mark.asyncio
async def test_groq_result_is_also_deterministically_validated():
    ollama = StubProvider("ollama", [ProviderError("temporary_provider_error")])
    # Groq returns schema-invalid response on both initial and mandatory-repair attempts
    groq = StubProvider("groq", ['{"invalid_schema": true}', '{"invalid_schema": true}'])

    client = LLMClient([ollama, groq], provider_retry_count=0)
    with pytest.raises(AllLLMProvidersFailed) as exc_info:
        await client.generate_structured_output(
            system_prompt="Test system",
            user_prompt="Test user",
            response_model=SimpleResponse,
        )

    attempted = exc_info.value.details.get("providers_attempted", [])
    assert "groq" in attempted
    assert exc_info.value.error_code == "ALL_LLM_PROVIDERS_FAILED"


def test_build_llm_client_hybrid_mode(monkeypatch):
    monkeypatch.setattr("app.llm.client.settings.llm_provider_mode", "hybrid")
    monkeypatch.setattr("app.llm.client.settings.ollama_base_url", "http://localhost:11434")
    monkeypatch.setattr("app.llm.client.settings.ollama_model", "llama3.1:8b")
    monkeypatch.setattr("app.llm.client.settings.groq_api_key", "gsk-key1")
    monkeypatch.setattr("app.llm.client.settings.groq_fallback_api_key", "gsk-key2")
    monkeypatch.setattr("app.llm.client.settings.app_mock_mode", False)

    client = build_llm_client("generation", mock_mode=False)
    provider_names = [p.name for p in client.providers]
    assert provider_names == ["ollama", "groq", "groq_fallback"]
    assert client.providers[0].model == "llama3.1:8b"


def test_build_llm_client_ollama_only_mode(monkeypatch):
    monkeypatch.setattr("app.llm.client.settings.llm_provider_mode", "ollama")
    monkeypatch.setattr("app.llm.client.settings.ollama_model", "llama3.1:8b")
    monkeypatch.setattr("app.llm.client.settings.app_mock_mode", False)

    client = build_llm_client("generation", mock_mode=False)
    provider_names = [p.name for p in client.providers]
    assert provider_names == ["ollama"]


def test_build_llm_client_groq_only_mode(monkeypatch):
    monkeypatch.setattr("app.llm.client.settings.llm_provider_mode", "groq")
    monkeypatch.setattr("app.llm.client.settings.groq_api_key", "gsk-test")
    monkeypatch.setattr("app.llm.client.settings.groq_fallback_api_key", "")
    monkeypatch.setattr("app.llm.client.settings.app_mock_mode", False)

    client = build_llm_client("generation", mock_mode=False)
    provider_names = [p.name for p in client.providers]
    assert provider_names == ["groq"]


@pytest.mark.asyncio
async def test_ollama_provider_direct_mock_client():
    class MockHttpResponse:
        status_code = 200

        def json(self):
            return {
                "message": {"content": json.dumps({"value": "ollama_success", "status": "ok"})},
                "prompt_eval_count": 15,
                "eval_count": 25,
            }

    class MockHttpClient:
        async def post(self, url, json, timeout):
            assert url == "http://localhost:11434/api/chat"
            assert json["model"] == "llama3.1:8b"
            assert "format" in json
            return MockHttpResponse()

    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        client=MockHttpClient(),
    )

    response = await provider.generate(
        system_prompt="Test system",
        user_prompt="Test user",
        response_model=SimpleResponse,
        temperature=0.2,
        max_output_tokens=1000,
        timeout=30.0,
    )

    assert response.provider == "ollama"
    assert response.model == "llama3.1:8b"
    assert response.token_usage == {"input_tokens": 15, "output_tokens": 25}
    parsed = SimpleResponse.model_validate_json(response.content)
    assert parsed.value == "ollama_success"
