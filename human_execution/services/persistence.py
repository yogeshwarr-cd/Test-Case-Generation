from __future__ import annotations

from app.database.session import AsyncSessionLocal, engine

from human_execution.database import HumanExecutionBase, HumanExecutionRepository
from human_execution.models import GeneratedHumanScript, HumanExecutionSession, RecordedAction


class HumanPersistence:
    async def initialize(self) -> None:
        async with engine.begin() as connection:
            await connection.run_sync(HumanExecutionBase.metadata.create_all)

    async def save_session(self, session: HumanExecutionSession) -> None:
        async with AsyncSessionLocal() as db:
            await HumanExecutionRepository(db).save_session(session)

    async def append_action(self, session_id: str, action: RecordedAction) -> None:
        async with AsyncSessionLocal() as db:
            await HumanExecutionRepository(db).append_action(session_id, action)

    async def save_scripts(
        self, session_id: str, scripts: list[GeneratedHumanScript]
    ) -> None:
        async with AsyncSessionLocal() as db:
            await HumanExecutionRepository(db).save_scripts(session_id, scripts)


class MemoryPersistence:
    """Test/local fallback implementing the same clean persistence interface."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.actions: dict[str, list[dict]] = {}
        self.scripts: dict[str, list[dict]] = {}

    async def initialize(self) -> None:
        return None

    async def save_session(self, session: HumanExecutionSession) -> None:
        self.sessions[session.session_id] = session.public()

    async def append_action(self, session_id: str, action: RecordedAction) -> None:
        self.actions.setdefault(session_id, []).append(
            action.redacted().model_dump(mode="json")
        )

    async def save_scripts(
        self, session_id: str, scripts: list[GeneratedHumanScript]
    ) -> None:
        self.scripts[session_id] = [
            item.model_dump(mode="json") for item in scripts
        ]

