from collections.abc import Iterable
def weighted_score(values:dict[str,float],weights:dict[str,float])->float:
    return max(0.0,min(1.0,round(sum(max(0,min(1,values.get(k,0)))*w for k,w in weights.items()),4)))
SCENARIO_WEIGHTS={"requirement_coverage":.25,"acceptance_criteria_coverage":.20,"traceability":.15,"completeness":.15,"consistency":.10,"technical_feasibility":.10,"duplicate_hallucination_control":.05}
TESTCASE_WEIGHTS={"scenario_coverage":.25,"acceptance_criteria_coverage":.20,"step_completeness":.15,"expected_result_quality":.15,"traceability":.10,"consistency_accuracy":.10,"duplicate_hallucination_control":.05}
def coverage(required:Iterable[str],covered:Iterable[str])->float:
    required=set(required); return 1.0 if not required else len(required&set(covered))/len(required)
