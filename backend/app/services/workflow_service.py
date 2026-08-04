import asyncio,json,uuid
from datetime import datetime,timezone
from pathlib import Path
from app.core.config import settings
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
from app.services.cache_service import cache
from app.services.document_service import document_service
class WorkflowService:
    """Coordinates agents; persistence adapters can subscribe to state transitions."""
    def __init__(self): self._states={};self._tasks={};self.orchestrator=WorkflowOrchestrator()
    @staticmethod
    def _state_path(wid):
        return Path(settings.automation_artifacts_path) / "workflows" / f"{wid}.json"
    def _persist_state(self,state):
        wid=state.get("workflow_id")
        if not wid:return
        path=self._state_path(wid);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(state,default=str,indent=2),encoding="utf-8")
    def _load_state(self,wid):
        path=self._state_path(wid)
        if not path.is_file():return None
        try:
            state=json.loads(path.read_text(encoding="utf-8"))
        except (OSError,ValueError,TypeError):return None
        state["workflow_id"]=uuid.UUID(str(state.get("workflow_id") or wid))
        if state.get("project_id"):state["project_id"]=uuid.UUID(str(state["project_id"]))
        return state
    async def start(self,request):
        project_id=request.project_id or uuid.uuid4()
        if request.document_session_id:
            payload=(await document_service.get(request.document_session_id))["input_payload"]
        else:
            payload=(request.input_payload.model_dump() if request.input_payload else await DatabaseInputSource().load(project_id))
        cache_key=cache.fingerprint("workflow",{"input":payload,"mock_mode":request.mock_mode,"confidence_threshold":request.confidence_threshold,"models":{"generation":settings.groq_generation_model or settings.groq_model,"regeneration":settings.groq_regeneration_model or settings.groq_model}})
        workflow_id=uuid.uuid4(); state=initial_state(workflow_id,project_id,request.source_type.value,payload,request.mock_mode,request.confidence_threshold);state["cache_key"]=cache_key;state["cache_hit"]=False
        cached=await cache.get_json(cache_key)
        if cached:
            state.update({key:cached.get(key,value) for key,value in {"structured_context":{},"scenarios":[],"scenario_validation":{},"test_cases":[],"testcase_validation":{}}.items()})
            for collection in ("scenarios","test_cases"):
                for item in state[collection]: item["project_id"]=str(project_id)
            state["status"]=state["current_stage"]="completed";state["completed_at"]=datetime.now(timezone.utc);state["cache_hit"]=True
            self._states[workflow_id]=state;self._persist_state(state);return state
        self._states[workflow_id]=state; self._tasks[workflow_id]=asyncio.create_task(self._run(workflow_id)); return state
    async def _run(self,wid):
        self._states[wid]=await self.orchestrator.run(self._states[wid])
        await self._cache_completed(self._states[wid])
    async def _cache_completed(self,state):
        if state.get("status")!="completed": return
        self._persist_state(state)
        if not state.get("cache_key"): return
        await cache.set_json(state["cache_key"],{"input_payload":state.get("input_payload",{}),"structured_context":state.get("structured_context",{}),"scenarios":state.get("scenarios",[]),"scenario_validation":state.get("scenario_validation",{}),"test_cases":state.get("test_cases",[]),"testcase_validation":state.get("testcase_validation",{})},settings.redis_workflow_ttl_seconds)
    def get(self,wid):
        if wid not in self._states:
            restored=self._load_state(wid)
            if restored is not None:self._states[wid]=restored
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
            index=next((i for i,x in enumerate(state.get("scenarios",[])) if str(x["scenario_id"])==request.entity_id),None)
            if index is None: raise ValueError(f"Scenario {request.entity_id} was not found in this workflow")
            original=state["scenarios"][index]
            payload={"context":state["structured_context"],"existing_scenarios":[original],"validation":{"regeneration_instructions":[request.feedback]}}
            generated=(await ScenarioGenerationAgent().execute(payload,ctx)).model_dump(mode="json")["scenarios"][0];generated["scenario_id"]=original["scenario_id"];state["scenarios"][index]=generated
            state["scenario_validation"]=(await ScenarioValidationAgent().execute({"context":state["structured_context"],"scenarios":{"scenarios":state["scenarios"]},"confidence_threshold":state.get("confidence_threshold",settings.validation_pass_threshold)},ctx)).model_dump(mode="json"); result=generated
        else:
            index=next((i for i,x in enumerate(state.get("test_cases",[])) if str(x["test_case_id"])==request.entity_id),None)
            if index is None: raise ValueError(f"Test case {request.entity_id} was not found in this workflow")
            original=state["test_cases"][index]; related=[x for x in state["scenarios"] if str(x["scenario_id"])==str(original["scenario_id"])]
            payload={"scenarios":related,"context":state["structured_context"],"existing_test_cases":[original],"validation":{"regeneration_instructions":[request.feedback]}}
            generated=(await TestCaseGenerationAgent().execute(payload,ctx)).model_dump(mode="json")["test_cases"][0];generated["test_case_id"]=original["test_case_id"];generated["scenario_id"]=original["scenario_id"];state["test_cases"][index]=generated
            state["testcase_validation"]=(await TestCaseValidationAgent().execute({"scenarios":{"scenarios":state["scenarios"]},"test_cases":{"test_cases":state["test_cases"]},"confidence_threshold":state.get("confidence_threshold",settings.validation_pass_threshold)},ctx)).model_dump(mode="json"); result=generated
        state.setdefault("regeneration_history",[]).append({"entity_type":request.entity_type,"entity_id":request.entity_id,"feedback":request.feedback,"regenerated_at":datetime.now(timezone.utc).isoformat()})
        self._persist_state(state)
        return {"status":"completed","item":result,"result":{k:state.get(k) for k in ("scenarios","scenario_validation","test_cases","testcase_validation")}}
    async def approve_review(self,wid,request):
        state=self.get(wid)
        if state["status"] != request.stage or request.stage not in {"scenario_manual_review","testcase_manual_review"}:
            raise ManualReviewRequired("Workflow is not awaiting approval for this review stage")
        if request.stage=="scenario_manual_review":
            decisions=state.setdefault("review_decisions",{})
            for item in state.get("scenarios",[]): decisions[f"scenario:{item['scenario_id']}"]="approved"
            state["scenario_validation"]["status"]="passed";state["status"]=state["current_stage"]="generating_test_cases"
            self._tasks[wid]=asyncio.create_task(self._continue_after_scenario_approval(wid));return state
        decisions=state.setdefault("review_decisions",{})
        for item in state.get("test_cases",[]): decisions[f"testCase:{item['test_case_id']}"]="approved"
        state["testcase_validation"]["status"]="passed"
        state=await nodes.persist_results_node(state);state=await nodes.complete_workflow_node(state);self._states[wid]=state;await self._cache_completed(state);return state
    async def _continue_after_scenario_approval(self,wid):
        state=self._states[wid]
        try:
            state=await nodes.generate_test_cases_node(state)
            while True:
                state=await nodes.validate_test_cases_node(state)
                if state["testcase_validation"].get("confidence_score",0)>=state.get("confidence_threshold",settings.validation_pass_threshold): state=await nodes.persist_results_node(state);state=await nodes.complete_workflow_node(state);break
                if state.get("testcase_attempt_count",0)>=settings.max_validation_attempts: state=await nodes.testcase_manual_review_node(state);break
                state=await nodes.regenerate_test_cases_node(state)
        except Exception as exc:
            state.setdefault("errors",[]).append({"stage":"testcase_generation","message":str(exc),"type":type(exc).__name__})
            state=await nodes.fail_workflow_node(state)
        self._states[wid]=state
        await self._cache_completed(state)
workflow_service=WorkflowService()
