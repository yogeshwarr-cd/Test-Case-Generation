import uuid
from enum import Enum
from typing import Any
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from app.schemas.common import Priority
class TestStep(BaseModel): step_number:int=Field(ge=1); action:str=Field(min_length=1); expected_result:str=Field(min_length=1)
class TestCase(BaseModel):
    model_config=ConfigDict(extra="ignore")
    test_case_id:uuid.UUID=Field(default_factory=uuid.uuid4); scenario_id:uuid.UUID=Field(default_factory=uuid.uuid4); project_id:uuid.UUID=Field(default_factory=uuid.uuid4); title:str=Field(min_length=1); description:str=Field(min_length=1); test_case_type:str=Field(default="functional"); priority:Priority=Priority.medium
    preconditions:list[str]=Field(default_factory=list); test_data:dict[str,Any]=Field(default_factory=dict); steps:list[TestStep]=Field(min_length=1); postconditions:list[str]=Field(default_factory=list); requirement_ids:list[str]=Field(default_factory=list); acceptance_criteria_ids:list[str]=Field(default_factory=list); source_references:list[str]=Field(default_factory=list); automation_candidate:bool=False; generation_metadata:dict[str,Any]=Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_common_llm_field_names(cls, value):
        if isinstance(value, str):
            text = value.strip()
            return {
                "scenario_id": uuid.uuid4(),
                "project_id": uuid.uuid4(),
                "title": text[:120] or "Generated Test Case",
                "description": text or "Generated test case description",
                "test_case_type": "functional",
                "steps": [{"step_number": 1, "action": text or "Execute test case", "expected_result": "Step completes successfully"}]
            }
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        aliases = {
            "title": ("test_case_title", "testcase_title", "name"),
            "description": ("test_case_description", "details", "objective", "summary"),
            "test_case_type": ("test_type", "type"),
            "steps": ("test_steps", "actions", "execution_steps"),
        }
        for target, candidates in aliases.items():
            if normalized.get(target) not in (None, ""):
                continue
            for candidate in candidates:
                if normalized.get(candidate) not in (None, ""):
                    normalized[target] = normalized[candidate]
                    break
        if not str(normalized.get("title") or "").strip():
            normalized["title"] = str(normalized.get("description") or "Generated Test Case")[:120]
        if not str(normalized.get("description") or "").strip():
            normalized["description"] = str(normalized.get("title") or "Generated test case description")
        if not str(normalized.get("test_case_type") or "").strip():
            normalized["test_case_type"] = "functional"
        if normalized.get("scenario_id") in (None, ""):
            normalized["scenario_id"] = uuid.uuid4()
        if normalized.get("project_id") in (None, ""):
            normalized["project_id"] = uuid.uuid4()
        if not normalized.get("steps"):
            title = normalized.get("title") or "described functionality"
            normalized["steps"] = [{"step_number": 1, "action": f"Verify {title}", "expected_result": f"{title} behaves as expected"}]
        return normalized

    @field_validator("test_case_id", "scenario_id", "project_id", mode="before")
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
        return str(value or "medium").strip().lower()

    @field_validator("steps", mode="before")
    @classmethod
    def normalize_step_numbers(cls, value):
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list) or not value:
            return [{"step_number": 1, "action": "Execute test step", "expected_result": "Step completes successfully"}]
        normalized_steps = []
        for index, step in enumerate(value, start=1):
            if isinstance(step, str):
                normalized_steps.append({
                    "step_number": index,
                    "action": step.strip() or "Execute test step",
                    "expected_result": "Step completes successfully"
                })
            elif isinstance(step, dict):
                s_dict = dict(step)
                s_dict["step_number"] = index
                if not str(s_dict.get("action") or "").strip():
                    s_dict["action"] = "Execute test step"
                if not str(s_dict.get("expected_result") or "").strip():
                    s_dict["expected_result"] = "Step completes successfully"
                normalized_steps.append(s_dict)
            else:
                normalized_steps.append({
                    "step_number": index,
                    "action": "Execute test step",
                    "expected_result": "Step completes successfully"
                })
        return normalized_steps

    @model_validator(mode="after")
    def ordered(self):
        if [s.step_number for s in self.steps]!=list(range(1,len(self.steps)+1)):
            for idx, step in enumerate(self.steps, start=1):
                step.step_number = idx
        return self

class TestCaseBatch(BaseModel):
    test_cases: list[TestCase] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def normalize_batch(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        cases = data.get("test_cases")
        if cases is None:
            if any(isinstance(v, (dict, str)) for v in data.values()):
                cases = list(data.values())
                data = {"test_cases": cases}
        elif isinstance(cases, dict):
            cases = list(cases.values())
            data["test_cases"] = cases
        if isinstance(data.get("test_cases"), list):
            normalized = []
            for item in data["test_cases"]:
                if isinstance(item, dict):
                    if len(item) == 1 and not any(k in item for k in ("title", "test_case_type", "steps", "scenario_id", "description")):
                        inner = list(item.values())[0]
                        if isinstance(inner, (dict, str)):
                            normalized.append(inner)
                        else:
                            normalized.append(item)
                    else:
                        normalized.append(item)
                else:
                    normalized.append(item)
            data["test_cases"] = normalized
        return data
