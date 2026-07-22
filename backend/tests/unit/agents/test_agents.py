import uuid

import pytest

from app.agents.base_agent import ExecutionContext
from app.agents.context_preparation_agent import ContextPreparationAgent
from app.agents.scenario_generation_agent import ScenarioGenerationAgent
from app.agents.scenario_validation_agent import ScenarioValidationAgent
from app.agents.testcase_generation_agent import TestCaseGenerationAgent as CaseGenerationAgent
from app.agents.testcase_validation_agent import TestCaseValidationAgent as CaseValidationAgent
from app.core.config import settings
from app.llm.client import build_llm_client
from app.schemas.scenario_schema import Scenario, ScenarioBatch
from app.schemas.testcase_schema import TestCase as CaseModel
from app.schemas.testcase_schema import TestCaseBatch as CaseBatch
from app.schemas.testcase_schema import TestStep as CaseStep


class StubStructuredClient:
    def __init__(self, project_id):
        self.project_id = project_id
        self.calls = []

    async def generate_structured_output(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["response_model"] is ScenarioBatch:
            return ScenarioBatch(scenarios=[
                Scenario(
                    project_id=self.project_id,
                    title="Transfer funds within the available balance",
                    description="Verify an authenticated user can transfer available funds",
                    scenario_type="positive",
                    priority="high",
                    preconditions=["The user is authenticated"],
                    test_data_requirements=["Source account with sufficient balance"],
                    expected_business_outcome="The transfer is completed exactly once",
                    requirement_ids=["REQ-1"], user_story_ids=["US1"],
                    acceptance_criteria_ids=["AC1"], source_references=["US1"],
                )
            ])
        return CaseBatch(test_cases=[
            CaseModel(
                scenario_id=self.scenario_id,
                project_id=self.project_id,
                title="Complete an available-balance transfer",
                description="Verify the validated transfer scenario",
                test_case_type="positive", priority="high",
                preconditions=["The user is authenticated"],
                test_data={"amount": "100.00"},
                steps=[CaseStep(step_number=1, action="Submit a transfer of 100.00", expected_result="The transfer is accepted once")],
                postconditions=["The destination balance increases by 100.00"],
                requirement_ids=["REQ-1"], acceptance_criteria_ids=["AC1"], automation_candidate=True,
            )
        ])


@pytest.mark.asyncio
async def test_plain_text_input_gets_ids_and_generated_traceability():
    project_id = uuid.uuid4()
    ctx = ExecutionContext(request_id="plain", workflow_id="plain")
    prepared = await ContextPreparationAgent().execute({
        "project_id": project_id,
        "source_type": "manual",
        "input_payload": {
            "user_stories": ["User can log in."],
            "functional_requirements": ["Support email login."],
            "acceptance_criteria": ["Valid credentials allow login."],
            "features": ["Login"],
        },
    }, ctx)
    assert prepared.user_stories[0]["id"] == "US-1"
    assert prepared.functional_requirements[0]["id"] == "REQ-1"
    assert prepared.acceptance_criteria[0]["id"] == "AC-1"

    client = StubStructuredClient(project_id)
    scenarios = await ScenarioGenerationAgent(client).execute(
        prepared.model_dump(), ctx
    )
    scenario = scenarios.scenarios[0]
    assert scenario.user_story_ids == ["US1"] or scenario.user_story_ids == ["US-1"]
    assert scenario.requirement_ids
    assert scenario.acceptance_criteria_ids


@pytest.mark.asyncio
async def test_context_and_validation_logic_remain_unchanged():
    project_id = uuid.uuid4()
    ctx = ExecutionContext(request_id="r", workflow_id="w")
    prepared = await ContextPreparationAgent().execute({
        "project_id": project_id,
        "source_type": "manual",
        "input_payload": {
            "functional_requirements": [{"id": "REQ-1", "text": "Transfer funds"}],
            "user_stories": [{"id": "US1", "title": "Transfer funds"}, {"id": "US1", "title": "Transfer funds"}],
            "acceptance_criteria": [{"id": "AC1", "text": "Transfer succeeds"}],
        },
    }, ctx)
    assert len(prepared.user_stories) == 1
    client = StubStructuredClient(project_id)
    scenarios = await ScenarioGenerationAgent(client).execute(prepared.model_dump(), ctx)
    assert client.calls and client.calls[0]["response_model"] is ScenarioBatch
    result = await ScenarioValidationAgent().execute({"context": prepared.model_dump(), "scenarios": scenarios.model_dump()}, ctx)
    assert result.score_breakdown["traceability"] == 1.0
    assert result.score_breakdown["completeness"] < 1.0
    assert any(issue.issue_code == "LOW_COMPLETENESS" for issue in result.issues)


@pytest.mark.asyncio
async def test_testcase_generation_agent_uses_structured_llm_client():
    project_id, scenario_id = uuid.uuid4(), uuid.uuid4()
    client = StubStructuredClient(project_id)
    client.scenario_id = scenario_id
    scenario = Scenario(
        scenario_id=scenario_id, project_id=project_id, title="Transfer funds",
        description="Verify transfer", scenario_type="positive", expected_business_outcome="Transfer succeeds",
    )
    result = await CaseGenerationAgent(client).execute(
        {"scenarios": [scenario.model_dump(mode="json")]},
        ExecutionContext(request_id="r", workflow_id="w"),
    )
    assert result.test_cases[0].scenario_id == scenario_id
    assert client.calls[0]["response_model"] is CaseBatch


@pytest.mark.asyncio
async def test_missing_acceptance_criteria_reduces_confidence():
    project_id = uuid.uuid4()
    scenario = Scenario(
        project_id=project_id, title="Login", description="Verify that a registered customer can log in successfully",
        scenario_type="positive", priority="high", preconditions=["A registered customer exists"],
        test_data_requirements=["Valid credentials"], expected_business_outcome="The customer account page is displayed",
        requirement_ids=["REQ-1"], user_story_ids=["US-1"],
    )
    context = await ContextPreparationAgent().execute({
        "project_id": project_id,
        "input_payload": {"user_stories": ["As a customer, I want to log in"], "functional_requirements": ["Support login"]},
    }, ExecutionContext(request_id="missing-ac", workflow_id="missing-ac"))
    result = await ScenarioValidationAgent().execute(
        {"context": context.model_dump(), "scenarios": {"scenarios": [scenario.model_dump(mode="json")]}},
        ExecutionContext(request_id="missing-ac", workflow_id="missing-ac"),
    )
    assert result.score_breakdown["acceptance_criteria_coverage"] == 0.0
    assert result.confidence_score < 0.8
    assert any(issue.issue_code == "LOW_ACCEPTANCE_CRITERIA_COVERAGE" for issue in result.issues)


@pytest.mark.asyncio
async def test_mock_mode_runs_generation_and_validation_without_live_provider(monkeypatch):
    monkeypatch.setattr(settings, "app_mock_mode", True)
    project_id = uuid.uuid4()
    ctx = ExecutionContext(request_id="mock", workflow_id="mock")
    assert [provider.name for provider in build_llm_client().providers] == ["mock"]
    prepared = await ContextPreparationAgent().execute({
        "project_id": project_id,
        "source_type": "manual",
        "input_payload": {
            "user_stories": ["As a user I can log in."],
            "functional_requirements": ["Support email login."],
            "acceptance_criteria": ["Valid credentials allow login."],
            "features": ["Login"],
        },
    }, ctx)
    scenarios = await ScenarioGenerationAgent().execute(prepared.model_dump(), ctx)
    scenario_validation = await ScenarioValidationAgent().execute(
        {"context": prepared.model_dump(), "scenarios": scenarios.model_dump()}, ctx
    )
    assert scenario_validation.confidence_score >= 0.95
    test_cases = await CaseGenerationAgent().execute({
        "scenarios": scenarios.model_dump(mode="json")["scenarios"],
        "context": prepared.model_dump(mode="json"),
    }, ctx)
    testcase_validation = await CaseValidationAgent().execute({
        "scenarios": scenarios.model_dump(mode="json"),
        "test_cases": test_cases.model_dump(mode="json"),
    }, ctx)
    assert testcase_validation.confidence_score >= 0.95
    assert all(case.steps for case in test_cases.test_cases)
