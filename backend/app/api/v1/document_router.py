import uuid

from fastapi import APIRouter, File, UploadFile

from app.schemas.document_schema import DocumentSessionUpdate
from app.services.document_service import document_service

router = APIRouter(prefix="/documents", tags=["Document intake"])


@router.post("/upload")
async def upload_document(document: UploadFile = File(...)):
    return await document_service.upload(document)


@router.put("/{session_id}")
async def update_document_session(session_id: uuid.UUID, body: DocumentSessionUpdate):
    return await document_service.update(session_id, [story.model_dump() for story in body.stories])
