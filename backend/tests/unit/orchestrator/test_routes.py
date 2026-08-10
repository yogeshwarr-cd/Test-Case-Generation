from app.orchestrator.routes import route_scenario_validation,route_testcase_validation,route_validation
def test_attempt_limit_routes_manual_review(): assert route_validation({"confidence_score":.8},3,"next","retry","manual",pass_threshold=.95,max_attempts=3)=="manual"
def test_passing_score_routes_forward(): assert route_validation({"confidence_score":.95},1,"next","retry","manual")=="next"
def test_workflow_threshold_controls_scenario_route():
    state={"scenario_validation":{"confidence_score":.82},"scenario_attempt_count":1,"confidence_threshold":.8}
    assert route_scenario_validation(state)=="generate_test_cases"
def test_workflow_threshold_controls_testcase_route():
    state={"testcase_validation":{"confidence_score":.82},"testcase_attempt_count":1,"confidence_threshold":.9}
    assert route_testcase_validation(state)=="regenerate_test_cases"
