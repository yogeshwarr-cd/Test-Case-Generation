import uuid
from app.agents.base_agent import BaseAgent,ExecutionContext
from app.schemas.context_schema import StructuredContext,TraceabilityEntry
from app.schemas.input_schema import ManualInputPayload
from app.schemas.common import SourceType
from app.utils.validators import deduplicate,item_id
class ContextPreparationAgent(BaseAgent[StructuredContext]):
    output_model=StructuredContext
    async def run(self,input_data,execution_context:ExecutionContext)->StructuredContext:
        payload=ManualInputPayload.model_validate(input_data.get("input_payload",input_data)).model_dump()
        for key,value in payload.items():
            if isinstance(value,list): payload[key]=deduplicate(value)
        if not payload["user_stories"]: raise ValueError("At least one user story is required")
        trace=[TraceabilityEntry(source_id=item_id(s,"US",i),target_ids=[item_id(a,"AC",j) for j,a in enumerate(payload["acceptance_criteria"])]) for i,s in enumerate(payload["user_stories"])]
        return StructuredContext(project_id=input_data.get("project_id") or uuid.uuid4(),source_type=input_data.get("source_type",SourceType.manual),traceability_map=trace,metadata={"normalized":True},**payload)
