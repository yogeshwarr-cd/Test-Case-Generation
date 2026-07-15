PASS_THRESHOLD=.95; MAX_ATTEMPTS=3
def route_validation(validation:dict,attempt_count:int,passed_node:str,retry_node:str,manual_node:str)->str:
    if validation.get("confidence_score",0)>=PASS_THRESHOLD: return passed_node
    return manual_node if attempt_count>=MAX_ATTEMPTS else retry_node
def route_scenario_validation(state): return route_validation(state.get("scenario_validation",{}),state.get("scenario_attempt_count",0),"generate_test_cases","regenerate_scenarios","scenario_manual_review")
def route_testcase_validation(state): return route_validation(state.get("testcase_validation",{}),state.get("testcase_attempt_count",0),"persist_results","regenerate_test_cases","testcase_manual_review")
