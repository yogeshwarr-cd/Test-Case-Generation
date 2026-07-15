import uuid
from abc import ABC,abstractmethod
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from app.core.exceptions import InputNotFound, ProjectNotFound
from app.repositories.project_repository import ProjectRepository
from app.repositories.input_repository import InputRepository
class InputSource(ABC):
    @abstractmethod
    async def load(self,project_id:uuid.UUID)->dict: ...
class ManualInputSource(InputSource):
    def __init__(self,session): self.repo=InputRepository(session)
    async def load(self,project_id):
        row=await self.repo.get_current(project_id)
        if not row: raise InputNotFound("Project input was not found")
        return row.payload
class DatabaseInputSource(InputSource):
    def __init__(self,mode=None): self.mode=mode or settings.backend_1_integration_mode
    async def load(self,project_id):
        if self.mode=="api":
            async with httpx.AsyncClient(base_url=settings.backend_1_api_url,timeout=30) as client: response=await client.get(f"/projects/{project_id}/approved-context");response.raise_for_status();return response.json()
        if not settings.backend_1_database_url: raise InputNotFound("BACKEND_1_DATABASE_URL is not configured")
        # The Backend 1 mapping is deliberately centralized here. Change it only when
        # the shared contract is agreed; no other module depends on its table layout.
        engine=create_async_engine(settings.backend_1_database_url)
        try:
            async with engine.connect() as connection:
                row=(await connection.execute(text("SELECT payload FROM approved_project_contexts WHERE external_project_id=:project_id AND approval_status='approved' AND is_current=true AND is_active=true"),{"project_id":str(project_id)})).mappings().first()
                if not row: raise InputNotFound("Approved Backend 1 context was not found")
                return dict(row["payload"])
        finally: await engine.dispose()
class InputService:
    def __init__(self,session): self.session=session;self.repo=InputRepository(session);self.projects=ProjectRepository(session)
    async def _ensure_project(self, project_id):
        project=await self.projects.get(project_id)
        if not project or not project.is_active: raise ProjectNotFound("Project was not found")
    async def create_version(self,project_id,payload):
        await self._ensure_project(project_id)
        row=await self.repo.create_version(project_id,payload);await self.session.commit();return row
    async def update_version(self,project_id,input_id,payload):
        await self._ensure_project(project_id)
        existing=await self.repo.get_by_id(input_id)
        if not existing or existing.project_id!=project_id: raise InputNotFound("Project input was not found")
        row=await self.repo.create_version(project_id,payload,existing.source_type);await self.session.commit();return row
    async def list(self,project_id): return await self.repo.list_by_project(project_id)
    async def current(self,project_id):
        row=await self.repo.get_current(project_id)
        if not row: raise InputNotFound("Project input was not found")
        return row
