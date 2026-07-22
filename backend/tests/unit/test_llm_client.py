import asyncio
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field, ValidationError

from app.core.exceptions import AllLLMProvidersFailed
from app.llm.client import LLMClient
from app.llm.parser import parse_json
from app.llm.providers import (
    CerebrasProvider,
    GeminiProvider,
    LLMProvider,
    ProviderError,
    ProviderResponse,
    _classify_error,
    _gemini_schema,
)


@pytest.fixture(autouse=True)
def clear_llm_client_global_state(monkeypatch):
    monkeypatch.setattr("app.llm.client._provider_unavailable_until", {})
    monkeypatch.setattr("app.llm.client._provider_last_request", {})


class Output(BaseModel):
    value: str


class RequiredTestCase(BaseModel):
    title: str
    steps: list[str] = Field(min_length=1)


class RequiredTestCaseOutput(BaseModel):
    test_cases: list[RequiredTestCase]


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
async def test_empty_primary_response_invokes_fallback_without_parsing():
    primary = StubProvider("cerebras", [""])
    fallback = StubProvider("cerebras_fallback", ['{"value":"fallback"}'])
    result = await generate(LLMClient([primary, fallback], cerebras_provider_retry_count=0))
    assert result.value == "fallback"
    assert primary.calls == 1
    assert fallback.calls == 1


@pytest.mark.asyncio
async def test_missing_required_steps_triggers_one_targeted_regeneration(caplog):
    provider = StubProvider(
        "cerebras",
        [
            '{"test_cases":[{"title":"Login"}]}',
            '{"test_cases":[{"title":"Login","steps":["Open login page"]}]}',
        ],
    )
    result = await LLMClient(
        [provider], cerebras_provider_retry_count=0
    ).generate_structured_output(
        system_prompt="system",
        user_prompt="generate test cases",
        response_model=RequiredTestCaseOutput,
        request_id="missing-steps",
    )
    assert result.test_cases[0].steps == ["Open login page"]
    assert provider.calls == 2
    assert "failure_type=missing_required_fields" in caplog.text
    assert "test_cases.0.steps" in caplog.text


@pytest.mark.asyncio
async def test_string_steps_trigger_mandatory_object_regeneration():
    class ObjectStep(BaseModel):
        step_number: int
        action: str
        expected_result: str

    class ObjectStepCase(BaseModel):
        title: str
        steps: list[ObjectStep] = Field(min_length=1)

    class ObjectStepBatch(BaseModel):
        test_cases: list[ObjectStepCase]

    provider = StubProvider(
        "cerebras",
        [
            '{"test_cases":[{"title":"Login","steps":["Open login"]}]}',
            '{"test_cases":[{"title":"Login","steps":[{"step_number":1,"action":"Open login","expected_result":"Login page opens"}]}]}',
        ],
    )
    result = await LLMClient(
        [provider], cerebras_provider_retry_count=0
    ).generate_structured_output(
        system_prompt="system",
        user_prompt="generate test cases",
        response_model=ObjectStepBatch,
        request_id="string-steps",
    )
    assert result.test_cases[0].steps[0].step_number == 1
    assert provider.calls == 2


@pytest.mark.asyncio
async def test_failed_regeneration_keeps_only_schema_valid_batch_items(caplog):
    provider = StubProvider(
        "cerebras",
        [
            '{"test_cases":[{"title":"Login","steps":["Open"]},{"title":"Logout"}]}',
            '{"test_cases":[{"title":"Login","steps":["Open"]},{"title":"Logout"}]}',
        ],
    )
    result = await LLMClient(
        [provider], cerebras_provider_retry_count=0
    ).generate_structured_output(
        system_prompt="system",
        user_prompt="generate test cases",
        response_model=RequiredTestCaseOutput,
        request_id="partially-valid-batch",
    )
    assert [item.title for item in result.test_cases] == ["Login"]
    assert provider.calls == 2
    assert "LLM malformed batch items removed" in caplog.text


def test_gemini_provider_supports_distinct_provider_names():
    primary = GeminiProvider(
        "key-one",
        "gemini-3.5-flash",
        provider_name="gemini_primary",
        thinking_level="low",
        min_output_tokens=4096,
    )
    fallback = GeminiProvider(
        "key-two",
        "gemini-3.5-flash",
        provider_name="gemini_fallback",
        thinking_level="low",
        min_output_tokens=4096,
    )
    assert primary.name == "gemini_primary"
    assert fallback.name == "gemini_fallback"
    assert primary.thinking_level == "low"
    assert primary.min_output_tokens == 4096


