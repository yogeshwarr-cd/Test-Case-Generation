from sqlalchemy import select
from app.models.scenario import TestScenario,TestScenarioVersion
from app.models.traceability import ScenarioAcceptanceCriteriaLink,ScenarioFeatureLink,ScenarioRequirementLink,ScenarioUserStoryLink
class ScenarioRepository:
    def __init__(self,session): self.session=session
    async def create_scenario(self,**v): row=TestScenario(**v); self.session.add(row); await self.session.flush(); return row
    async def get_by_id(self,i,lock=False): return await self.session.scalar(select(TestScenario).where(TestScenario.id==i).with_for_update() if lock else select(TestScenario).where(TestScenario.id==i))
    async def create_scenario_version(self,scenario,**v): await self.get_by_id(scenario.id,True); row=TestScenarioVersion(scenario_id=scenario.id,version_number=scenario.current_version_number+1,**v); self.session.add(row); await self.session.flush(); return row
    async def update_current_version(self,s,v): s.current_version_id=v.id;s.current_version_number=v.version_number;await self.session.flush();return s
    async def list_by_project(self,i): return list((await self.session.scalars(select(TestScenario).where(TestScenario.project_id==i,TestScenario.is_active.is_(True)))).all())
    async def list_by_workflow(self,i): return list((await self.session.scalars(select(TestScenario).where(TestScenario.workflow_id==i,TestScenario.is_active.is_(True)))).all())
    async def get_current_version(self,s): return await self.session.get(TestScenarioVersion,s.current_version_id)
    async def list_versions(self,i): return list((await self.session.scalars(select(TestScenarioVersion).where(TestScenarioVersion.scenario_id==i).order_by(TestScenarioVersion.version_number.desc()))).all())
    async def save_traceability_links(self,i,links):
        mapping={"requirements":ScenarioRequirementLink,"features":ScenarioFeatureLink,"user_stories":ScenarioUserStoryLink,"acceptance_criteria":ScenarioAcceptanceCriteriaLink}; rows=[]
        for kind,model in mapping.items():
            for item in links.get(kind,[]): rows.append(model(scenario_id=i,external_entity_id=str(item),**({"requirement_type":"functional"} if kind=="requirements" else {})))
        self.session.add_all(rows); await self.session.flush(); return rows
    async def update_validation_status(self,s,v): s.validation_status=v;await self.session.flush()
    async def update_approval_status(self,s,v): s.approval_status=v;await self.session.flush()
    async def soft_delete(self,s): s.is_active=False;await self.session.flush()
