import json

from app.agents.base_agent import BaseAgent, ExecutionContext
from app.llm.client import build_llm_client
from app.llm.prompt_loader import PromptLoader
from app.schemas.context_schema import StructuredContext
from app.schemas.scenario_schema import ScenarioBatch
from app.schemas.testcase_schema import TestCaseBatch


class TestCaseGenerationAgent(BaseAgent[TestCaseBatch]):
    output_model = TestCaseBatch

    def __init__(self, llm_client=None, prompt_loader=None):
        super().__init__(llm_client=llm_client)
        self.llm_client = llm_client or build_llm_client()
        self.prompt_loader = prompt_loader or PromptLoader()

    async def run(self, input_data, execution_context: ExecutionContext) -> TestCaseBatch:
        scenarios = ScenarioBatch.model_validate({"scenarios": input_data["scenarios"]})
        context = None
        if input_data.get("context"):
            context = StructuredContext.model_validate(input_data["context"])
        template = "testcase_regeneration.jinja2" if "validation" in input_data else "testcase_generation.jinja2"
        user_prompt = self.prompt_loader.render(
            template,
            scenarios=json.dumps(scenarios.model_dump(mode="json"), ensure_ascii=False),
            context=json.dumps(context.model_dump(mode="json") if context else {}, ensure_ascii=False),
            failed_item=json.dumps(input_data.get("existing_test_cases", []), ensure_ascii=False),
            scenario=json.dumps(scenarios.model_dump(mode="json"), ensure_ascii=False),
            feedback=json.dumps(input_data.get("validation", {}), ensure_ascii=False),
        )
        return await self.llm_client.generate_structured_output(
            system_prompt="You are a senior software test engineer. Return schema-compliant JSON only.",
            user_prompt=user_prompt,
            response_model=TestCaseBatch,
            request_id=execution_context.request_id,
        )
