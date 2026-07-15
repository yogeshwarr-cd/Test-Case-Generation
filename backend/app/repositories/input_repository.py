import uuid
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.input import ProjectInput
class InputRepository:
    def __init__(self, session: AsyncSession): self.session=session
    async def create_version(self, project_id, payload, source_type="manual", created_by=None):
        await self.session.execute(select(ProjectInput).where(ProjectInput.project_id==project_id).with_for_update())
        version=(await self.session.scalar(select(func.coalesce(func.max(ProjectInput.input_version),0)).where(ProjectInput.project_id==project_id)))+1
        await self.session.execute(update(ProjectInput).where(ProjectInput.project_id==project_id,ProjectInput.is_current.is_(True)).values(is_current=False))
        row=ProjectInput(project_id=project_id,input_version=version,payload=payload,source_type=source_type,created_by=created_by,is_current=True); self.session.add(row); await self.session.flush(); return row
    async def list_by_project(self, project_id): return list((await self.session.scalars(select(ProjectInput).where(ProjectInput.project_id==project_id).order_by(ProjectInput.input_version.desc()))).all())
    async def get_current(self, project_id): return await self.session.scalar(select(ProjectInput).where(ProjectInput.project_id==project_id,ProjectInput.is_current.is_(True)))
