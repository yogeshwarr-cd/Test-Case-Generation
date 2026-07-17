import asyncio,json,uuid
from fastapi import APIRouter,status
from fastapi.responses import StreamingResponse
from app.schemas.input_schema import WorkflowStartRequest
from app.schemas.workflow_schema import WorkflowStartResponse,ResumeRequest,WorkflowEntityDecisionRequest,WorkflowBulkDecisionRequest,WorkflowRegenerationRequest,WorkflowReviewApprovalRequest
from app.services.workflow_service import workflow_service
router=APIRouter(prefix="/workflows",tags=["AI workflows"])
@router.post("/start",response_model=WorkflowStartResponse,status_code=status.HTTP_202_ACCEPTED,summary="Start test generation workflow")
async def start_workflow(request:WorkflowStartRequest):
    s=await workflow_service.start(request);return WorkflowStartResponse(workflow_id=s["workflow_id"],project_id=s["project_id"],status=s["status"])
@router.get("/{workflow_id}",summary="Get workflow status")
async def get_workflow(workflow_id:uuid.UUID): return workflow_service.get(workflow_id)
@router.get("/{workflow_id}/result",summary="Get generated results")
async def get_result(workflow_id:uuid.UUID):
    s=workflow_service.get(workflow_id);return {k:s.get(k) for k in ("workflow_id","project_id","status","current_stage","errors","manual_intervention_reason","structured_context","scenarios","scenario_validation","test_cases","testcase_validation")}
@router.get("/{workflow_id}/events",summary="Stream workflow status events")
async def events(workflow_id:uuid.UUID):
    async def stream():
        last=None
        while True:
            s=workflow_service.get(workflow_id)
            snapshot={
                "status":s["status"],
                "current_stage":s["current_stage"],
                "scenario_attempt_count":s.get("scenario_attempt_count",0),
                "testcase_attempt_count":s.get("testcase_attempt_count",0),
                "errors":s.get("errors",[]),
                "message":(
                    s.get("manual_intervention_reason")
                    or (s.get("errors") or [None])[-1]
                    or s["current_stage"].replace("_"," ")
                ),
            }
            if snapshot!=last: yield f"data: {json.dumps(snapshot)}\n\n";last=snapshot
            if s["status"] in {"completed","failed","cancelled","scenario_manual_review","testcase_manual_review"}: break
            await asyncio.sleep(.5)
    return StreamingResponse(stream(),media_type="text/event-stream")
@router.post("/{workflow_id}/resume",summary="Resume after manual correction")
async def resume(workflow_id:uuid.UUID,request:ResumeRequest): return await workflow_service.resume(workflow_id,request)
@router.post("/{workflow_id}/cancel",summary="Cancel workflow")
async def cancel(workflow_id:uuid.UUID): return await workflow_service.cancel(workflow_id)
@router.post("/{workflow_id}/decision")
async def decide(workflow_id:uuid.UUID,request:WorkflowEntityDecisionRequest): return workflow_service.decide(workflow_id,request)
@router.post("/{workflow_id}/decision/all")
async def decide_all(workflow_id:uuid.UUID,request:WorkflowBulkDecisionRequest): return workflow_service.decide_all(workflow_id,request)
@router.post("/{workflow_id}/regenerate")
async def regenerate(workflow_id:uuid.UUID,request:WorkflowRegenerationRequest): return await workflow_service.regenerate_entity(workflow_id,request)
@router.post("/{workflow_id}/review/approve")
async def approve_review(workflow_id:uuid.UUID,request:WorkflowReviewApprovalRequest): return await workflow_service.approve_review(workflow_id,request)
