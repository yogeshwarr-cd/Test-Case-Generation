import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.models.base import UUIDMixin, utcnow

class TraceabilityMixin:
    external_entity_id: Mapped[str] = mapped_column(String(255)); coverage_type: Mapped[str] = mapped_column(String(50), default="direct"); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
class ScenarioRequirementLink(UUIDMixin, TraceabilityMixin, Base):
    __tablename__="scenario_requirement_links"; scenario_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("test_scenarios.id"),index=True); requirement_type: Mapped[str]=mapped_column(String(50)); __table_args__=(UniqueConstraint("scenario_id","external_entity_id"),)
class ScenarioFeatureLink(UUIDMixin, TraceabilityMixin, Base):
    __tablename__="scenario_feature_links"; scenario_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("test_scenarios.id"),index=True); __table_args__=(UniqueConstraint("scenario_id","external_entity_id"),)
class ScenarioUserStoryLink(UUIDMixin, TraceabilityMixin, Base):
    __tablename__="scenario_user_story_links"; scenario_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("test_scenarios.id"),index=True); __table_args__=(UniqueConstraint("scenario_id","external_entity_id"),)
class ScenarioAcceptanceCriteriaLink(UUIDMixin, TraceabilityMixin, Base):
    __tablename__="scenario_acceptance_criteria_links"; scenario_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("test_scenarios.id"),index=True); __table_args__=(UniqueConstraint("scenario_id","external_entity_id"),)
class TestcaseRequirementLink(UUIDMixin, TraceabilityMixin, Base):
    __tablename__="testcase_requirement_links"; test_case_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("test_cases.id"),index=True); requirement_type: Mapped[str]=mapped_column(String(50)); __table_args__=(UniqueConstraint("test_case_id","external_entity_id"),)
class TestcaseAcceptanceCriteriaLink(UUIDMixin, TraceabilityMixin, Base):
    __tablename__="testcase_acceptance_criteria_links"; test_case_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True),ForeignKey("test_cases.id"),index=True); __table_args__=(UniqueConstraint("test_case_id","external_entity_id"),)
