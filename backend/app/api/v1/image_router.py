import uuid
from fastapi import APIRouter,File,Form,HTTPException,UploadFile
from app.core.config import settings
from app.image_processing import ImagePipeline
router=APIRouter(prefix="/images",tags=["Image analysis"])
@router.post("/upload")
async def upload_image(image:UploadFile=File(...),project_id:uuid.UUID|None=Form(None),image_description:str=Form("")):
    if not settings.image_upload_enabled: raise HTTPException(404,"Image upload is disabled")
    try: record,cached=await ImagePipeline().analyze(await image.read(),image.content_type or "",image.filename or "image",image_description,project_id)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    full=record["full_analysis"];return {"image_id":record["image_id"],"status":"analyzed","image_type":full["image_type"],"screen_type":full["screen_type"],"analysis_confidence":full["overall_confidence"],"warnings":full["warnings"],"cached":cached}
@router.get("/{image_id}")
async def get_analysis(image_id:str):
    record=ImagePipeline.get(image_id)
    if not record: raise HTTPException(404,"Image analysis was not found")
    return record
