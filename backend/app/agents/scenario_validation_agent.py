from app.agents.base_agent import BaseAgent,ExecutionContext
from app.schemas.context_schema import StructuredContext
from app.schemas.scenario_schema import ScenarioBatch
from app.schemas.validation_schema import ValidationResult,ValidationIssue
from app.schemas.common import ValidationStatus,ScenarioType
from app.services.confidence_service import weighted_score,coverage,mapping_quality,content_quality,SCENARIO_WEIGHTS
from app.utils.similarity import duplicate_indexes
from app.utils.validators import item_id
class ScenarioValidationAgent(BaseAgent[ValidationResult]):
    output_model=ValidationResult
    async def run(self,input_data,execution_context:ExecutionContext)->ValidationResult:
        c=StructuredContext.model_validate(input_data["context"]); batch=ScenarioBatch.model_validate(input_data["scenarios"]); ss=batch.scenarios
        req=[item_id(x,"REQ",i) for i,x in enumerate(c.functional_requirements)]; ac=[item_id(x,"AC",i) for i,x in enumerate(c.acceptance_criteria)]
        duplicates=duplicate_indexes([s.title for s in ss]); types={s.scenario_type for s in ss}; complete=[s for s in ss if s.description and s.expected_business_outcome]
        vals={"requirement_coverage":coverage(req,[x for s in ss for x in s.requirement_ids]),"acceptance_criteria_coverage":coverage(ac,[x for s in ss for x in s.acceptance_criteria_ids]) if ac else 0.0,"traceability":sum(bool(s.user_story_ids) for s in ss)/len(ss) if ss else 0,"completeness":len(complete)/len(ss) if ss else 0,"consistency":0.0,"technical_feasibility":0.0,"duplicate_hallucination_control":1-len(duplicates)/len(ss) if ss else 0}
        missing={ScenarioType.positive,ScenarioType.negative,ScenarioType.boundary}-types; issues=[]
        if missing: issues.append(ValidationIssue(issue_code="MISSING_PATHS",description=f"Missing scenario types: {sorted(x.value for x in missing)}",recommendation="Generate only the missing path types"))
        for i in duplicates: issues.append(ValidationIssue(issue_code="DUPLICATE_SCENARIO",description="Scenario duplicates another scenario",affected_entity_id=ss[i].scenario_id,recommendation="Regenerate this scenario only"))
        labels={
            "requirement_coverage":"functional requirement coverage",
            "acceptance_criteria_coverage":"acceptance-criteria coverage",
            "traceability":"user-story traceability",
            "completeness":"scenario completeness",
        }
        entity_scores={}; entity_breakdowns=[]
        for i,s in enumerate(ss):
            req_quality=mapping_quality(req,s.requirement_ids); ac_quality=mapping_quality(ac,s.acceptance_criteria_ids) if ac else 0.0
            traceability=sum((req_quality,ac_quality,float(bool(s.user_story_ids))))/3
            completeness=sum((content_quality(s.description,120),content_quality(s.expected_business_outcome,80),float(bool(s.preconditions)),float(bool(s.test_data_requirements))))/4
            entity_vals={"requirement_coverage":req_quality,"acceptance_criteria_coverage":ac_quality,"traceability":traceability,"completeness":completeness,"consistency":sum((req_quality,ac_quality))/2,"technical_feasibility":sum((float(bool(s.preconditions)),float(bool(s.test_data_requirements))))/2,"duplicate_hallucination_control":float(i not in duplicates)}
            entity_breakdowns.append(entity_vals)
            entity_scores[str(s.scenario_id)]=weighted_score(entity_vals,SCENARIO_WEIGHTS)
        if entity_breakdowns:
            vals={key:round(sum(item[key] for item in entity_breakdowns)/len(entity_breakdowns),4) for key in SCENARIO_WEIGHTS}
        for metric,label in labels.items():
            if vals[metric] < 1:
                issues.append(ValidationIssue(
                    issue_code=f"LOW_{metric.upper()}",
                    description=f"Incomplete {label}: {round(vals[metric]*100)}%",
                    recommendation=f"Populate the missing {label} mappings",
                ))
        score=round(sum(entity_scores.values())/len(entity_scores),4) if entity_scores else 0.0
        return ValidationResult(confidence_score=score,score_breakdown=vals,entity_scores=entity_scores,status=ValidationStatus.passed if score>=.95 else ValidationStatus.failed,issues=issues,failed_entity_ids=[ss[i].scenario_id for i in duplicates],regeneration_instructions=[x.recommendation for x in issues if x.recommendation])
