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
        client = self.llm_client or build_llm_client(
            task, mock_mode=execution_context.metadata.get("mock_mode")
        )
        context_dict = context.model_dump(mode="json") if context else {}
        scenario_items = scenarios.model_dump(mode="json")["scenarios"]
        existing = input_data.get("existing_test_cases", [])

        async def generate_batch(selected):
            compact_context = scoped_context(context_dict, selected) if context else {}
            scenario_ids = {str(item["scenario_id"]) for item in selected}
            related_existing = [
                item for item in existing if str(item.get("scenario_id")) in scenario_ids
            ]
            scenario_batch = {"scenarios": selected}
            user_prompt = self.prompt_loader.render(
                template,
                scenarios=json.dumps(scenario_batch, ensure_ascii=False),
                context=json.dumps(compact_context, ensure_ascii=False),
                failed_item=json.dumps(related_existing, ensure_ascii=False),
                scenario=json.dumps(scenario_batch, ensure_ascii=False),
                feedback=json.dumps(input_data.get("validation", {}), ensure_ascii=False),
            )
            return await client.generate_structured_output(
                system_prompt="You are a senior software test engineer. Return schema-compliant JSON only.",
                user_prompt=user_prompt,
                response_model=TestCaseBatch,
                request_id=execution_context.request_id,
            )

        generated = []
        for batch in batches(scenario_items, settings.llm_testcase_batch_size):
            result = await generate_batch(batch)
            by_scenario = {}
            for test_case in result.test_cases:
                by_scenario.setdefault(str(test_case.scenario_id), test_case)
            for scenario in batch:
                scenario_id = str(scenario["scenario_id"])
                if scenario_id not in by_scenario:
                    singleton = await generate_batch([scenario])
                    match = next(
                        (case for case in singleton.test_cases if str(case.scenario_id) == scenario_id),
                        None,
                    )
                    if match is None:
                        raise ValueError(f"LLM did not return a complete test case for scenario {scenario_id}")
                    by_scenario[scenario_id] = match
            ordered = [by_scenario[str(scenario["scenario_id"])] for scenario in batch]
            for test_case in ordered:
                test_case.source_references=list(dict.fromkeys(test_case.source_references+[str(x) for x in context_dict.get("image_ids",[])]))
            generated.extend(ordered)
        return TestCaseBatch(test_cases=generated)
