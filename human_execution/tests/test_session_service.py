import asyncio
import uuid

import pytest

from human_execution.models import (
    ActionKind,
    RecordedAction,
    SessionState,
    StartSessionRequest,
)
from human_execution.services.persistence import MemoryPersistence
from human_execution.services.session_service import HumanExecutionService, HumanSessionError


class FakeReport:
    execution_id = "exec-1"


class FakePipeline:
    def __init__(self):
        self.stored = []

    async def store_generation(self, session, scripts):
        self.stored.extend(scripts)
        return "human-gen-1"

    async def execute_and_compare(self, generation_id):
        assert generation_id == "human-gen-1"
        return FakeReport(), {"comparison_id": "compare-1"}


class FakeRecorder:
    def __init__(self, incomplete=False):
        self.incomplete = incomplete
        self.closed = False

    async def authentication_incomplete(self):
        return self.incomplete

    async def close(self):
        self.closed = True


def request():
    return StartSessionRequest(
        workflow_id=uuid.uuid4(),
        scenario_id="SC-1",
        test_case_id="TC-1",
        application_url="https://example.com/app",
    )


@pytest.mark.asyncio
async def test_record_finish_generates_and_stores_for_existing_execution_flow():
    persistence = MemoryPersistence()
    pipeline = FakePipeline()
    service = HumanExecutionService(persistence, pipeline)
    payload = request()
    session = service.sessions["session-1"] = __import__(
        "human_execution.models", fromlist=["HumanExecutionSession"]
    ).HumanExecutionSession(
        session_id="session-1",
        workflow_id=payload.workflow_id,
        scenario_id=payload.scenario_id,
        test_case_id=payload.test_case_id,
        application_url=str(payload.application_url),
        state=SessionState.recording,
        browser_status="open",
    )
    service._locks[session.session_id] = asyncio.Lock()
    service.recorders[session.session_id] = FakeRecorder()

    await service._record(
        session.session_id,
        RecordedAction(
            kind=ActionKind.click,
            page_url="https://example.com/app",
            role="button",
            accessible_name="Save",
            test_id="save",
        ),
    )
    await service.finish(session.session_id)
    await service.tasks[session.session_id]

    assert session.state == SessionState.completed
    assert session.recorded_action_count == 1
    assert session.generation_id == "human-gen-1"
    assert session.execution_id is None
    assert pipeline.stored


@pytest.mark.asyncio
async def test_finish_rejects_incomplete_authentication():
    persistence = MemoryPersistence()
    service = HumanExecutionService(persistence, FakePipeline())
    payload = request()
    session = service.sessions["session-2"] = __import__(
        "human_execution.models", fromlist=["HumanExecutionSession"]
    ).HumanExecutionSession(
        session_id="session-2",
        workflow_id=payload.workflow_id,
        scenario_id=payload.scenario_id,
        test_case_id=payload.test_case_id,
        application_url=str(payload.application_url),
        state=SessionState.recording,
    )
    service.recorders[session.session_id] = FakeRecorder(incomplete=True)
    with pytest.raises(HumanSessionError, match="Authentication is incomplete"):
        await service.finish(session.session_id)


@pytest.mark.asyncio
async def test_password_is_redacted_before_persistence():
    persistence = MemoryPersistence()
    service = HumanExecutionService(persistence, FakePipeline())
    payload = request()
    session = service.sessions["session-3"] = __import__(
        "human_execution.models", fromlist=["HumanExecutionSession"]
    ).HumanExecutionSession(
        session_id="session-3",
        workflow_id=payload.workflow_id,
        scenario_id=payload.scenario_id,
        test_case_id=payload.test_case_id,
        application_url=str(payload.application_url),
        state=SessionState.recording,
    )
    service._locks[session.session_id] = asyncio.Lock()
    await service._record(
        session.session_id,
        RecordedAction(
            kind=ActionKind.fill,
            page_url="https://example.com/login",
            role="textbox",
            label="Password",
            input_value="never-store-this",
        ),
    )
    assert session.actions[0].input_value == "<REDACTED>"
    assert persistence.actions[session.session_id][0]["input_value"] == "<REDACTED>"
