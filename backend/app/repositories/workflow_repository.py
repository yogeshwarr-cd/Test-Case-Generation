from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.workflow import GenerationWorkflow
from app.repositories.base_repository import BaseRepository
class WorkflowRepository(BaseRepository[GenerationWorkflow]):
    def __init__(self, session: AsyncSession): super().__init__(session,GenerationWorkflow)
    async def create_workflow(self, **values): return await self.add(GenerationWorkflow(**values))
    async def get_workflow(self, workflow_id): return await self.get(workflow_id)
    async def _set(self,w,**values): [setattr(w,k,v) for k,v in values.items()]; await self.session.flush(); return w
    async def update_status(self,w,s): return await self._set(w,status=s)
    async def update_stage(self,w,s): return await self._set(w,current_stage=s)
    async def update_progress(self,w,p): return await self._set(w,progress_percentage=p)
    async def increment_scenario_attempt(self,w): return await self._set(w,scenario_attempt_count=w.scenario_attempt_count+1)
    async def increment_testcase_attempt(self,w): return await self._set(w,testcase_attempt_count=w.testcase_attempt_count+1)
    async def mark_completed(self,w): return await self._set(w,status="completed",progress_percentage=100,completed_at=datetime.now(timezone.utc))
    async def mark_failed(self,w,code=None,message=None): return await self._set(w,status="failed",error_code=code,error_message=message)
    async def mark_cancelled(self,w): return await self._set(w,status="cancelled",cancelled_at=datetime.now(timezone.utc))
