import asyncio,json,uuid
from fastapi import APIRouter,status
from fastapi.responses import StreamingResponse
from app.schemas.input_schema import WorkflowStartRequest
from app.schemas.workflow_schema import WorkflowStartResponse,ResumeRequest
from app.services.workflow_service import workflow_service
router=APIRouter(prefix="/workflows",tags=["AI workflows"])
@router.post("/start",response_model=WorkflowStartResponse,status_code=status.HTTP_202_ACCEPTED,summary="Start test generation workflow")
async def start_workflow(request:WorkflowStartRequest):
    s=await workflow_service.start(request);return WorkflowStartResponse(workflow_id=s["workflow_id"],project_id=s["project_id"],status=s["status"])
@router.get("/{workflow_id}",summary="Get workflow status")
async def get_workflow(workflow_id:uuid.UUID): return workflow_service.get(workflow_id)
@router.get("/{workflow_id}/result",summary="Get generated results")
async def get_result(workflow_id:uuid.UUID):
    s=workflow_service.get(workflow_id);return {k:s.get(k) for k in ("workflow_id","status","structured_context","scenarios","scenario_validation","test_cases","testcase_validation")}
@router.get("/{workflow_id}/events",summary="Stream workflow status events")
async def events(workflow_id:uuid.UUID):
    async def stream():
        last=None
        while True:
            s=workflow_service.get(workflow_id); snapshot={"status":s["status"],"current_stage":s["current_stage"]}
            if snapshot!=last: yield f"data: {json.dumps(snapshot)}\n\n";last=snapshot
            if s["status"] in {"completed","failed","cancelled","scenario_manual_review","testcase_manual_review"}: break
            await asyncio.sleep(.5)
    return StreamingResponse(stream(),media_type="text/event-stream")
@router.post("/{workflow_id}/resume",summary="Resume after manual correction")
async def resume(workflow_id:uuid.UUID,request:ResumeRequest): return await workflow_service.resume(workflow_id,request)
@router.post("/{workflow_id}/cancel",summary="Cancel workflow")
async def cancel(workflow_id:uuid.UUID): return await workflow_service.cancel(workflow_id)
