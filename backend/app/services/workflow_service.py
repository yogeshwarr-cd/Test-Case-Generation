import asyncio,uuid
from app.core.exceptions import WorkflowNotFound,ManualReviewRequired
from app.orchestrator.state import initial_state
from app.orchestrator.workflow import WorkflowOrchestrator
from app.services.input_service import DatabaseInputSource
class WorkflowService:
    """Coordinates agents; persistence adapters can subscribe to state transitions."""
    def __init__(self): self._states={};self._tasks={};self.orchestrator=WorkflowOrchestrator()
    async def start(self,request):
        project_id=request.project_id or uuid.uuid4()
        payload=(request.input_payload.model_dump() if request.input_payload else await DatabaseInputSource().load(project_id))
        workflow_id=uuid.uuid4(); state=initial_state(workflow_id,project_id,request.source_type.value,payload)
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
workflow_service=WorkflowService()
