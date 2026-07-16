from app.schemas.common import InputPayload
from app.core.config import Settings


def test_cors_origins_accept_comma_separated_values() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins="http://localhost:3000,http://localhost:5173",
    )

    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]


def test_cors_origins_accept_json_array() -> None:
    settings = Settings(
        _env_file=None,
        cors_origins='["http://localhost:3000","http://localhost:5173"]',
    )

    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]


def test_cors_origins_accept_single_value() -> None:
    settings = Settings(_env_file=None, cors_origins="http://localhost:3000")

    assert settings.cors_origins == ["http://localhost:3000"]


def test_input_payload_defaults_are_not_shared() -> None:
    first = InputPayload()
    second = InputPayload()

    first.user_stories.append({"id": "US-1"})

    assert second.user_stories == []
import uuid

from app.schemas.scenario_schema import Scenario
from app.schemas.testcase_schema import TestCase


def test_scenario_tolerates_display_id_and_normalizes_enums():
    project_id = uuid.uuid4()
    scenario = Scenario.model_validate({
        "scenario_id": "SCN-001",
        "project_id": str(project_id),
        "title": "Login succeeds",
        "description": "Valid credentials allow access",
        "scenario_type": "Data Validation",
        "priority": "HIGH",
        "expected_business_outcome": "User reaches the account",
        "confidence_score": 0.9,
    })
    assert isinstance(scenario.scenario_id, uuid.UUID)
    assert scenario.scenario_type.value == "data_validation"
    assert scenario.priority.value == "high"


def test_scenario_accepts_common_llm_aliases():
    scenario = Scenario.model_validate({
        "scenario_name": "Successful login",
        "scenario_description": "Verify valid credentials",
        "expected_result": "The account dashboard opens",
        "type": "positive",
        "project_id": str(uuid.uuid4()),
    })
    assert scenario.title == "Successful login"
    assert scenario.expected_business_outcome == "The account dashboard opens"


def test_testcase_replaces_display_id_and_renumbers_steps():
    test_case = TestCase.model_validate({
        "test_case_id": "TC-001",
        "scenario_id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "title": "Submit valid credentials",
        "description": "Verify successful login",
        "test_case_type": "functional",
        "priority": "HIGH",
        "steps": [
            {"step_number": 0, "action": "Enter credentials", "expected_result": "Values appear"},
            {"step_number": 4, "action": "Submit", "expected_result": "Account opens"},
        ],
    })
    assert isinstance(test_case.test_case_id, uuid.UUID)
    assert [step.step_number for step in test_case.steps] == [1, 2]


def test_testcase_accepts_common_llm_aliases():
    test_case = TestCase.model_validate({
        "test_case_title": "Login with valid credentials",
        "test_case_description": "Verify successful authentication",
        "test_type": "functional",
        "scenario_id": str(uuid.uuid4()),
        "project_id": str(uuid.uuid4()),
        "test_steps": [
            {"step_number": 1, "action": "Submit credentials", "expected_result": "Login succeeds"},
        ],
    })
    assert test_case.title == "Login with valid credentials"
    assert test_case.test_case_type == "functional"
