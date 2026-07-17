import uuid
from enum import Enum
from typing import Any
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from app.schemas.common import Priority
class TestStep(BaseModel): step_number:int=Field(ge=1); action:str=Field(min_length=1); expected_result:str=Field(min_length=1)
class TestCase(BaseModel):
    model_config=ConfigDict(extra="ignore")
    test_case_id:uuid.UUID=Field(default_factory=uuid.uuid4); scenario_id:uuid.UUID; project_id:uuid.UUID; title:str=Field(min_length=1); description:str=Field(min_length=1); test_case_type:str; priority:Priority=Priority.medium
    preconditions:list[str]=Field(default_factory=list); test_data:dict[str,Any]=Field(default_factory=dict); steps:list[TestStep]=Field(min_length=1); postconditions:list[str]=Field(default_factory=list); requirement_ids:list[str]=Field(default_factory=list); acceptance_criteria_ids:list[str]=Field(default_factory=list); source_references:list[str]=Field(default_factory=list); automation_candidate:bool=False; generation_metadata:dict[str,Any]=Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_common_llm_field_names(cls, value):
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        aliases = {
            "title": ("test_case_title", "testcase_title", "name"),
            "description": ("test_case_description", "details", "objective"),
            "test_case_type": ("test_type", "type"),
            "steps": ("test_steps",),
        }
        for target, candidates in aliases.items():
            if normalized.get(target) not in (None, ""):
                continue
            for candidate in candidates:
                if normalized.get(candidate) not in (None, ""):
                    normalized[target] = normalized[candidate]
                    break
        return normalized

    @field_validator("test_case_id", mode="before")
    @classmethod
    def replace_display_id_with_uuid(cls, value):
        if value in (None, ""):
            return uuid.uuid4()
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            return uuid.uuid4()

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, value):
        if isinstance(value, Enum):
            return value.value
        return str(value).strip().lower()

    @field_validator("steps", mode="before")
    @classmethod
    def normalize_step_numbers(cls, value):
        if not isinstance(value, list):
            return value
        return [
            {**step, "step_number": index}
            if isinstance(step, dict)
            else step
            for index, step in enumerate(value, start=1)
        ]

    @model_validator(mode="after")
    def ordered(self):
        if [s.step_number for s in self.steps]!=list(range(1,len(self.steps)+1)): raise ValueError("steps must be consecutively ordered")
        return self
class TestCaseBatch(BaseModel): test_cases:list[TestCase]
