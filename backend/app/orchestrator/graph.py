from app.orchestrator import nodes,routes
class WorkflowGraph:
    async def ainvoke(self,state):
        try:
            for node in (nodes.load_input_node,nodes.prepare_context_node,nodes.generate_scenarios_node,nodes.validate_scenarios_node): state=await node(state)
            while routes.route_scenario_validation(state)=="regenerate_scenarios": state=await nodes.regenerate_scenarios_node(state);state=await nodes.validate_scenarios_node(state)
            if routes.route_scenario_validation(state)=="scenario_manual_review": return await nodes.scenario_manual_review_node(state)
            state=await nodes.generate_test_cases_node(state);state=await nodes.validate_test_cases_node(state)
            while routes.route_testcase_validation(state)=="regenerate_test_cases": state=await nodes.regenerate_test_cases_node(state);state=await nodes.validate_test_cases_node(state)
            if routes.route_testcase_validation(state)=="testcase_manual_review": return await nodes.testcase_manual_review_node(state)
            return await nodes.complete_workflow_node(await nodes.persist_results_node(state))
        except Exception as exc: state.setdefault("errors",[]).append(str(exc)); return await nodes.fail_workflow_node(state)
def build_graph(): return WorkflowGraph()
