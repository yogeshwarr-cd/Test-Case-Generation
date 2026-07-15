from datetime import datetime,timezone
from sqlalchemy import select
from app.models.validation import ValidationIssue,ValidationResult
class ValidationRepository:
    def __init__(self,session): self.session=session
    async def create_validation_result(self,**values): row=ValidationResult(**values); self.session.add(row); await self.session.flush(); return row
    async def create_validation_issues(self,result_id,issues): rows=[ValidationIssue(validation_result_id=result_id,**i) for i in issues]; self.session.add_all(rows); await self.session.flush(); return rows
    async def list_by_workflow(self,workflow_id): return list((await self.session.scalars(select(ValidationResult).where(ValidationResult.workflow_id==workflow_id).order_by(ValidationResult.created_at.desc()))).all())
    async def get_latest_for_entity(self,entity_id): return await self.session.scalar(select(ValidationResult).where(ValidationResult.entity_id==entity_id).order_by(ValidationResult.created_at.desc()).limit(1))
    async def resolve_issue(self,issue_id): row=await self.session.get(ValidationIssue,issue_id); row.resolved=True; row.resolved_at=datetime.now(timezone.utc); await self.session.flush(); return row
