import uuid
from typing import Any
from pydantic import BaseModel,ConfigDict,Field
from app.schemas.common import SourceType
class TraceabilityEntry(BaseModel): source_id:str; target_ids:list[str]=Field(default_factory=list)
class StructuredContext(BaseModel):
    model_config=ConfigDict(extra="forbid")
    project_id:uuid.UUID; functional_requirements:list[Any]=Field(default_factory=list); non_functional_requirements:list[Any]=Field(default_factory=list)
    epics:list[Any]=Field(default_factory=list); features:list[Any]=Field(default_factory=list); user_stories:list[Any]=Field(default_factory=list); acceptance_criteria:list[Any]=Field(default_factory=list)
    business_rules:list[Any]=Field(default_factory=list); dependencies:list[Any]=Field(default_factory=list); constraints:list[Any]=Field(default_factory=list); tech_stack:dict[str,Any]=Field(default_factory=dict)
    traceability_map:list[TraceabilityEntry]=Field(default_factory=list); source_type:SourceType; metadata:dict[str,Any]=Field(default_factory=dict)
