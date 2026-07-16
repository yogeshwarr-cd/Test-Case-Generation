import json

from app.agents.base_agent import BaseAgent, ExecutionContext
from app.llm.client import build_llm_client
from app.llm.context import batches, scoped_context
from app.core.config import settings
from app.llm.prompt_loader import PromptLoader
from app.schemas.context_schema import StructuredContext
from app.schemas.scenario_schema import ScenarioBatch


class ScenarioGenerationAgent(BaseAgent[ScenarioBatch]):
    output_model = ScenarioBatch

    def __init__(self, llm_client=None, prompt_loader=None):
        super().__init__(llm_client=llm_client)
        self.llm_client = llm_client
        self.prompt_loader = prompt_loader or PromptLoader()

    async def run(self, input_data, execution_context: ExecutionContext) -> ScenarioBatch:
        context_data = input_data.get("context", input_data)
        context = StructuredContext.model_validate(context_data)
        template = "scenario_regeneration.jinja2" if "validation" in input_data else "scenario_generation.jinja2"
        task = "regeneration" if "validation" in input_data else "generation"
        client = self.llm_client or build_llm_client(task)
        context_dict = context.model_dump(mode="json")
        work_items = (
            input_data.get("existing_scenarios", [])
            if task == "regeneration"
            else context_dict["user_stories"]
        )
        generated = []
        for batch in batches(work_items, settings.llm_scenario_batch_size):
            compact_context = scoped_context(context_dict, batch)
            user_prompt = self.prompt_loader.render(
                template,
                context=json.dumps(compact_context, ensure_ascii=False),
                failed_item=json.dumps(batch if task == "regeneration" else [], ensure_ascii=False),
                feedback=json.dumps(input_data.get("validation", {}), ensure_ascii=False),
            )
            result = await client.generate_structured_output(
                system_prompt="You are a senior QA architect. Return schema-compliant JSON only.",
                user_prompt=user_prompt,
                response_model=ScenarioBatch,
                request_id=execution_context.request_id,
            )
            story_ids = [
                str(item["id"]) for item in batch
                if isinstance(item, dict) and item.get("id")
            ]
            if not story_ids:
                story_ids = [
                    str(item["id"])
                    for item in compact_context.get("user_stories", [])
                    if isinstance(item, dict) and item.get("id")
                ]
            requirement_ids = [
                str(item["id"])
                for key in ("functional_requirements", "non_functional_requirements")
                for item in compact_context.get(key, [])
                if isinstance(item, dict) and item.get("id")
            ]
            feature_ids = [
                str(item["id"]) for item in compact_context.get("features", [])
                if isinstance(item, dict) and item.get("id")
            ]
            acceptance_criteria_ids = [
                str(item["id"]) for item in compact_context.get("acceptance_criteria", [])
                if isinstance(item, dict) and item.get("id")
            ]
            for scenario in result.scenarios:
                scenario.user_story_ids = scenario.user_story_ids or story_ids
                scenario.requirement_ids = scenario.requirement_ids or requirement_ids
                scenario.feature_ids = scenario.feature_ids or feature_ids
                scenario.acceptance_criteria_ids = (
                    scenario.acceptance_criteria_ids or acceptance_criteria_ids
                )
                scenario.source_references = (
                    scenario.source_references or story_ids
                )
            generated.extend(result.scenarios)
        return ScenarioBatch(scenarios=generated)
