import uuid
from app.agents.base_agent import BaseAgent,ExecutionContext
from app.schemas.context_schema import StructuredContext,TraceabilityEntry
from app.schemas.input_schema import ManualInputPayload
from app.schemas.common import SourceType
from app.utils.validators import deduplicate,item_id,item_text
from app.image_processing.image_pipeline import ImagePipeline
from app.image_processing.context_fusion import fuse

PREFIXES = {
    "functional_requirements": "REQ",
    "non_functional_requirements": "NFR",
    "epics": "EPIC",
    "features": "FEAT",
    "user_stories": "US",
    "acceptance_criteria": "AC",
    "business_rules": "BR",
    "dependencies": "DEP",
    "constraints": "CON",
}

def _structured_items(items, prefix):
    structured = []
    for index, item in enumerate(items):
        if isinstance(item, dict):
            normalized = dict(item)
            normalized.setdefault("id", item_id(item, prefix, index))
            if not any(normalized.get(key) for key in ("text", "title", "description", "name")):
                normalized["text"] = item_text(item)
        else:
            normalized = {"id": item_id(item, prefix, index), "text": item_text(item)}
        structured.append(normalized)
    return structured

class ContextPreparationAgent(BaseAgent[StructuredContext]):
    output_model=StructuredContext
    async def run(self,input_data,execution_context:ExecutionContext)->StructuredContext:
        payload=ManualInputPayload.model_validate(input_data.get("input_payload",input_data)).model_dump()
        for key,value in payload.items():
            if isinstance(value,list): payload[key]=deduplicate(value)
        if not payload["user_stories"]: raise ValueError("At least one user story is required")
        for key, prefix in PREFIXES.items():
            payload[key] = _structured_items(payload[key], prefix)
        visual_context=[]
        for image_id in payload.get("image_ids",[]):
            record=ImagePipeline.get(image_id)
            if record: visual_context.append(record["compact_context"])
        payload["visual_context"]=[fuse(payload,visual_context)] if visual_context else []
        target_ids = [
            str(item["id"])
            for key in (
                "functional_requirements",
                "non_functional_requirements",
                "epics",
                "features",
                "acceptance_criteria",
                "business_rules",
                "dependencies",
                "constraints",
            )
            for item in payload[key]
        ]
        trace=[
            TraceabilityEntry(source_id=str(story["id"]),target_ids=target_ids)
            for story in payload["user_stories"]
        ]
        return StructuredContext(project_id=input_data.get("project_id") or uuid.uuid4(),source_type=input_data.get("source_type",SourceType.manual),traceability_map=trace,metadata={"normalized":True},**payload)
