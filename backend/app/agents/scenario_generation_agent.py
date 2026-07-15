from app.agents.base_agent import BaseAgent,ExecutionContext
from app.schemas.context_schema import StructuredContext
from app.schemas.scenario_schema import ScenarioBatch,Scenario
from app.schemas.common import ScenarioType,Priority
from app.utils.validators import item_id,item_text
class ScenarioGenerationAgent(BaseAgent[ScenarioBatch]):
    output_model=ScenarioBatch
    async def run(self,input_data,execution_context:ExecutionContext)->ScenarioBatch:
        context=StructuredContext.model_validate(input_data)
        scenarios=[]
        ac_ids=[item_id(x,"AC",i) for i,x in enumerate(context.acceptance_criteria)]
        req_ids=[item_id(x,"REQ",i) for i,x in enumerate(context.functional_requirements)]
        for i,story in enumerate(context.user_stories):
            sid=item_id(story,"US",i); text=item_text(story)
            for kind,title in ((ScenarioType.positive,"Successful"),(ScenarioType.negative,"Invalid"),(ScenarioType.boundary,"Boundary")):
                scenarios.append(Scenario(project_id=context.project_id,title=f"{title}: {text}",description=f"Verify {kind.value} behavior for {text}",scenario_type=kind,priority=Priority.high if kind==ScenarioType.positive else Priority.medium,preconditions=["System is available"],test_data_requirements=[f"{kind.value} data"],expected_business_outcome=f"The {kind.value} path follows the documented requirement",requirement_ids=req_ids,user_story_ids=[sid],acceptance_criteria_ids=ac_ids,source_references=[sid],generation_metadata={"deterministic":True}))
        return ScenarioBatch(scenarios=scenarios)
