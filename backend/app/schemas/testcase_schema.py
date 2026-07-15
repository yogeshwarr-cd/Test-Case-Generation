import uuid
from typing import Any
from pydantic import BaseModel,ConfigDict,Field,model_validator
from app.schemas.common import Priority
class TestStep(BaseModel): step_number:int=Field(ge=1); action:str=Field(min_length=1); expected_result:str=Field(min_length=1)
class TestCase(BaseModel):
    model_config=ConfigDict(extra="forbid")
    test_case_id:uuid.UUID=Field(default_factory=uuid.uuid4); scenario_id:uuid.UUID; project_id:uuid.UUID; title:str=Field(min_length=1); description:str=Field(min_length=1); test_case_type:str; priority:Priority=Priority.medium
    preconditions:list[str]=Field(default_factory=list); test_data:dict[str,Any]=Field(default_factory=dict); steps:list[TestStep]=Field(min_length=1); postconditions:list[str]=Field(default_factory=list); requirement_ids:list[str]=Field(default_factory=list); acceptance_criteria_ids:list[str]=Field(default_factory=list); automation_candidate:bool=False; generation_metadata:dict[str,Any]=Field(default_factory=dict)
    @model_validator(mode="after")
    def ordered(self):
        if [s.step_number for s in self.steps]!=list(range(1,len(self.steps)+1)): raise ValueError("steps must be consecutively ordered")
        return self
class TestCaseBatch(BaseModel): test_cases:list[TestCase]
