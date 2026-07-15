import uuid
from fastapi import APIRouter
from app.services.workflow_service import workflow_service
router=APIRouter(prefix="/validations",tags=["AI validation"])
@router.get("/{workflow_id}")
async def validations(workflow_id:uuid.UUID):
    s=workflow_service.get(workflow_id);return {"scenario_validation":s.get("scenario_validation"),"testcase_validation":s.get("testcase_validation")}
@router.get("/{workflow_id}/issues")
async def issues(workflow_id:uuid.UUID):
    s=workflow_service.get(workflow_id);return [i for key in ("scenario_validation","testcase_validation") for i in (s.get(key) or {}).get("issues",[])]
@router.post("/{workflow_id}/revalidate")
async def revalidate(workflow_id:uuid.UUID):
    s=workflow_service.get(workflow_id);return {"message":"Revalidation uses the current generated versions","status":s["status"]}
