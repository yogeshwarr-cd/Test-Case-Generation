from __future__ import annotations

import asyncio
import uuid
from typing import Any

from human_execution.models import (
    HumanExecutionSession,
    RecordedAction,
    SessionState,
    StartSessionRequest,
    utcnow,
)
from human_execution.services.browser_recorder import BrowserRecorder, HumanBrowserError
from human_execution.services.pipeline_adapter import ExistingPipelineAdapter
from human_execution.services.script_generator import (
    HumanScriptValidationError,
    generate_script,
)


class HumanSessionError(RuntimeError):
    pass


class HumanSessionNotFound(HumanSessionError):
    pass


class HumanExecutionService:
    def __init__(self, persistence: Any, pipeline: Any | None = None):
        self.persistence = persistence
        self.pipeline = pipeline or ExistingPipelineAdapter()
        self.sessions: dict[str, HumanExecutionSession] = {}
        self.recorders: dict[str, BrowserRecorder] = {}
        self.tasks: dict[str, asyncio.Task[Any]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    async def start(self, request: StartSessionRequest) -> HumanExecutionSession:
        session_id = f"human-{uuid.uuid4()}"
        session = HumanExecutionSession(
            session_id=session_id,
            workflow_id=request.workflow_id,
            scenario_id=request.scenario_id,
            test_case_id=request.test_case_id,
            application_url=str(request.application_url),
        )
        self.sessions[session_id] = session
        self._locks[session_id] = asyncio.Lock()
        await self.persistence.save_session(session)
        recorder = BrowserRecorder(
            session,
            lambda action: self._record(session_id, action),
            lambda status: self._browser_status(session_id, status),
        )
        self.recorders[session_id] = recorder
        self.tasks[session_id] = asyncio.create_task(self._launch(session_id))
        return session

    async def _launch(self, session_id: str) -> None:
        session = self.get(session_id)
        try:
            await self.recorders[session_id].launch()
            session.state = SessionState.recording
            session.browser_status = "open"
            await self._save(session)
        except Exception as exc:
            await self._fail(session, str(exc))

    async def _record(self, session_id: str, action: RecordedAction) -> None:
        session = self.get(session_id)
        if session.state != SessionState.recording:
            return
        has_locator = any(
            (
                action.test_id,
                action.label,
                action.role and action.accessible_name,
                action.placeholder,
                action.stable_id,
                action.stable_css,
                action.exact_text,
            )
        )
        if action.kind.value != "navigation" and not has_locator:
            return
        async with self._locks[session_id]:
            action.sequence = len(session.actions) + 1
            session.actions.append(action.redacted())
            session.recorded_action_count = len(session.actions)
            await self.persistence.append_action(session_id, action)
            await self._save(session)

    async def _browser_status(self, session_id: str, status: str) -> None:
        session = self.get(session_id)
        session.browser_status = status
        if "unexpectedly" in status.lower() and session.state == SessionState.recording:
            await self._fail(
                session, "The headed browser closed before recording was finished."
            )
        else:
            await self._save(session)

    async def finish(self, session_id: str) -> HumanExecutionSession:
        session = self.get(session_id)
        if session.state != SessionState.recording:
            raise HumanSessionError("Only a recording session can be finished.")
        recorder = self.recorders[session_id]
        if await recorder.authentication_incomplete():
            raise HumanSessionError(
                "Authentication is incomplete; finish login before ending the recording."
            )
        if not any(action.kind.value != "navigation" for action in session.actions):
            raise HumanSessionError("No executable actions were recorded.")
        session.state = SessionState.generating_scripts
        session.browser_status = "closing"
        await self._save(session)
        await recorder.close()
        session.browser_status = "closed"
        self.tasks[session_id] = asyncio.create_task(self._generate_scripts(session_id))
        return session

    async def _generate_scripts(self, session_id: str) -> None:
        session = self.get(session_id)
        try:
            script = generate_script(session)
            session.generated_scripts = [script]
            session.state = SessionState.validating_scripts
            await self._save(session)

            await self.persistence.save_scripts(session_id, [script])
            session.generation_id = await self.pipeline.store_generation(session, [script])
            session.state = SessionState.completed
            await self._save(session)
        except (HumanScriptValidationError, HumanBrowserError, Exception) as exc:
            await self._fail(session, str(exc))

    async def cancel(self, session_id: str) -> HumanExecutionSession:
        session = self.get(session_id)
        if session.state in {
            SessionState.completed,
            SessionState.failed,
            SessionState.cancelled,
        }:
            return session
        task = self.tasks.get(session_id)
        if task and not task.done():
            task.cancel()
        recorder = self.recorders.get(session_id)
        if recorder:
            await recorder.close()
        session.state = SessionState.cancelled
        session.browser_status = "closed"
        await self._save(session)
        return session

    def get(self, session_id: str) -> HumanExecutionSession:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise HumanSessionNotFound(f"Human execution session not found: {session_id}") from exc

    async def _fail(self, session: HumanExecutionSession, error: str) -> None:
        session.state = SessionState.failed
        session.error = error
        session.browser_status = "closed"
        recorder = self.recorders.get(session.session_id)
        if recorder:
            await recorder.close()
        await self._save(session)

    async def _save(self, session: HumanExecutionSession) -> None:
        session.updated_at = utcnow()
        await self.persistence.save_session(session)
