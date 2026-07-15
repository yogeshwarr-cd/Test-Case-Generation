from langgraph.graph import END, START, StateGraph

from app.core.exceptions import AppError
from app.orchestrator import nodes, routes
from app.orchestrator.state import WorkflowState


class LangGraphWorkflow:
    """Runs the existing workflow nodes through a compiled LangGraph graph."""

    def __init__(self):
        builder = StateGraph(WorkflowState)
        builder.add_node("load_input", nodes.load_input_node)
        builder.add_node("prepare_context", nodes.prepare_context_node)
        builder.add_node("generate_scenarios", nodes.generate_scenarios_node)
        builder.add_node("validate_scenarios", nodes.validate_scenarios_node)
        builder.add_node("regenerate_scenarios", nodes.regenerate_scenarios_node)
        builder.add_node("scenario_manual_review", nodes.scenario_manual_review_node)
        builder.add_node("generate_test_cases", nodes.generate_test_cases_node)
        builder.add_node("validate_test_cases", nodes.validate_test_cases_node)
        builder.add_node("regenerate_test_cases", nodes.regenerate_test_cases_node)
        builder.add_node("testcase_manual_review", nodes.testcase_manual_review_node)
        builder.add_node("persist_results", nodes.persist_results_node)
        builder.add_node("complete_workflow", nodes.complete_workflow_node)

        builder.add_edge(START, "load_input")
        builder.add_edge("load_input", "prepare_context")
        builder.add_edge("prepare_context", "generate_scenarios")
        builder.add_edge("generate_scenarios", "validate_scenarios")
        builder.add_conditional_edges(
            "validate_scenarios",
            routes.route_scenario_validation,
            {
                "generate_test_cases": "generate_test_cases",
                "regenerate_scenarios": "regenerate_scenarios",
                "scenario_manual_review": "scenario_manual_review",
            },
        )
        builder.add_edge("regenerate_scenarios", "validate_scenarios")
        builder.add_edge("scenario_manual_review", END)
        builder.add_edge("generate_test_cases", "validate_test_cases")
        builder.add_conditional_edges(
            "validate_test_cases",
            routes.route_testcase_validation,
            {
                "persist_results": "persist_results",
                "regenerate_test_cases": "regenerate_test_cases",
                "testcase_manual_review": "testcase_manual_review",
            },
        )
        builder.add_edge("regenerate_test_cases", "validate_test_cases")
        builder.add_edge("testcase_manual_review", END)
        builder.add_edge("persist_results", "complete_workflow")
        builder.add_edge("complete_workflow", END)
        self.compiled = builder.compile()

    async def ainvoke(self, state: WorkflowState) -> WorkflowState:
        try:
            return await self.compiled.ainvoke(state)
        except Exception as exc:
            message = (
                f"{exc.error_code}: {exc.message}" if isinstance(exc, AppError) else str(exc)
            )
            state.setdefault("errors", []).append(message)
            return await nodes.fail_workflow_node(state)


def build_graph() -> LangGraphWorkflow:
    return LangGraphWorkflow()
