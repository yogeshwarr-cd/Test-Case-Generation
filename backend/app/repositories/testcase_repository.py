from sqlalchemy import select
from app.models.testcase import TestCase,TestCaseStep,TestCaseVersion
from app.models.traceability import TestcaseAcceptanceCriteriaLink,TestcaseRequirementLink
class TestCaseRepository:
    def __init__(self,session): self.session=session
    async def create_testcase(self,**v): row=TestCase(**v);self.session.add(row);await self.session.flush();return row
    async def get_by_id(self,i,lock=False): return await self.session.scalar(select(TestCase).where(TestCase.id==i).with_for_update() if lock else select(TestCase).where(TestCase.id==i))
    async def create_testcase_version(self,t,**v): await self.get_by_id(t.id,True);row=TestCaseVersion(test_case_id=t.id,version_number=t.current_version_number+1,**v);self.session.add(row);await self.session.flush();return row
    async def create_steps(self,v,steps): rows=[TestCaseStep(test_case_version_id=v.id,step_number=n+1,**s) for n,s in enumerate(steps)];self.session.add_all(rows);await self.session.flush();return rows
    async def update_current_version(self,t,v): t.current_version_id=v.id;t.current_version_number=v.version_number;await self.session.flush();return t
    async def list_by_project(self,i): return list((await self.session.scalars(select(TestCase).where(TestCase.project_id==i,TestCase.is_active.is_(True)))).all())
    async def list_by_workflow(self,i): return list((await self.session.scalars(select(TestCase).where(TestCase.workflow_id==i,TestCase.is_active.is_(True)))).all())
    async def get_current_version(self,t): return await self.session.get(TestCaseVersion,t.current_version_id)
    async def list_versions(self,i): return list((await self.session.scalars(select(TestCaseVersion).where(TestCaseVersion.test_case_id==i).order_by(TestCaseVersion.version_number.desc()))).all())
    async def save_traceability_links(self,i,links): rows=[TestcaseRequirementLink(test_case_id=i,external_entity_id=str(x),requirement_type="functional") for x in links.get("requirements",[])]+[TestcaseAcceptanceCriteriaLink(test_case_id=i,external_entity_id=str(x)) for x in links.get("acceptance_criteria",[])];self.session.add_all(rows);await self.session.flush();return rows
    async def update_validation_status(self,t,v): t.validation_status=v;await self.session.flush()
    async def update_approval_status(self,t,v): t.approval_status=v;await self.session.flush()
    async def soft_delete(self,t): t.is_active=False;await self.session.flush()
