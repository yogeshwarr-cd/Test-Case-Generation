import uuid
from enum import Enum
from typing import Any
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from app.schemas.common import Priority,ScenarioType
class Scenario(BaseModel):
    model_config=ConfigDict(extra="ignore")
    scenario_id:uuid.UUID=Field(default_factory=uuid.uuid4); project_id:uuid.UUID; title:str=Field(min_length=1); description:str=Field(min_length=1); scenario_type:ScenarioType; priority:Priority=Priority.medium
    preconditions:list[str]=Field(default_factory=list); test_data_requirements:list[str]=Field(default_factory=list); expected_business_outcome:str=Field(min_length=1)
    requirement_ids:list[str]=Field(default_factory=list); feature_ids:list[str]=Field(default_factory=list); user_story_ids:list[str]=Field(default_factory=list); acceptance_criteria_ids:list[str]=Field(default_factory=list); source_references:list[str]=Field(default_factory=list); generation_metadata:dict[str,Any]=Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_common_llm_field_names(cls, value):
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        aliases = {
            "title": ("scenario_title", "scenario_name", "name"),
            "description": ("scenario_description", "details", "objective"),
            "expected_business_outcome": (
                "expected_outcome",
                "expected_result",
                "business_outcome",
            ),
            "scenario_type": ("type",),
        }
        for target, candidates in aliases.items():
            if normalized.get(target) not in (None, ""):
                continue
            for candidate in candidates:
                if normalized.get(candidate) not in (None, ""):
                    normalized[target] = normalized[candidate]
                    break
        return normalized

    @field_validator("scenario_id", mode="before")
    @classmethod
    def replace_display_id_with_uuid(cls, value):
        if value in (None, ""):
            return uuid.uuid4()
        try:
            return uuid.UUID(str(value))
        except (TypeError, ValueError, AttributeError):
            return uuid.uuid4()

    @field_validator("scenario_type", "priority", mode="before")
    @classmethod
    def normalize_enum_values(cls, value):
        if isinstance(value, Enum):
            return value.value
        return str(value).strip().lower().replace("-", "_").replace(" ", "_")
class ScenarioBatch(BaseModel): scenarios:list[Scenario]
