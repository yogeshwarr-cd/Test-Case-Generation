import uuid
from datetime import datetime,timezone
from typing import Any,TypedDict
class WorkflowState(TypedDict,total=False):
    workflow_id:uuid.UUID; project_id:uuid.UUID; source_type:str; input_payload:dict[str,Any]; mock_mode:bool; structured_context:dict[str,Any]; scenarios:list[dict[str,Any]]; scenario_validation:dict[str,Any]; scenario_attempt_count:int; test_cases:list[dict[str,Any]]; testcase_validation:dict[str,Any]; testcase_attempt_count:int; current_stage:str; status:str; errors:list[str]; manual_intervention_reason:str|None; started_at:datetime; completed_at:datetime|None; cancelled:bool
def initial_state(workflow_id,project_id,source_type,input_payload,mock_mode=False)->WorkflowState:
    return {"workflow_id":workflow_id,"project_id":project_id,"source_type":source_type,"input_payload":input_payload,"mock_mode":mock_mode,"scenario_attempt_count":0,"testcase_attempt_count":0,"scenarios":[],"test_cases":[],"current_stage":"pending","status":"pending","errors":[],"started_at":datetime.now(timezone.utc),"completed_at":None,"cancelled":False}
