import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.models.base import UUIDMixin, utcnow

class ProjectInput(UUIDMixin, Base):
    __tablename__ = "project_inputs"
    __table_args__ = (UniqueConstraint("project_id", "input_version"), Index("uq_project_inputs_current", "project_id", unique=True, postgresql_where=text("is_current")))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), index=True)
    input_version: Mapped[int] = mapped_column(Integer)
    source_type: Mapped[str] = mapped_column(String(50), default="manual")
    payload: Mapped[dict] = mapped_column(JSONB)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
