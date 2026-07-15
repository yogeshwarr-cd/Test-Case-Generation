from app.core.exceptions import ProjectNotFound
from app.models.project import Project
from app.repositories.project_repository import ProjectRepository
class ProjectService:
    def __init__(self,session): self.session=session;self.repo=ProjectRepository(session)
    async def create(self,data): row=await self.repo.add(Project(**data));await self.session.commit();return row
    async def list(self): return await self.repo.list_active()
    async def get(self,i):
        row=await self.repo.get(i)
        if not row or not row.is_active: raise ProjectNotFound("Project was not found")
        return row
    async def update(self,i,data): row=await self.get(i);[setattr(row,k,v) for k,v in data.items() if v is not None];await self.session.commit();return row
    async def delete(self,i): row=await self.get(i);await self.repo.soft_delete(row);await self.session.commit()
