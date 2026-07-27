from app.orchestrator.routes import route_validation
def test_attempt_limit_routes_manual_review(): assert route_validation({"confidence_score":.8},3,"next","retry","manual",pass_threshold=.95,max_attempts=3)=="manual"
def test_passing_score_routes_forward(): assert route_validation({"confidence_score":.95},1,"next","retry","manual")=="next"
