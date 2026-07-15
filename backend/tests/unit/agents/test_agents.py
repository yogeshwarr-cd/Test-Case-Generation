import uuid
import pytest
from app.agents.base_agent import ExecutionContext
from app.agents.context_preparation_agent import ContextPreparationAgent
from app.agents.scenario_generation_agent import ScenarioGenerationAgent
from app.agents.scenario_validation_agent import ScenarioValidationAgent

@pytest.mark.asyncio
async def test_context_normalizes_duplicates_and_scenarios_pass():
    project_id=uuid.uuid4(); ctx=ExecutionContext(request_id="r",workflow_id="w")
    prepared=await ContextPreparationAgent().execute({"project_id":project_id,"source_type":"manual","input_payload":{"user_stories":[{"id":"US1","title":"Transfer funds"},{"id":"US1","title":"Transfer funds"}],"acceptance_criteria":[{"id":"AC1","text":"Transfer succeeds"}]}},ctx)
    assert len(prepared.user_stories)==1
    scenarios=await ScenarioGenerationAgent().execute(prepared.model_dump(),ctx)
    assert {x.scenario_type.value for x in scenarios.scenarios}=={"positive","negative","boundary"}
    result=await ScenarioValidationAgent().execute({"context":prepared.model_dump(),"scenarios":scenarios.model_dump()},ctx)
    assert result.confidence_score>=.95
