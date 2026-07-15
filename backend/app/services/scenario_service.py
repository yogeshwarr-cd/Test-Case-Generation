from app.core.exceptions import ScenarioNotFound,VersionConflict
from app.models.feedback import ApprovalHistory
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.scenario_repository import ScenarioRepository
class ScenarioService:
    def __init__(self,s): self.s=s;self.r=ScenarioRepository(s);self.f=FeedbackRepository(s)
    async def get(self,i):
        x=await self.r.get_by_id(i)
        if not x or not x.is_active: raise ScenarioNotFound("Scenario was not found")
        return x
    async def edit(self,i,d):
        x=await self.get(i);v=await self.r.create_scenario_version(x,title=d.title,description=d.description,scenario_type=d.type,priority=d.priority,preconditions=d.preconditions,test_data_requirements=d.test_data if isinstance(d.test_data,list) else [],expected_business_outcome=d.expected_business_outcome,payload=d.model_dump(),generation_reason="manual_edit",created_by_type="user");await self.r.update_current_version(x,v);await self.s.commit();return x
    async def feedback(self,x,text,user=None): row=await self.f.create_feedback(project_id=x.project_id,entity_type="scenario",entity_id=x.id,version_id=x.current_version_id,feedback_text=text,feedback_type="manual",submitted_by=user);await self.s.commit();return row
    async def approval(self,i,body,status):
        x=await self.get(i)
        if body.version_id!=x.current_version_id: raise VersionConflict("Approval must target the current version")
        self.s.add(ApprovalHistory(entity_type="scenario",entity_id=x.id,version_id=body.version_id,previous_status=x.approval_status,new_status=status,comments=body.comments,action_by=body.action_by));await self.r.update_approval_status(x,status);await self.s.commit();return x
