import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.models.base import UUIDMixin, utcnow

class Feedback(UUIDMixin, Base):
    __tablename__ = "feedback"
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True); entity_type: Mapped[str] = mapped_column(String(50)); entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True); version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True)); feedback_text: Mapped[str] = mapped_column(Text); feedback_type: Mapped[str] = mapped_column(String(50)); submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True)); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
class ApprovalHistory(UUIDMixin, Base):
    __tablename__ = "approval_history"
    entity_type: Mapped[str] = mapped_column(String(50)); entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True); version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True)); previous_status: Mapped[str | None] = mapped_column(String(50)); new_status: Mapped[str] = mapped_column(String(50), index=True); comments: Mapped[str | None] = mapped_column(Text); action_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True)); action_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"
    entity_type: Mapped[str] = mapped_column(String(50)); entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True)); action: Mapped[str] = mapped_column(String(100)); actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True)); details: Mapped[dict] = mapped_column(JSONB, default=dict); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
