import json

from app.agents.base_agent import BaseAgent, ExecutionContext
from app.llm.client import build_llm_client
from app.llm.context import batches, scoped_context
from app.core.config import settings
from app.llm.prompt_loader import PromptLoader
from app.schemas.context_schema import StructuredContext
from app.schemas.scenario_schema import ScenarioBatch
from app.schemas.testcase_schema import TestCaseBatch


class TestCaseGenerationAgent(BaseAgent[TestCaseBatch]):
    output_model = TestCaseBatch

    def __init__(self, llm_client=None, prompt_loader=None):
        super().__init__(llm_client=llm_client)
        self.llm_client = llm_client
        self.prompt_loader = prompt_loader or PromptLoader()

    async def run(self, input_data, execution_context: ExecutionContext) -> TestCaseBatch:
        scenarios = ScenarioBatch.model_validate({"scenarios": input_data["scenarios"]})
        context = None
        if input_data.get("context"):
            context = StructuredContext.model_validate(input_data["context"])
        template = "testcase_regeneration.jinja2" if "validation" in input_data else "testcase_generation.jinja2"
        task = "regeneration" if "validation" in input_data else "generation"
        client = self.llm_client or build_llm_client(task)
        context_dict = context.model_dump(mode="json") if context else {}
        scenario_items = scenarios.model_dump(mode="json")["scenarios"]
        generated = []
        for batch in batches(scenario_items, settings.llm_testcase_batch_size):
            compact_context = scoped_context(context_dict, batch) if context else {}
            existing = input_data.get("existing_test_cases", [])
            scenario_ids = {str(item["scenario_id"]) for item in batch}
            related_existing = [
                item for item in existing if str(item.get("scenario_id")) in scenario_ids
            ]
            scenario_batch = {"scenarios": batch}
            user_prompt = self.prompt_loader.render(
                template,
                scenarios=json.dumps(scenario_batch, ensure_ascii=False),
                context=json.dumps(compact_context, ensure_ascii=False),
                failed_item=json.dumps(related_existing, ensure_ascii=False),
                scenario=json.dumps(scenario_batch, ensure_ascii=False),
                feedback=json.dumps(input_data.get("validation", {}), ensure_ascii=False),
            )
            result = await client.generate_structured_output(
                system_prompt="You are a senior software test engineer. Return schema-compliant JSON only.",
                user_prompt=user_prompt,
                response_model=TestCaseBatch,
                request_id=execution_context.request_id,
            )
            generated.extend(result.test_cases)
        return TestCaseBatch(test_cases=generated)
