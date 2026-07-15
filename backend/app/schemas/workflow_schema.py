import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel,Field
from app.schemas.common import WorkflowStatus
class WorkflowStartResponse(BaseModel): workflow_id:uuid.UUID; project_id:uuid.UUID; status:WorkflowStatus; message:str="Workflow started"
class WorkflowStatusResponse(BaseModel): workflow_id:uuid.UUID; project_id:uuid.UUID; status:WorkflowStatus; current_stage:str; scenario_attempt_count:int=Field(ge=0,le=3); testcase_attempt_count:int=Field(ge=0,le=3); errors:list[str]=Field(default_factory=list)
class ResumeRequest(BaseModel): stage:str; feedback:str=Field(min_length=1); corrected_data:dict[str,Any]=Field(default_factory=dict)
class WorkflowResultResponse(BaseModel): workflow_id:uuid.UUID; status:WorkflowStatus; structured_context:dict[str,Any]|None=None; scenarios:list[dict[str,Any]]=Field(default_factory=list); test_cases:list[dict[str,Any]]=Field(default_factory=list)
