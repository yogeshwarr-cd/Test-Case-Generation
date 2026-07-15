from sqlalchemy import select
from app.models.feedback import Feedback
class FeedbackRepository:
    def __init__(self,session): self.session=session
    async def create_feedback(self,**values): row=Feedback(**values); self.session.add(row); await self.session.flush(); return row
    async def list_feedback(self,entity_id): return list((await self.session.scalars(select(Feedback).where(Feedback.entity_id==entity_id).order_by(Feedback.created_at.desc()))).all())
    async def get_feedback_for_version(self,version_id): return list((await self.session.scalars(select(Feedback).where(Feedback.version_id==version_id))).all())
