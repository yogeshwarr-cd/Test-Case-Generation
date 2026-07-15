import uuid
from datetime import datetime
from pydantic import BaseModel,ConfigDict,Field
class ORMModel(BaseModel): model_config=ConfigDict(from_attributes=True)
class ProjectCreate(BaseModel): name:str=Field(examples=["Employee Leave Management Testing"]);description:str|None=None;external_project_id:str|None=None
class ProjectUpdate(BaseModel): name:str|None=None;description:str|None=None;external_project_id:str|None=None;status:str|None=None
class ProjectRead(ORMModel): id:uuid.UUID;name:str;description:str|None;external_project_id:str|None;status:str;created_at:datetime;updated_at:datetime
class InputPayload(BaseModel): tech_stack:dict={};functional_requirements:list=[];non_functional_requirements:list=[];epics:list=[];features:list=[];user_stories:list=[];acceptance_criteria:list=[];business_rules:list=[];dependencies:list=[];constraints:list=[]
class InputRead(ORMModel): id:uuid.UUID;project_id:uuid.UUID;input_version:int;source_type:str;payload:dict;is_current:bool;created_at:datetime
class EntityEdit(BaseModel): title:str;description:str="";type:str="functional";priority:str="medium";preconditions:list=[];test_data:dict|list={};postconditions:list=[];expected_business_outcome:str="";steps:list[dict]=[];traceability:dict={}
class FeedbackRequest(BaseModel): feedback:str=Field(min_length=1);submitted_by:uuid.UUID|None=None
class ApprovalRequest(BaseModel): version_id:uuid.UUID;comments:str|None=None;action_by:uuid.UUID|None=None
