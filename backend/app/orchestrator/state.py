import uuid
from datetime import datetime,timezone
from typing import Any,TypedDict
WORKFLOW_STAGE_PROGRESS: dict[str, int] = {
    "pending": 0,
    "load_input": 5,
    "preparing_context": 15,
    "generating_scenarios": 30,
    "validating_scenarios": 45,
    "scenario_manual_review": 50,
    "generating_test_cases": 65,
    "validating_test_cases": 80,
    "testcase_manual_review": 85,
    "persist_results": 95,
    "completed": 100,
    "failed": 100,
    "cancelled": 100,
}

def workflow_progress(current_stage: str | None) -> int:
    """Return a derived, backward-compatible percentage for a workflow stage."""
    return WORKFLOW_STAGE_PROGRESS.get(current_stage or "pending", 0)

class WorkflowState(TypedDict,total=False):
    workflow_id:uuid.UUID; project_id:uuid.UUID; source_type:str; input_payload:dict[str,Any]; mock_mode:bool; cache_key:str; cache_hit:bool; structured_context:dict[str,Any]; scenarios:list[dict[str,Any]]; scenario_validation:dict[str,Any]; scenario_attempt_count:int; test_cases:list[dict[str,Any]]; testcase_validation:dict[str,Any]; testcase_attempt_count:int; current_stage:str; progress_percentage:int; status:str; errors:list[str]; manual_intervention_reason:str|None; started_at:datetime; completed_at:datetime|None; cancelled:bool
def initial_state(workflow_id,project_id,source_type,input_payload,mock_mode=False)->WorkflowState:
    return {"workflow_id":workflow_id,"project_id":project_id,"source_type":source_type,"input_payload":input_payload,"mock_mode":mock_mode,"scenario_attempt_count":0,"testcase_attempt_count":0,"scenarios":[],"test_cases":[],"current_stage":"pending","progress_percentage":0,"status":"pending","errors":[],"started_at":datetime.now(timezone.utc),"completed_at":None,"cancelled":False}
