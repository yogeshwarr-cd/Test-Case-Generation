from __future__ import annotations

import ast
import re
from urllib.parse import urlsplit

from human_execution.models import GeneratedHumanScript, HumanExecutionSession, RecordedAction


class HumanScriptValidationError(ValueError):
    pass


def _literal(value: str) -> str:
    return repr(value)


def _locator(action: RecordedAction) -> str:
    if action.test_id:
        return f"page.get_by_test_id({_literal(action.test_id)})"
    if action.label:
        return f"page.get_by_label({_literal(action.label)}, exact=True)"
    if action.role and action.accessible_name:
        return (
            f"page.get_by_role({_literal(action.role)}, "
            f"name={_literal(action.accessible_name)}, exact=True)"
        )
    if action.placeholder:
        return f"page.get_by_placeholder({_literal(action.placeholder)}, exact=True)"
    if action.stable_id:
        return f"page.locator({_literal('#' + action.stable_id)})"
    if action.stable_css:
        return f"page.locator({_literal(action.stable_css)})"
    if action.exact_text:
        return f"page.get_by_text({_literal(action.exact_text)}, exact=True)"
    raise HumanScriptValidationError(
        f"Action {action.sequence} has no stable locator evidence."
    )


def _action_lines(action: RecordedAction) -> list[str]:
    if action.kind.value == "navigation":
        target = action.navigation_url or action.page_url
        return [
            f"    page.goto({_literal(target)}, wait_until=\"domcontentloaded\")",
            "    page.wait_for_load_state(\"networkidle\")",
        ]

    locator = _locator(action)
    lines = [f"    target = {locator}", "    expect(target).to_be_visible()"]
    if action.kind.value == "click":
        lines.extend(["    target.click()", "    page.wait_for_load_state(\"domcontentloaded\")"])
    elif action.kind.value == "fill":
        if action.is_password:
            lines.extend(
                [
                    "    password = os.environ.get(\"HUMAN_EXECUTION_PASSWORD\")",
                    "    assert password, \"HUMAN_EXECUTION_PASSWORD is required\"",
                    "    target.fill(password)",
                ]
            )
        else:
            lines.append(f"    target.fill({_literal(action.input_value or '')})")
    elif action.kind.value == "select":
        lines.append(f"    target.select_option(label={_literal(action.input_value or '')})")
    elif action.kind.value == "check":
        lines.append("    target.check()")
    elif action.kind.value == "uncheck":
        lines.append("    target.uncheck()")
    else:
        raise HumanScriptValidationError(f"Unsupported action kind: {action.kind}")
    lines.append("    page.wait_for_timeout(250)")
    if action.visible_result:
        concise = re.sub(r"\s+", " ", action.visible_result).strip()[:160]
        if concise:
            lines.append(
                f"    expect(page.get_by_text({_literal(concise)}, exact=False).first).to_be_visible()"
            )
    return lines


def generate_script(session: HumanExecutionSession) -> GeneratedHumanScript:
    executable = [
        action.redacted()
        for action in session.actions
        if action.kind.value in {"click", "fill", "select", "check", "uncheck", "navigation"}
    ]
    interaction_count = sum(action.kind.value != "navigation" for action in executable)
    if interaction_count == 0:
        raise HumanScriptValidationError("No executable human actions were recorded.")

    body: list[str] = []
    for action in executable:
        body.extend(_action_lines(action))
    source = "\n".join(
        [
            "import os",
            "from playwright.sync_api import Page, expect",
            "",
            "",
            f"def test_human_flow_{re.sub(r'[^a-zA-Z0-9_]', '_', session.test_case_id).lower()}(page: Page):",
            f"    page.goto({_literal(session.application_url)}, wait_until=\"domcontentloaded\")",
            "    page.wait_for_load_state(\"networkidle\")",
            *body,
            "",
        ]
    )
    validate_script(source)
    return GeneratedHumanScript(
        script_id=f"human-{session.session_id}-{session.test_case_id}",
        workflow_id=session.workflow_id,
        scenario_id=session.scenario_id,
        test_case_id=session.test_case_id,
        name=f"Human recording: {session.test_case_id}",
        application_url=session.application_url,
        source=source,
        action_count=interaction_count,
    )


def validate_script(source: str) -> None:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise HumanScriptValidationError(f"Generated script has invalid syntax: {exc}") from exc
    if "<REDACTED>" in source:
        raise HumanScriptValidationError("A redacted password placeholder leaked into the script.")
    if "input[type=" in source or "nth-child" in source or ".nth(" in source:
        raise HumanScriptValidationError("Generated script contains an unstable locator.")
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    if not any(
        isinstance(call.func, ast.Attribute)
        and call.func.attr in {"click", "fill", "select_option", "check", "uncheck"}
        for call in calls
    ):
        raise HumanScriptValidationError("Generated script has no executable interaction.")
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "password" in node.value.lower() and len(node.value) > 80:
                raise HumanScriptValidationError("Potential password value detected in script.")


def same_origin(application_url: str, candidate: str) -> bool:
    expected = urlsplit(application_url)
    actual = urlsplit(candidate)

    def origin(value):
        default_port = 443 if value.scheme == "https" else 80 if value.scheme == "http" else None
        return value.scheme, value.hostname, value.port or default_port

    return origin(expected) == origin(actual)
