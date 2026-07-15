from app.core.exceptions import InvalidApprovalAction,TestCaseNotFound,VersionConflict
from app.models.feedback import ApprovalHistory
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.testcase_repository import TestCaseRepository
class TestCaseService:
    def __init__(self,s): self.s=s;self.r=TestCaseRepository(s);self.f=FeedbackRepository(s)
    async def get(self,i):
        x=await self.r.get_by_id(i)
        if not x or not x.is_active: raise TestCaseNotFound("Test case was not found")
        return x
    async def edit(self,i,d):
        try:
            x=await self.get(i);v=await self.r.create_testcase_version(x,title=d.title,description=d.description,test_case_type=d.type,priority=d.priority,preconditions=d.preconditions,test_data=d.test_data if isinstance(d.test_data,dict) else {},postconditions=d.postconditions,payload=d.model_dump(mode="json"),generation_reason="manual_edit",created_by_type="user");await self.r.create_steps(v,d.steps);await self.r.save_traceability_links(x.id,d.traceability);await self.r.update_current_version(x,v);await self.s.commit();return x
        except Exception:
            await self.s.rollback();raise
    async def feedback(self,x,text,user=None): row=await self.f.create_feedback(project_id=x.project_id,entity_type="testcase",entity_id=x.id,version_id=x.current_version_id,feedback_text=text,feedback_type="manual",submitted_by=user);await self.s.commit();return row
    async def approval(self,i,body,status):
        if status not in {"approved","rejected"}: raise InvalidApprovalAction("Unsupported approval action")
        x=await self.get(i)
        if body.version_id!=x.current_version_id: raise VersionConflict("Approval must target the current version")
        self.s.add(ApprovalHistory(entity_type="testcase",entity_id=x.id,version_id=body.version_id,previous_status=x.approval_status,new_status=status,comments=body.comments,action_by=body.action_by));await self.r.update_approval_status(x,status);await self.s.commit();return x
