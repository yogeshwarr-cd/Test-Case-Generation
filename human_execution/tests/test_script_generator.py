import uuid

import pytest

from human_execution.models import (
    ActionKind,
    HumanExecutionSession,
    RecordedAction,
    SessionState,
)
from human_execution.services.script_generator import (
    HumanScriptValidationError,
    generate_script,
    same_origin,
)


def session_with(*actions: RecordedAction) -> HumanExecutionSession:
    return HumanExecutionSession(
        session_id="session-1",
        workflow_id=uuid.uuid4(),
        scenario_id="SC-1",
        test_case_id="TC-1",
        application_url="https://example.com/app",
        state=SessionState.recording,
        actions=list(actions),
        recorded_action_count=len(actions),
    )


def test_locator_priority_and_password_redaction():
    session = session_with(
        RecordedAction(
            sequence=1,
            kind=ActionKind.fill,
            page_url="https://example.com/login",
            role="textbox",
            label="Password",
            test_id="password-input",
            input_value="super-secret",
        ),
        RecordedAction(
            sequence=2,
            kind=ActionKind.click,
            page_url="https://example.com/login",
            role="button",
            accessible_name="Sign in",
            test_id="login-submit",
            visible_result="Dashboard",
        ),
    )

    script = generate_script(session)

    assert "get_by_test_id('password-input')" in script.source
    assert "get_by_test_id('login-submit')" in script.source
    assert "HUMAN_EXECUTION_PASSWORD" in script.source
    assert "super-secret" not in script.source
    assert "<REDACTED>" not in script.source


def test_accessible_locator_fallback_order():
    session = session_with(
        RecordedAction(
            kind=ActionKind.fill,
            page_url="https://example.com/app",
            role="textbox",
            label="Customer name",
            placeholder="Enter customer",
            input_value="Ada",
        ),
        RecordedAction(
            kind=ActionKind.click,
            page_url="https://example.com/app",
            role="button",
            accessible_name="Save",
        ),
    )
    source = generate_script(session).source
    assert "get_by_label('Customer name', exact=True)" in source
    assert "get_by_role('button', name='Save', exact=True)" in source


def test_no_executable_actions_is_rejected():
    session = session_with(
        RecordedAction(
            kind=ActionKind.navigation,
            page_url="https://example.com/app",
            navigation_url="https://example.com/app",
        )
    )
    with pytest.raises(HumanScriptValidationError, match="No executable"):
        generate_script(session)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("https://example.com/other", True),
        ("https://example.com:443/other", True),
        ("https://evil.example/other", False),
        ("http://example.com/other", False),
    ],
)
def test_same_origin(candidate, expected):
    assert same_origin("https://example.com/app", candidate) is expected

