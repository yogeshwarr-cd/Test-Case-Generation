import uuid
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.common import SourceType

class ManualInputPayload(BaseModel):
    model_config=ConfigDict(extra="forbid")
    tech_stack:dict[str,Any]=Field(default_factory=dict)
    functional_requirements:list[Any]=Field(default_factory=list)
    non_functional_requirements:list[Any]=Field(default_factory=list)
    epics:list[Any]=Field(default_factory=list); features:list[Any]=Field(default_factory=list)
    user_stories:list[Any]=Field(default_factory=list); acceptance_criteria:list[Any]=Field(default_factory=list)
    business_rules:list[Any]=Field(default_factory=list); dependencies:list[Any]=Field(default_factory=list); constraints:list[Any]=Field(default_factory=list)
    image_ids:list[str]=Field(default_factory=list)

class WorkflowStartRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    project_id:uuid.UUID|None=None; source_type:SourceType=SourceType.manual; input_payload:ManualInputPayload|None=None; mock_mode:bool=False
    @model_validator(mode="after")
    def source_requirements(self):
        if self.source_type==SourceType.database and not self.project_id: raise ValueError("project_id is required for database source")
        if self.source_type==SourceType.manual and not self.input_payload: raise ValueError("input_payload is required for manual source")
        return self
