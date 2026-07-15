import uuid
from typing import Any
from pydantic import BaseModel,ConfigDict,Field
from app.schemas.common import Priority,ScenarioType
class Scenario(BaseModel):
    model_config=ConfigDict(extra="forbid")
    scenario_id:uuid.UUID=Field(default_factory=uuid.uuid4); project_id:uuid.UUID; title:str=Field(min_length=1); description:str=Field(min_length=1); scenario_type:ScenarioType; priority:Priority=Priority.medium
    preconditions:list[str]=Field(default_factory=list); test_data_requirements:list[str]=Field(default_factory=list); expected_business_outcome:str=Field(min_length=1)
    requirement_ids:list[str]=Field(default_factory=list); feature_ids:list[str]=Field(default_factory=list); user_story_ids:list[str]=Field(default_factory=list); acceptance_criteria_ids:list[str]=Field(default_factory=list); source_references:list[str]=Field(default_factory=list); generation_metadata:dict[str,Any]=Field(default_factory=dict)
class ScenarioBatch(BaseModel): scenarios:list[Scenario]
