from datetime import datetime,timezone
from app.agents.base_agent import ExecutionContext
from app.agents.context_preparation_agent import ContextPreparationAgent
from app.agents.scenario_generation_agent import ScenarioGenerationAgent
from app.agents.scenario_validation_agent import ScenarioValidationAgent
from app.agents.testcase_generation_agent import TestCaseGenerationAgent
from app.agents.testcase_validation_agent import TestCaseValidationAgent
def _ctx(s): return ExecutionContext(request_id=str(s["workflow_id"]),workflow_id=str(s["workflow_id"]),metadata={"mock_mode":s.get("mock_mode",False)})
async def load_input_node(s): s["current_stage"]="load_input"; return s
async def prepare_context_node(s): s["status"]=s["current_stage"]="preparing_context"; s["structured_context"]=(await ContextPreparationAgent().execute({"project_id":s["project_id"],"source_type":s["source_type"],"input_payload":s["input_payload"]},_ctx(s))).model_dump(mode="json"); return s
async def generate_scenarios_node(s): s["status"]=s["current_stage"]="generating_scenarios"; s["scenario_attempt_count"]+=1; s["scenarios"]=(await ScenarioGenerationAgent().execute(s["structured_context"],_ctx(s))).model_dump(mode="json")["scenarios"]; return s
async def validate_scenarios_node(s): s["status"]=s["current_stage"]="validating_scenarios"; s["scenario_validation"]=(await ScenarioValidationAgent().execute({"context":s["structured_context"],"scenarios":{"scenarios":s["scenarios"]}},_ctx(s))).model_dump(mode="json"); return s
async def regenerate_scenarios_node(s):
    s["status"]=s["current_stage"]="generating_scenarios";s["scenario_attempt_count"]+=1
    payload={"context":s["structured_context"],"existing_scenarios":s["scenarios"],"validation":s["scenario_validation"]}
    s["scenarios"]=(await ScenarioGenerationAgent().execute(payload,_ctx(s))).model_dump(mode="json")["scenarios"]
    return s
async def scenario_manual_review_node(s): s["status"]=s["current_stage"]="scenario_manual_review"; s["manual_intervention_reason"]="Scenario confidence remained below 95% after three attempts"; return s
async def generate_test_cases_node(s): s["status"]=s["current_stage"]="generating_test_cases"; s["test_cases"]=(await TestCaseGenerationAgent().execute({"scenarios":s["scenarios"],"context":s["structured_context"]},_ctx(s))).model_dump(mode="json")["test_cases"]; return s
async def validate_test_cases_node(s): s["status"]=s["current_stage"]="validating_test_cases"; s["testcase_attempt_count"]+=1; s["testcase_validation"]=(await TestCaseValidationAgent().execute({"scenarios":{"scenarios":s["scenarios"]},"test_cases":{"test_cases":s["test_cases"]}},_ctx(s))).model_dump(mode="json"); return s
async def regenerate_test_cases_node(s):
    s["status"]=s["current_stage"]="generating_test_cases"
    payload={"scenarios":s["scenarios"],"context":s["structured_context"],"existing_test_cases":s["test_cases"],"validation":s["testcase_validation"]}
    s["test_cases"]=(await TestCaseGenerationAgent().execute(payload,_ctx(s))).model_dump(mode="json")["test_cases"]
    return s
async def testcase_manual_review_node(s): s["status"]=s["current_stage"]="testcase_manual_review"; s["manual_intervention_reason"]="Test-case confidence remained below 95% after three attempts"; return s
async def persist_results_node(s): s["current_stage"]="persist_results"; return s
async def complete_workflow_node(s): s["status"]=s["current_stage"]="completed"; s["completed_at"]=datetime.now(timezone.utc); return s
async def fail_workflow_node(s): s["status"]="failed";s["current_stage"]="failed";return s
