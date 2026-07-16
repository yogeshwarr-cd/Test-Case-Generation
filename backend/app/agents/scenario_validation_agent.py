from app.agents.base_agent import BaseAgent,ExecutionContext
from app.schemas.context_schema import StructuredContext
from app.schemas.scenario_schema import ScenarioBatch
from app.schemas.validation_schema import ValidationResult,ValidationIssue
from app.schemas.common import ValidationStatus,ScenarioType
from app.services.confidence_service import weighted_score,coverage,SCENARIO_WEIGHTS
from app.utils.similarity import duplicate_indexes
from app.utils.validators import item_id
class ScenarioValidationAgent(BaseAgent[ValidationResult]):
    output_model=ValidationResult
    async def run(self,input_data,execution_context:ExecutionContext)->ValidationResult:
        c=StructuredContext.model_validate(input_data["context"]); batch=ScenarioBatch.model_validate(input_data["scenarios"]); ss=batch.scenarios
        req=[item_id(x,"REQ",i) for i,x in enumerate(c.functional_requirements)]; ac=[item_id(x,"AC",i) for i,x in enumerate(c.acceptance_criteria)]
        duplicates=duplicate_indexes([s.title for s in ss]); types={s.scenario_type for s in ss}; complete=[s for s in ss if s.description and s.expected_business_outcome]
        vals={"requirement_coverage":coverage(req,[x for s in ss for x in s.requirement_ids]),"acceptance_criteria_coverage":coverage(ac,[x for s in ss for x in s.acceptance_criteria_ids]),"traceability":sum(bool(s.user_story_ids) for s in ss)/len(ss) if ss else 0,"completeness":len(complete)/len(ss) if ss else 0,"consistency":1.0,"technical_feasibility":1.0,"duplicate_hallucination_control":1-len(duplicates)/len(ss) if ss else 0}
        missing={ScenarioType.positive,ScenarioType.negative,ScenarioType.boundary}-types; issues=[]
        if missing: issues.append(ValidationIssue(issue_code="MISSING_PATHS",description=f"Missing scenario types: {sorted(x.value for x in missing)}",recommendation="Generate only the missing path types"))
        for i in duplicates: issues.append(ValidationIssue(issue_code="DUPLICATE_SCENARIO",description="Scenario duplicates another scenario",affected_entity_id=ss[i].scenario_id,recommendation="Regenerate this scenario only"))
        labels={
            "requirement_coverage":"functional requirement coverage",
            "acceptance_criteria_coverage":"acceptance-criteria coverage",
            "traceability":"user-story traceability",
            "completeness":"scenario completeness",
        }
        for metric,label in labels.items():
            if vals[metric] < 1:
                issues.append(ValidationIssue(
                    issue_code=f"LOW_{metric.upper()}",
                    description=f"Incomplete {label}: {round(vals[metric]*100)}%",
                    recommendation=f"Populate the missing {label} mappings",
                ))
        score=weighted_score(vals,SCENARIO_WEIGHTS); return ValidationResult(confidence_score=score,score_breakdown=vals,status=ValidationStatus.passed if score>=.95 else ValidationStatus.failed,issues=issues,failed_entity_ids=[ss[i].scenario_id for i in duplicates],regeneration_instructions=[x.recommendation for x in issues if x.recommendation])
