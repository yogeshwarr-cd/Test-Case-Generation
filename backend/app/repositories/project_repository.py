import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import Project
from app.repositories.base_repository import BaseRepository
class ProjectRepository(BaseRepository[Project]):
    def __init__(self, session: AsyncSession): super().__init__(session, Project)
    async def list_active(self): return list((await self.session.scalars(select(Project).where(Project.is_active.is_(True)).order_by(Project.created_at.desc()))).all())
    async def soft_delete(self, project): project.is_active=False; project.status="deleted"; await self.session.flush()
