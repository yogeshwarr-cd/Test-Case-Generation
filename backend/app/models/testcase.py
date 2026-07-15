import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.models.base import TimestampMixin, UUIDMixin, utcnow

class TestCase(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "test_cases"; __table_args__ = (UniqueConstraint("project_id", "test_case_code"), CheckConstraint("confidence_score BETWEEN 0 AND 1", name="confidence_range"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True); workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_workflows.id"), index=True); scenario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("test_scenarios.id"), index=True)
    test_case_code: Mapped[str] = mapped_column(String(100)); current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True)); current_version_number: Mapped[int] = mapped_column(Integer, default=0); validation_status: Mapped[str] = mapped_column(String(50), default="pending", index=True); approval_status: Mapped[str] = mapped_column(String(50), default="pending", index=True); confidence_score: Mapped[Decimal] = mapped_column(Numeric(5,4), default=0); automation_candidate: Mapped[bool] = mapped_column(Boolean, default=False); is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class TestCaseVersion(UUIDMixin, Base):
    __tablename__ = "test_case_versions"; __table_args__ = (UniqueConstraint("test_case_id", "version_number"),)
    test_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("test_cases.id"), index=True); version_number: Mapped[int] = mapped_column(Integer); title: Mapped[str] = mapped_column(String(255)); description: Mapped[str] = mapped_column(Text); test_case_type: Mapped[str] = mapped_column(String(50)); priority: Mapped[str] = mapped_column(String(50)); preconditions: Mapped[list] = mapped_column(JSONB, default=list); test_data: Mapped[dict] = mapped_column(JSONB, default=dict); postconditions: Mapped[list] = mapped_column(JSONB, default=list); payload: Mapped[dict] = mapped_column(JSONB, default=dict); generation_reason: Mapped[str] = mapped_column(String(100)); feedback_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True)); created_by_type: Mapped[str] = mapped_column(String(50)); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

class TestCaseStep(UUIDMixin, Base):
    __tablename__ = "test_case_steps"; __table_args__ = (UniqueConstraint("test_case_version_id", "step_number"),)
    test_case_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("test_case_versions.id"), index=True); step_number: Mapped[int] = mapped_column(Integer); action: Mapped[str] = mapped_column(Text); expected_result: Mapped[str] = mapped_column(Text); test_data: Mapped[dict | None] = mapped_column(JSONB); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
