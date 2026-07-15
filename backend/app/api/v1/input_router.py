import uuid
from fastapi import APIRouter
from app.api.dependencies import DBSession
from app.schemas.common import InputPayload,InputRead
from app.services.input_service import InputService
router=APIRouter(prefix="/projects/{project_id}/inputs",tags=["Project inputs"])
@router.post("",response_model=InputRead,status_code=201)
async def create(project_id:uuid.UUID,body:InputPayload,db:DBSession): return await InputService(db).create_version(project_id,body.model_dump())
@router.get("",response_model=list[InputRead])
async def list_inputs(project_id:uuid.UUID,db:DBSession): return await InputService(db).list(project_id)
@router.get("/current",response_model=InputRead)
async def current(project_id:uuid.UUID,db:DBSession): return await InputService(db).current(project_id)
@router.put("/{input_id}",response_model=InputRead)
async def update(project_id:uuid.UUID,input_id:uuid.UUID,body:InputPayload,db:DBSession): return await InputService(db).create_version(project_id,body.model_dump())
