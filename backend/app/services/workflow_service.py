import asyncio,uuid
from app.core.exceptions import WorkflowNotFound,ManualReviewRequired
from app.orchestrator.state import initial_state
from app.orchestrator.workflow import WorkflowOrchestrator
from app.services.input_service import DatabaseInputSource
from app.agents.base_agent import ExecutionContext
from app.agents.scenario_generation_agent import ScenarioGenerationAgent
from app.agents.scenario_validation_agent import ScenarioValidationAgent
from app.agents.testcase_generation_agent import TestCaseGenerationAgent
from app.agents.testcase_validation_agent import TestCaseValidationAgent
from app.orchestrator import nodes
class WorkflowService:
    """Coordinates agents; persistence adapters can subscribe to state transitions."""
    def __init__(self): self._states={};self._tasks={};self.orchestrator=WorkflowOrchestrator()
    async def start(self,request):
        project_id=request.project_id or uuid.uuid4()
        payload=(request.input_payload.model_dump() if request.input_payload else await DatabaseInputSource().load(project_id))
        workflow_id=uuid.uuid4(); state=initial_state(workflow_id,project_id,request.source_type.value,payload,request.mock_mode)
        self._states[workflow_id]=state; self._tasks[workflow_id]=asyncio.create_task(self._run(workflow_id)); return state
    async def _run(self,wid): self._states[wid]=await self.orchestrator.run(self._states[wid])
    def get(self,wid):
        if wid not in self._states: raise WorkflowNotFound("Workflow was not found")
        return self._states[wid]
    async def cancel(self,wid):
        state=self.get(wid); task=self._tasks.get(wid)
        if task and not task.done(): task.cancel()
        state["cancelled"]=True;state["status"]=state["current_stage"]="cancelled";return state
    async def resume(self,wid,request):
        state=self.get(wid)
        if state["status"] not in {"scenario_manual_review","testcase_manual_review"}: raise ManualReviewRequired("Workflow is not awaiting manual review")
        if request.corrected_data: state["input_payload"].update(request.corrected_data)
        state["manual_feedback"]=request.feedback
        if request.stage=="scenario_manual_review": state["scenario_attempt_count"]=0;state["current_stage"]="pending"
        else: state["testcase_attempt_count"]=0;state["current_stage"]="generating_test_cases"
        self._tasks[wid]=asyncio.create_task(self._run(wid)); return state
    def decide(self,wid,request):
        state=self.get(wid); key=f"{request.entity_type}:{request.entity_id}"
        state.setdefault("review_decisions",{})[key]=request.decision
        return {"status":"saved","entity_id":request.entity_id,"decision":request.decision}
    def decide_all(self,wid,request):
        state=self.get(wid); collection="scenarios" if request.entity_type=="scenario" else "test_cases"; id_key="scenario_id" if request.entity_type=="scenario" else "test_case_id"
        decisions=state.setdefault("review_decisions",{})
        for item in state.get(collection,[]): decisions[f"{request.entity_type}:{item[id_key]}"]=request.decision
        return {"status":"saved","count":len(state.get(collection,[])),"decision":request.decision}
    async def regenerate_entity(self,wid,request):
        state=self.get(wid); ctx=ExecutionContext(request_id=str(wid),workflow_id=str(wid),metadata={"mock_mode":state.get("mock_mode",False)})
        if request.entity_type=="scenario":
            index=next(i for i,x in enumerate(state["scenarios"]) if str(x["scenario_id"])==request.entity_id); original=state["scenarios"][index]
            payload={"context":state["structured_context"],"existing_scenarios":[original],"validation":{"regeneration_instructions":[request.feedback]}}
            generated=(await ScenarioGenerationAgent().execute(payload,ctx)).model_dump(mode="json")["scenarios"][0];generated["scenario_id"]=original["scenario_id"];state["scenarios"][index]=generated
            state["scenario_validation"]=(await ScenarioValidationAgent().execute({"context":state["structured_context"],"scenarios":{"scenarios":state["scenarios"]}},ctx)).model_dump(mode="json"); result=generated
        else:
            index=next(i for i,x in enumerate(state["test_cases"]) if str(x["test_case_id"])==request.entity_id); original=state["test_cases"][index]; related=[x for x in state["scenarios"] if str(x["scenario_id"])==str(original["scenario_id"])]
            payload={"scenarios":related,"context":state["structured_context"],"existing_test_cases":[original],"validation":{"regeneration_instructions":[request.feedback]}}
            generated=(await TestCaseGenerationAgent().execute(payload,ctx)).model_dump(mode="json")["test_cases"][0];generated["test_case_id"]=original["test_case_id"];generated["scenario_id"]=original["scenario_id"];state["test_cases"][index]=generated
            state["testcase_validation"]=(await TestCaseValidationAgent().execute({"scenarios":{"scenarios":state["scenarios"]},"test_cases":{"test_cases":state["test_cases"]}},ctx)).model_dump(mode="json"); result=generated
        return {"status":"completed","item":result,"result":{k:state.get(k) for k in ("scenarios","scenario_validation","test_cases","testcase_validation")}}
    async def approve_review(self,wid,request):
        state=self.get(wid)
        if request.stage=="scenario_manual_review":
            state["scenario_validation"]["status"]="passed";state["status"]=state["current_stage"]="generating_test_cases"
            self._tasks[wid]=asyncio.create_task(self._continue_after_scenario_approval(wid));return state
        state["testcase_validation"]["status"]="passed"
        state=await nodes.persist_results_node(state);state=await nodes.complete_workflow_node(state);self._states[wid]=state;return state
    async def _continue_after_scenario_approval(self,wid):
        state=self._states[wid]
        try:
            state=await nodes.generate_test_cases_node(state)
            while True:
                state=await nodes.validate_test_cases_node(state)
                if state["testcase_validation"].get("confidence_score",0)>=.95: state=await nodes.persist_results_node(state);state=await nodes.complete_workflow_node(state);break
                if state.get("testcase_attempt_count",0)>=3: state=await nodes.testcase_manual_review_node(state);break
                state=await nodes.regenerate_test_cases_node(state)
        except Exception as exc:
            state.setdefault("errors",[]).append({"stage":"testcase_generation","message":str(exc),"type":type(exc).__name__})
            state=await nodes.fail_workflow_node(state)
        self._states[wid]=state
workflow_service=WorkflowService()
