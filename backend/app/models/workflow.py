import uuid
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.models.base import TimestampMixin, UUIDMixin, utcnow

class GenerationWorkflow(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "generation_workflows"
    __table_args__ = (CheckConstraint("scenario_attempt_count BETWEEN 0 AND 3", name="scenario_attempt_range"), CheckConstraint("testcase_attempt_count BETWEEN 0 AND 3", name="testcase_attempt_range"), CheckConstraint("progress_percentage BETWEEN 0 AND 100", name="progress_range"))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True); input_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("project_inputs.id"))
    source_type: Mapped[str] = mapped_column(String(50), default="manual"); current_stage: Mapped[str] = mapped_column(String(80), default="pending")
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True); scenario_attempt_count: Mapped[int] = mapped_column(Integer, default=0); testcase_attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    progress_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0); error_code: Mapped[str | None] = mapped_column(String(100)); error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class StructuredContext(UUIDMixin, Base):
    __tablename__ = "structured_contexts"; __table_args__ = (UniqueConstraint("workflow_id", "context_version"),)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_workflows.id"), index=True); project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True)
    context_version: Mapped[int] = mapped_column(Integer); payload: Mapped[dict] = mapped_column(JSONB); traceability_map: Mapped[dict] = mapped_column(JSONB, default=dict); source_type: Mapped[str] = mapped_column(String(50)); is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

class AgentExecution(UUIDMixin, Base):
    __tablename__ = "agent_executions"
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_workflows.id"), index=True); agent_name: Mapped[str] = mapped_column(String(100)); execution_number: Mapped[int] = mapped_column(Integer); status: Mapped[str] = mapped_column(String(50), index=True)
    input_snapshot: Mapped[dict | None] = mapped_column(JSONB); output_snapshot: Mapped[dict | None] = mapped_column(JSONB); provider: Mapped[str | None] = mapped_column(String(100)); model_name: Mapped[str | None] = mapped_column(String(100)); token_usage: Mapped[dict | None] = mapped_column(JSONB); latency_ms: Mapped[int | None]; error_details: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow); completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
