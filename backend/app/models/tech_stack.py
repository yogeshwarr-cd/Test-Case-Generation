import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.models.base import UUIDMixin, utcnow

class TechStack(UUIDMixin, Base):
    __tablename__ = "tech_stacks"
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True)
    input_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("project_inputs.id"))
    frontend: Mapped[dict] = mapped_column(JSONB, default=dict); backend: Mapped[dict] = mapped_column(JSONB, default=dict)
    database: Mapped[dict] = mapped_column(JSONB, default=dict); infrastructure: Mapped[dict] = mapped_column(JSONB, default=dict)
    integrations: Mapped[dict] = mapped_column(JSONB, default=dict); testing_tools: Mapped[dict] = mapped_column(JSONB, default=dict)
    raw_content: Mapped[str | None] = mapped_column(Text); is_structured: Mapped[bool] = mapped_column(Boolean, default=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1); is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
