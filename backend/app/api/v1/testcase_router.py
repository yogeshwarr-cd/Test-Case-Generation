import uuid
from fastapi import APIRouter,Response
from app.api.dependencies import DBSession
from app.schemas.common import ApprovalRequest,EntityEdit,FeedbackRequest
from app.services.testcase_service import TestCaseService
from app.services.export_service import ExportService
router=APIRouter(tags=["Test cases"])
@router.get("/projects/{project_id}/testcases")
async def list_testcases(project_id:uuid.UUID,db:DBSession): return await TestCaseService(db).r.list_by_project(project_id)
@router.get("/projects/{project_id}/export/testcases")
async def export(project_id:uuid.UUID,db:DBSession,format:str="json"): content,media=ExportService.prepare(await TestCaseService(db).r.list_by_project(project_id),format);return Response(content=content,media_type=media,headers={"Content-Disposition":f"attachment; filename=testcases.{format}"})
@router.get("/testcases/{entity_id}")
async def get(entity_id:uuid.UUID,db:DBSession): return await TestCaseService(db).get(entity_id)
@router.get("/testcases/{entity_id}/versions")
async def versions(entity_id:uuid.UUID,db:DBSession): return await TestCaseService(db).r.list_versions(entity_id)
@router.put("/testcases/{entity_id}")
async def edit(entity_id:uuid.UUID,body:EntityEdit,db:DBSession): return await TestCaseService(db).edit(entity_id,body)
@router.post("/testcases/{entity_id}/feedback")
async def feedback(entity_id:uuid.UUID,body:FeedbackRequest,db:DBSession): s=TestCaseService(db);return await s.feedback(await s.get(entity_id),body.feedback,body.submitted_by)
@router.post("/testcases/{entity_id}/regenerate",status_code=202)
async def regenerate(entity_id:uuid.UUID,body:FeedbackRequest,db:DBSession): s=TestCaseService(db);return {"status":"accepted","feedback_id":str((await s.feedback(await s.get(entity_id),body.feedback,body.submitted_by)).id),"workflow_hook":"testcase_regeneration"}
@router.post("/testcases/{entity_id}/approve")
async def approve(entity_id:uuid.UUID,body:ApprovalRequest,db:DBSession): return await TestCaseService(db).approval(entity_id,body,"approved")
@router.post("/testcases/{entity_id}/reject")
async def reject(entity_id:uuid.UUID,body:ApprovalRequest,db:DBSession): return await TestCaseService(db).approval(entity_id,body,"rejected")
@router.delete("/testcases/{entity_id}",status_code=204)
async def delete(entity_id:uuid.UUID,db:DBSession): s=TestCaseService(db);await s.r.soft_delete(await s.get(entity_id));await db.commit();return Response(status_code=204)
