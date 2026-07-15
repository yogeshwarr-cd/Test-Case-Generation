import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.models.base import UUIDMixin, utcnow

class ValidationResult(UUIDMixin, Base):
    __tablename__ = "validation_results"
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_workflows.id"), index=True); entity_type: Mapped[str] = mapped_column(String(50)); entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True); validation_stage: Mapped[str] = mapped_column(String(80)); attempt_number: Mapped[int] = mapped_column(Integer); confidence_score: Mapped[Decimal] = mapped_column(Numeric(5,4)); score_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict); status: Mapped[str] = mapped_column(String(50), index=True); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
class ValidationIssue(UUIDMixin, Base):
    __tablename__ = "validation_issues"
    validation_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("validation_results.id")); issue_code: Mapped[str] = mapped_column(String(100)); severity: Mapped[str] = mapped_column(String(50)); description: Mapped[str] = mapped_column(Text); affected_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True)); recommendation: Mapped[str | None] = mapped_column(Text); resolved: Mapped[bool] = mapped_column(Boolean, default=False); resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
class RegenerationAttempt(UUIDMixin, Base):
    __tablename__ = "regeneration_attempts"
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_workflows.id"), index=True); entity_type: Mapped[str] = mapped_column(String(50)); entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True)); attempt_number: Mapped[int] = mapped_column(Integer); reason: Mapped[str] = mapped_column(Text); validation_feedback: Mapped[dict] = mapped_column(JSONB, default=dict); previous_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True)); generated_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True)); status: Mapped[str] = mapped_column(String(50), index=True); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
class ManualIntervention(UUIDMixin, Base):
    __tablename__ = "manual_interventions"
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_workflows.id"), index=True); stage: Mapped[str] = mapped_column(String(80)); reason: Mapped[str] = mapped_column(Text); missing_information: Mapped[dict] = mapped_column(JSONB, default=dict); feedback: Mapped[str | None] = mapped_column(Text); corrected_data: Mapped[dict | None] = mapped_column(JSONB); status: Mapped[str] = mapped_column(String(50), index=True); requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow); resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
