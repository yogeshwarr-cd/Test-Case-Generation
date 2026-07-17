from app.agents.base_agent import BaseAgent,ExecutionContext
from app.schemas.scenario_schema import ScenarioBatch
from app.schemas.testcase_schema import TestCaseBatch
from app.schemas.validation_schema import ValidationResult,ValidationIssue
from app.schemas.common import ValidationStatus
from app.services.confidence_service import weighted_score,coverage,mapping_quality,content_quality,TESTCASE_WEIGHTS
from app.utils.similarity import duplicate_indexes
class TestCaseValidationAgent(BaseAgent[ValidationResult]):
    output_model=ValidationResult
    async def run(self,input_data,execution_context:ExecutionContext)->ValidationResult:
        scenarios=ScenarioBatch.model_validate(input_data["scenarios"]).scenarios; cases=TestCaseBatch.model_validate(input_data["test_cases"]).test_cases
        sids={s.scenario_id for s in scenarios}; duplicates=duplicate_indexes([c.title for c in cases]); expected=sum(bool(st.expected_result.strip()) for c in cases for st in c.steps); steps=sum(len(c.steps) for c in cases)
        ac={x for s in scenarios for x in s.acceptance_criteria_ids}; vals={"scenario_coverage":coverage(sids,[c.scenario_id for c in cases]),"acceptance_criteria_coverage":coverage(ac,[x for c in cases for x in c.acceptance_criteria_ids]),"step_completeness":sum(bool(c.steps) for c in cases)/len(cases) if cases else 0,"expected_result_quality":expected/steps if steps else 0,"traceability":sum(c.scenario_id in sids for c in cases)/len(cases) if cases else 0,"consistency_accuracy":sum(c.scenario_id in sids for c in cases)/len(cases) if cases else 0,"duplicate_hallucination_control":1-len(duplicates)/len(cases) if cases else 0}
        issues=[ValidationIssue(issue_code="DUPLICATE_TESTCASE",description="Test case duplicates another",affected_entity_id=cases[i].test_case_id,recommendation="Regenerate this test case only") for i in duplicates]
        labels={"scenario_coverage":"scenario coverage","acceptance_criteria_coverage":"acceptance-criteria coverage","step_completeness":"step completeness","expected_result_quality":"expected-result quality","traceability":"scenario traceability"}
        for metric,label in labels.items():
            if vals[metric] < 1:
                issues.append(ValidationIssue(issue_code=f"LOW_{metric.upper()}",description=f"Incomplete {label}: {round(vals[metric]*100)}%",recommendation=f"Populate the missing {label} data"))
        entity_scores={}
        for i,c in enumerate(cases):
            scenario_quality=float(c.scenario_id in sids); ac_quality=mapping_quality(ac,c.acceptance_criteria_ids)
            step_quality=sum(content_quality(step.action,60) for step in c.steps)/len(c.steps) if c.steps else 0.0
            expected_quality=sum(content_quality(step.expected_result,80) for step in c.steps)/len(c.steps) if c.steps else 0.0
            traceability=sum((scenario_quality,ac_quality,float(bool(c.requirement_ids))))/3
            consistency=sum((scenario_quality,ac_quality,mapping_quality({x for s in scenarios for x in s.requirement_ids},c.requirement_ids)))/3
            entity_vals={"scenario_coverage":scenario_quality,"acceptance_criteria_coverage":ac_quality,"step_completeness":step_quality,"expected_result_quality":expected_quality,"traceability":traceability,"consistency_accuracy":consistency,"duplicate_hallucination_control":float(i not in duplicates)}
            entity_scores[str(c.test_case_id)]=weighted_score(entity_vals,TESTCASE_WEIGHTS)
        score=round(sum(entity_scores.values())/len(entity_scores),4) if entity_scores else 0.0
        return ValidationResult(confidence_score=score,score_breakdown=vals,entity_scores=entity_scores,status=ValidationStatus.passed if score>=.95 else ValidationStatus.failed,issues=issues,failed_entity_ids=[cases[i].test_case_id for i in duplicates],regeneration_instructions=[x.recommendation for x in issues if x.recommendation])
