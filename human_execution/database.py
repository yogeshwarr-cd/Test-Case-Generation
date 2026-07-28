from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .models import GeneratedHumanScript, HumanExecutionSession, RecordedAction, utcnow


class HumanExecutionBase(DeclarativeBase):
    """Separate metadata keeps this extension isolated from existing models."""


class HumanSessionRow(HumanExecutionBase):
    __tablename__ = "human_execution_sessions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    scenario_reference: Mapped[str] = mapped_column(String(200), index=True)
    test_case_reference: Mapped[str] = mapped_column(String(200), index=True)
    application_url: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(40), index=True)
    browser_status: Mapped[str] = mapped_column(String(100))
    generation_id: Mapped[str | None] = mapped_column(String(100))
    execution_id: Mapped[str | None] = mapped_column(String(100))
    comparison: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HumanActionRow(HumanExecutionBase):
    __tablename__ = "human_execution_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("human_execution_sessions.id"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HumanScriptRow(HumanExecutionBase):
    __tablename__ = "human_execution_scripts"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("human_execution_sessions.id"), index=True
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    scenario_reference: Mapped[str] = mapped_column(String(200), index=True)
    test_case_reference: Mapped[str] = mapped_column(String(200), index=True)
    source: Mapped[str] = mapped_column(Text)
    action_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HumanExecutionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_session(self, session: HumanExecutionSession) -> None:
        row = await self.db.get(HumanSessionRow, session.session_id)
        if row is None:
            row = HumanSessionRow(
                id=session.session_id,
                workflow_id=session.workflow_id,
                scenario_reference=session.scenario_id,
                test_case_reference=session.test_case_id,
                application_url=session.application_url,
                state=session.state.value,
                browser_status=session.browser_status,
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
            self.db.add(row)
        row.state = session.state.value
        row.browser_status = session.browser_status
        row.generation_id = session.generation_id
        row.execution_id = session.execution_id
        row.comparison = session.comparison
        row.error = session.error
        row.updated_at = session.updated_at
        await self.db.commit()

    async def append_action(self, session_id: str, action: RecordedAction) -> None:
        self.db.add(
            HumanActionRow(
                session_id=session_id,
                sequence=action.sequence,
                kind=action.kind.value,
                payload=action.redacted().model_dump(mode="json"),
            )
        )
        await self.db.commit()

    async def save_scripts(
        self, session_id: str, scripts: list[GeneratedHumanScript]
    ) -> None:
        for script in scripts:
            self.db.add(
                HumanScriptRow(
                    id=script.script_id,
                    session_id=session_id,
                    workflow_id=script.workflow_id,
                    scenario_reference=script.scenario_id,
                    test_case_reference=script.test_case_id,
                    source=script.source,
                    action_count=script.action_count,
                )
            )
        await self.db.commit()

    async def action_count(self, session_id: str) -> int:
        rows = await self.db.execute(
            select(HumanActionRow.id).where(HumanActionRow.session_id == session_id)
        )
        return len(rows.scalars().all())
