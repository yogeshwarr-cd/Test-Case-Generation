import uuid
from fastapi import APIRouter,Response
from app.api.dependencies import DBSession
from app.schemas.common import ApprovalRequest,EntityEdit,FeedbackRequest
from app.services.scenario_service import ScenarioService
from app.services.export_service import ExportService
router=APIRouter(tags=["Scenarios"])
@router.get("/projects/{project_id}/scenarios")
async def list_scenarios(project_id:uuid.UUID,db:DBSession): return await ScenarioService(db).r.list_by_project(project_id)
@router.get("/projects/{project_id}/export/scenarios")
async def export(project_id:uuid.UUID,db:DBSession,format:str="json"): content,media=ExportService.prepare(await ScenarioService(db).r.list_by_project(project_id),format);return Response(content=content,media_type=media,headers={"Content-Disposition":f"attachment; filename=scenarios.{format}"})
@router.get("/scenarios/{entity_id}")
async def get(entity_id:uuid.UUID,db:DBSession): return await ScenarioService(db).get(entity_id)
@router.get("/scenarios/{entity_id}/versions")
async def versions(entity_id:uuid.UUID,db:DBSession): return await ScenarioService(db).r.list_versions(entity_id)
@router.put("/scenarios/{entity_id}")
async def edit(entity_id:uuid.UUID,body:EntityEdit,db:DBSession): return await ScenarioService(db).edit(entity_id,body)
@router.post("/scenarios/{entity_id}/feedback")
async def feedback(entity_id:uuid.UUID,body:FeedbackRequest,db:DBSession): s=ScenarioService(db);return await s.feedback(await s.get(entity_id),body.feedback,body.submitted_by)
@router.post("/scenarios/{entity_id}/regenerate",status_code=202)
async def regenerate(entity_id:uuid.UUID,body:FeedbackRequest,db:DBSession): s=ScenarioService(db);return {"status":"accepted","feedback_id":str((await s.feedback(await s.get(entity_id),body.feedback,body.submitted_by)).id),"workflow_hook":"scenario_regeneration"}
@router.post("/scenarios/{entity_id}/approve")
async def approve(entity_id:uuid.UUID,body:ApprovalRequest,db:DBSession): return await ScenarioService(db).approval(entity_id,body,"approved")
@router.post("/scenarios/{entity_id}/reject")
async def reject(entity_id:uuid.UUID,body:ApprovalRequest,db:DBSession): return await ScenarioService(db).approval(entity_id,body,"rejected")
@router.delete("/scenarios/{entity_id}",status_code=204)
async def delete(entity_id:uuid.UUID,db:DBSession): s=ScenarioService(db);await s.r.soft_delete(await s.get(entity_id));await db.commit();return Response(status_code=204)