def test_cerebras_provider_supports_distinct_fallback_name():
    primary = CerebrasProvider("key-one", "gpt-oss-120b")
    fallback = CerebrasProvider(
        "key-two", "gpt-oss-120b", provider_name="cerebras_fallback"
    )
    assert primary.name == "cerebras"
    assert fallback.name == "cerebras_fallback"


@pytest.mark.asyncio
async def test_gemini_uses_parsed_schema_and_reserves_output_tokens():
    captured = {}

    class Models:
        async def generate_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                parsed={"value": "structured"},
                text="not used",
                usage_metadata=None,
            )

    client = SimpleNamespace(aio=SimpleNamespace(models=Models()))
    provider = GeminiProvider(
        "key",
        "gemini-3.5-flash",
        client=client,
        provider_name="gemini_primary",
        thinking_level="low",
        min_output_tokens=4096,
    )
    response = await provider.generate(
        system_prompt="system",
        user_prompt="user",
        response_model=Output,
        timeout=30,
        temperature=0.2,
        max_output_tokens=1200,
    )
    assert response.content == '{"value":"structured"}'
    assert captured["config"].response_schema is None
    assert captured["config"].response_json_schema == _gemini_schema(Output)
    assert captured["config"].max_output_tokens == 4096
    assert captured["config"].thinking_config.thinking_level.value == "LOW"


def test_gemini_schema_removes_unsupported_additional_properties():
    from app.schemas.scenario_schema import ScenarioBatch
    from app.schemas.testcase_schema import TestCaseBatch
    from app.schemas.validation_schema import ValidationResult

    def contains_key(value, target):
        if isinstance(value, dict):
            return target in value or any(
                contains_key(item, target) for item in value.values()
            )
        if isinstance(value, list):
            return any(contains_key(item, target) for item in value)
        return False

    for model in (ScenarioBatch, TestCaseBatch, ValidationResult):
        schema = _gemini_schema(model)
        assert not contains_key(schema, "additionalProperties")


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
async def test_temporary_provider_error_is_retried_once(monkeypatch):
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.llm.client.asyncio.sleep", record_sleep)
    gemini = StubProvider(
        "gemini_primary",
        [ProviderError("temporary_provider_error", status_code=503), '{"value":"ok"}'],
    )
    client = LLMClient(
        [gemini],
        provider_retry_count=1,
        rate_limit_backoff_seconds=1,
        rate_limit_jitter_seconds=0,
    )
    assert (await generate(client)).value == "ok"
    assert delays == [1]


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
async def test_only_available_provider_waits_even_above_fallback_threshold(monkeypatch):
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.llm.client.asyncio.sleep", record_sleep)
    groq = StubProvider(
        "groq",
        [
            ProviderError("rate_limited", status_code=429, retry_after=4),
            '{"value":"groq"}',
        ],
    )
    client = LLMClient(
        [groq],
        provider_retry_count=1,
        rate_limit_fallback_threshold_seconds=3,
        rate_limit_jitter_seconds=0,
    )
    assert (await generate(client)).value == "groq"
    assert delays == [4]


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
async def test_cerebras_fallback_uses_independent_rate_limit_lane(monkeypatch):
    delays = []

    async def record_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("app.llm.client.asyncio.sleep", record_sleep)
    monkeypatch.setattr("app.llm.client.time.monotonic", lambda: 100.0)
    monkeypatch.setattr("app.llm.client._provider_last_request", {})
    primary = StubProvider("cerebras", [ProviderError("quota_exceeded")])
    fallback = StubProvider("cerebras_fallback", ['{"value":"fallback"}'])
    client = LLMClient(
        [primary, fallback],
        cerebras_provider_retry_count=0,
        provider_min_request_interval={"cerebras": 65, "cerebras_fallback": 65},
    )

    assert (await generate(client)).value == "fallback"
    assert primary.calls == fallback.calls == 1
    assert delays == []


def test_generation_batches_reject_empty_outputs():
    from app.schemas.scenario_schema import ScenarioBatch
    from app.schemas.testcase_schema import TestCaseBatch

    with pytest.raises(ValidationError):
        ScenarioBatch(scenarios=[])
    with pytest.raises(ValidationError):
        TestCaseBatch(test_cases=[])


