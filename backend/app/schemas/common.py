import uuid
from enum import Enum
from datetime import datetime
from pydantic import BaseModel,ConfigDict,Field
class ORMModel(BaseModel): model_config=ConfigDict(from_attributes=True)
class ProjectCreate(BaseModel): name:str=Field(examples=["Employee Leave Management Testing"]);description:str|None=None;external_project_id:str|None=None
class ProjectUpdate(BaseModel): name:str|None=None;description:str|None=None;external_project_id:str|None=None;status:str|None=None
class ProjectRead(ORMModel): id:uuid.UUID;name:str;description:str|None;external_project_id:str|None;status:str;created_at:datetime;updated_at:datetime
class InputPayload(BaseModel):
    tech_stack:dict=Field(default_factory=dict);functional_requirements:list=Field(default_factory=list);non_functional_requirements:list=Field(default_factory=list);epics:list=Field(default_factory=list);features:list=Field(default_factory=list);user_stories:list=Field(default_factory=list);acceptance_criteria:list=Field(default_factory=list);business_rules:list=Field(default_factory=list);dependencies:list=Field(default_factory=list);constraints:list=Field(default_factory=list)
class InputRead(ORMModel): id:uuid.UUID;project_id:uuid.UUID;input_version:int;source_type:str;payload:dict;is_current:bool;created_at:datetime
class EntityEdit(BaseModel):
    title:str;description:str="";type:str="functional";priority:str="medium";preconditions:list=Field(default_factory=list);test_data:dict|list=Field(default_factory=dict);postconditions:list=Field(default_factory=list);expected_business_outcome:str="";steps:list[dict]=Field(default_factory=list);traceability:dict=Field(default_factory=dict)
class FeedbackRequest(BaseModel): feedback:str=Field(min_length=1);submitted_by:uuid.UUID|None=None
class ApprovalRequest(BaseModel): version_id:uuid.UUID;comments:str|None=None;action_by:uuid.UUID|None=None

class WorkflowStatus(str,Enum):
    pending="pending"; preparing_context="preparing_context"; generating_scenarios="generating_scenarios"; validating_scenarios="validating_scenarios"; scenario_manual_review="scenario_manual_review"; generating_test_cases="generating_test_cases"; validating_test_cases="validating_test_cases"; testcase_manual_review="testcase_manual_review"; completed="completed"; failed="failed"; cancelled="cancelled"
class ValidationStatus(str,Enum): pending="pending"; passed="passed"; failed="failed"; manual_review="manual_review"
class ApprovalStatus(str,Enum): draft="draft"; approved="approved"; rejected="rejected"
class SourceType(str,Enum): manual="manual"; database="database"
class Priority(str,Enum): low="low"; medium="medium"; high="high"; critical="critical"
class ScenarioType(str,Enum): positive="positive"; negative="negative"; boundary="boundary"; integration="integration"; security="security"; performance="performance"; accessibility="accessibility"; data_validation="data_validation"
