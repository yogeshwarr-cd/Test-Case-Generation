from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.schemas.automation_schema import (
    ExecuteScriptsRequest,
    GeneratedScript,
    PlaywrightAuthentication,
    ScriptGenerationResponse,
)
from app.services.automation_service import SCRIPT_ARTIFACT_SUFFIX, automation_service
from app.services.workflow_service import workflow_service

from human_execution.models import GeneratedHumanScript, HumanExecutionSession


class PipelineIntegrationError(RuntimeError):
    pass


class ExistingPipelineAdapter:
    """Publishes the existing generation contract, then calls public pipeline services."""

    async def store_generation(
        self,
        session: HumanExecutionSession,
        scripts: list[GeneratedHumanScript],
    ) -> str:
        generation_id = f"human-gen-{uuid.uuid4()}"
        directory = Path(settings.automation_artifacts_path) / generation_id
        try:
            directory.mkdir(parents=True, exist_ok=False)
            page_elements = [
                {
                    "role": action.role,
                    "name": action.accessible_name,
                    "aria_label": action.accessible_name,
                    "label": action.label,
                    "test_id": action.test_id,
                    "tag": "input" if action.kind.value == "fill" else "button",
                    "placeholder": action.placeholder,
                    "visible_text": action.exact_text,
                    "page_url": action.page_url,
                    "element_id": action.stable_id,
                    "css_selector": action.stable_css,
                    "locator_validated": True,
                }
                for action in session.actions
                if action.kind.value != "navigation"
            ]
            executable_steps = [
                self._pipeline_step(index, action)
                for index, action in enumerate(session.actions, start=1)
                if action.kind.value != "navigation" and not action.is_password
            ]
            generated = [
                GeneratedScript(
                    script_id=item.script_id,
                    workflow_id=item.workflow_id,
                    test_case_id=item.test_case_id,
                    scenario_id=item.scenario_id,
                    name=item.name,
                    application_url=item.application_url,
                    source=item.source,
                    download_path=(
                        f"/api/v1/automation/scripts/{generation_id}/{item.script_id}/download"
                    ),
                    page_url=item.application_url,
                    page_elements=page_elements,
                    executable_steps=executable_steps,
                )
                for item in scripts
            ]
            response = ScriptGenerationResponse(
                generation_id=generation_id,
                application_url=session.application_url,
                reachable=True,
                crawl_status="script_generation_completed",
                crawl_report={
                    "source": "human_execution",
                    "session_id": session.session_id,
                    "events": ["human_recording_completed", "script_generation_completed"],
                },
                scripts=generated,
            )
            workflow = workflow_service.get(session.workflow_id)
            if workflow.get("status") != "completed":
                raise PipelineIntegrationError(
                    "Human execution requires a completed workflow."
                )
            scenario_ids = {str(item.get("scenario_id")) for item in workflow.get("scenarios", [])}
            test_case_ids = {
                str(item.get("test_case_id")) for item in workflow.get("test_cases", [])
            }
            if session.scenario_id not in scenario_ids or session.test_case_id not in test_case_ids:
                raise PipelineIntegrationError(
                    "The scenario or test-case reference does not belong to the workflow."
                )
            manifest = {
                "response": response.model_dump(mode="json"),
                "workflow": workflow,
                "directory": str(directory),
                "learned_locators": {},
            }
            for item in generated:
                (directory / f"{item.script_id}{SCRIPT_ARTIFACT_SUFFIX}").write_text(
                    item.source, encoding="utf-8"
                )
            (directory / "generation.json").write_text(
                json.dumps(manifest, default=str, indent=2), encoding="utf-8"
            )
            return generation_id
        except PipelineIntegrationError:
            raise
        except Exception as exc:
            raise PipelineIntegrationError(
                f"Database or generation-manifest storage failed: {exc}"
            ) from exc

    async def execute_and_compare(self, generation_id: str) -> tuple[Any, dict[str, Any]]:
        try:
            email = os.getenv("HUMAN_EXECUTION_EMAIL")
            password = os.getenv("HUMAN_EXECUTION_PASSWORD")
            authentication = (
                PlaywrightAuthentication(email=email, password=password)
                if email and password
                else None
            )
            report = await automation_service.execute(
                ExecuteScriptsRequest(
                    generation_id=generation_id,
                    mode="automated",
                    authentication=authentication,
                )
            )
            comparison = await automation_service.compare(report.execution_id)
            return report, comparison.model_dump(mode="json")
        except Exception as exc:
            raise PipelineIntegrationError(
                f"Existing Playwright execution pipeline failed: {exc}"
            ) from exc

    @staticmethod
    def _pipeline_step(index: int, action: Any) -> dict[str, Any]:
        target = (
            action.test_id
            or action.label
            or action.accessible_name
            or action.placeholder
            or action.stable_id
            or action.exact_text
            or "recorded element"
        )
        if action.kind.value == "click":
            instruction = f"Click '{target}'"
        elif action.kind.value == "fill":
            instruction = f"Fill '{target}' with '{action.input_value or ''}'"
        elif action.kind.value == "select":
            instruction = f"Select '{action.input_value or ''}' from '{target}'"
        elif action.kind.value in {"check", "uncheck"}:
            instruction = f"{action.kind.value.title()} '{target}'"
        else:
            instruction = f"Click '{target}'"
        return {
            "step_number": index,
            "action": instruction,
            "expected_result": (
                action.visible_result
                or f"The application remains ready after {action.kind.value}."
            ),
        }