@pytest.mark.asyncio
async def test_quota_failed_provider_is_skipped_on_next_generation():
    cerebras = StubProvider("cerebras", [ProviderError("quota_exceeded")])
    groq = StubProvider("groq", ['{"value":"first"}', '{"value":"second"}'])
    client = LLMClient([cerebras, groq])
    assert (await generate(client)).value == "first"
    assert (await generate(client)).value == "second"
    assert cerebras.calls == 1


@pytest.mark.asyncio
async def test_provider_quota_cooldown_is_shared_across_clients(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("app.llm.client.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("app.llm.client._provider_unavailable_until", {})
    first_cerebras = StubProvider("cerebras", [ProviderError("quota_exceeded")])
    first_groq = StubProvider("groq", ['{"value":"first"}'])
    first = LLMClient(
        [first_cerebras, first_groq],
        provider_cooldown_seconds={"cerebras": 60},
    )
    assert (await generate(first)).value == "first"

    second_cerebras = StubProvider("cerebras", ['{"value":"unused"}'])
    second_groq = StubProvider("groq", ['{"value":"second"}'])
    second = LLMClient(
        [second_cerebras, second_groq],
        provider_cooldown_seconds={"cerebras": 60},
    )
    assert (await generate(second)).value == "second"
    assert second_cerebras.calls == 0


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
async def test_optional_remote_repair_can_be_enabled(monkeypatch):
    monkeypatch.setattr("app.llm.client.settings.llm_structured_output_repair_enabled", True)
    groq = StubProvider("groq", ["not json", '{"value":"repaired"}'])
    assert (await generate(LLMClient([groq]))).value == "repaired"
    assert groq.calls == 2


@pytest.mark.asyncio
async def test_failed_repair_moves_to_next_provider():
    groq = StubProvider("groq", ["not json", "still not json"])
    gemini = StubProvider("gemini", ['{"value":"gemini"}'])
    assert (await generate(LLMClient([groq, gemini]))).value == "gemini"
    assert groq.calls == 1


@pytest.mark.asyncio
async def test_all_providers_fail_without_static_output():
    providers = [StubProvider(name, [ProviderError("missing_configuration")]) for name in ("groq", "gemini", "openai")]
    with pytest.raises(AllLLMProvidersFailed) as caught:
        await generate(LLMClient(providers))
    assert caught.value.error_code == "ALL_LLM_PROVIDERS_FAILED"
    assert caught.value.details["providers_attempted"] == ["groq", "gemini", "openai"]
    assert set(caught.value.details["failures"]) == {"groq", "gemini", "openai"}


def test_capacity_failure_has_user_friendly_retry_message():
    error = AllLLMProvidersFailed(
        ["gemini_primary", "gemini_fallback"],
        {
            "gemini_primary": {
                "category": "rate_limited",
                "status_code": 429,
                "retry_after": 59.6,
            },
            "gemini_fallback": {
                "category": "temporary_provider_error",
                "status_code": 503,
                "retry_after": None,
            },
        },
    )
    assert "temporarily unavailable" in error.message
    assert "60 seconds" in error.message


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
    ("content", "expected"),
    [
        ('Here is the result: {"value":"ok"}', {"value": "ok"}),
        ('```json\n{"value":"ok"}\n```\nDone.', {"value": "ok"}),
        ('Reasoning {"value":"brace } inside string"} trailing', {"value": "brace } inside string"}),
        ('{"value":"locally repaired"', {"value": "locally repaired"}),
    ],
)
def test_parser_extracts_balanced_json_from_wrapped_output(content, expected):
    assert parse_json(content) == expected


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


def test_gemini_retry_message_is_classified_as_recoverable_rate_limit():
    error = type("ResourceExhausted", (Exception,), {"status_code": 429})(
        "Quota exceeded. Please retry in 5.824261529s."
    )
    classified = _classify_error(error)
    assert classified.category == "rate_limited"
    assert classified.retry_after == 5.824261529


def test_groq_tpm_413_is_classified_as_rate_limit():
    error = type("RequestTooLargeError", (Exception,), {"status_code": 413})(
        "Request too large on tokens per minute (TPM): rate_limit_exceeded"
    )
    classified = _classify_error(error)
    assert classified.category == "rate_limited"


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
