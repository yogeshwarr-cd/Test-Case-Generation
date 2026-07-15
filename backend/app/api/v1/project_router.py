import uuid
from fastapi import APIRouter,Response,status
from app.api.dependencies import DBSession
from app.schemas.common import ProjectCreate,ProjectRead,ProjectUpdate
from app.services.project_service import ProjectService
router=APIRouter(prefix="/projects",tags=["Projects"])
@router.post("",response_model=ProjectRead,status_code=201)
async def create(body:ProjectCreate,db:DBSession): return await ProjectService(db).create(body.model_dump())
@router.get("",response_model=list[ProjectRead])
async def list_projects(db:DBSession): return await ProjectService(db).list()
@router.get("/{project_id}",response_model=ProjectRead)
async def get(project_id:uuid.UUID,db:DBSession): return await ProjectService(db).get(project_id)
@router.put("/{project_id}",response_model=ProjectRead)
async def update(project_id:uuid.UUID,body:ProjectUpdate,db:DBSession): return await ProjectService(db).update(project_id,body.model_dump(exclude_unset=True))
@router.delete("/{project_id}",status_code=204)
async def delete(project_id:uuid.UUID,db:DBSession): await ProjectService(db).delete(project_id);return Response(status_code=204)
