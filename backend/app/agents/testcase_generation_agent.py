from app.agents.base_agent import BaseAgent,ExecutionContext
from app.schemas.scenario_schema import ScenarioBatch
from app.schemas.testcase_schema import TestCaseBatch,TestCase,TestStep
class TestCaseGenerationAgent(BaseAgent[TestCaseBatch]):
    output_model=TestCaseBatch
    async def run(self,input_data,execution_context:ExecutionContext)->TestCaseBatch:
        batch=ScenarioBatch.model_validate(input_data)
        return TestCaseBatch(test_cases=[TestCase(scenario_id=s.scenario_id,project_id=s.project_id,title=f"Test: {s.title}",description=s.description,test_case_type=s.scenario_type.value,priority=s.priority,preconditions=s.preconditions,test_data={"requirements":s.test_data_requirements},steps=[TestStep(step_number=1,action="Prepare the specified test data",expected_result="Test data is accepted and ready"),TestStep(step_number=2,action=f"Execute {s.title}",expected_result=s.expected_business_outcome)],postconditions=["Record the observed result"],requirement_ids=s.requirement_ids,acceptance_criteria_ids=s.acceptance_criteria_ids,automation_candidate=s.scenario_type.value in {"positive","negative","boundary","data_validation"},generation_metadata={"source_scenario_id":str(s.scenario_id)}) for s in batch.scenarios])
