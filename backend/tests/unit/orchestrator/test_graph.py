from app.orchestrator.graph import LangGraphWorkflow, build_graph


def test_build_graph_uses_compiled_langgraph():
    workflow = build_graph()
    assert isinstance(workflow, LangGraphWorkflow)
    graph = workflow.compiled.get_graph()
    assert "generate_scenarios" in graph.nodes
    assert "validate_scenarios" in graph.nodes
    assert "generate_test_cases" in graph.nodes
    assert "validate_test_cases" in graph.nodes
