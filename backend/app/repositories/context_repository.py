from sqlalchemy import select, update
from app.models.workflow import StructuredContext
class ContextRepository:
    def __init__(self,session): self.session=session
    async def save_structured_context(self,**values): await self.session.execute(update(StructuredContext).where(StructuredContext.workflow_id==values["workflow_id"]).values(is_current=False)); row=StructuredContext(**values,is_current=True); self.session.add(row); await self.session.flush(); return row
    async def get_current_context(self,project_id): return await self.session.scalar(select(StructuredContext).where(StructuredContext.project_id==project_id,StructuredContext.is_current.is_(True)).order_by(StructuredContext.created_at.desc()))
    async def get_context_by_workflow(self,workflow_id): return await self.session.scalar(select(StructuredContext).where(StructuredContext.workflow_id==workflow_id,StructuredContext.is_current.is_(True)))
