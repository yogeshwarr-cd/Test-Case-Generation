import uuid
from typing import Any
from pydantic import BaseModel,ConfigDict,Field
from app.schemas.common import ValidationStatus
class ValidationIssue(BaseModel): issue_code:str; severity:str="error"; description:str; affected_entity_id:uuid.UUID|None=None; recommendation:str|None=None
class ScoreBreakdown(BaseModel): model_config=ConfigDict(extra="allow")
class ValidationResult(BaseModel):
    confidence_score:float=Field(ge=0,le=1); score_breakdown:dict[str,float]; status:ValidationStatus; issues:list[ValidationIssue]=Field(default_factory=list); failed_entity_ids:list[uuid.UUID]=Field(default_factory=list); regeneration_instructions:list[str]=Field(default_factory=list)
