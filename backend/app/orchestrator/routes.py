from app.core.config import settings

def route_validation(
    validation: dict,
    attempt_count: int,
    passed_node: str,
    retry_node: str,
    manual_node: str,
    pass_threshold: float | None = None,
    max_attempts: int | None = None,
) -> str:
    threshold = settings.validation_pass_threshold if pass_threshold is None else pass_threshold
    limit = settings.max_validation_attempts if max_attempts is None else max_attempts
    if validation.get("confidence_score", 0) >= threshold:
        return passed_node
    return manual_node if attempt_count >= limit else retry_node

def route_scenario_validation(state):
    return route_validation(
        state.get("scenario_validation", {}),
        state.get("scenario_attempt_count", 0),
        "generate_test_cases",
        "regenerate_scenarios",
        "scenario_manual_review",
        pass_threshold=state.get("confidence_threshold", settings.validation_pass_threshold),
    )

def route_testcase_validation(state):
    return route_validation(
        state.get("testcase_validation", {}),
        state.get("testcase_attempt_count", 0),
        "persist_results",
        "regenerate_test_cases",
        "testcase_manual_review",
        pass_threshold=state.get("confidence_threshold", settings.validation_pass_threshold),
    )
