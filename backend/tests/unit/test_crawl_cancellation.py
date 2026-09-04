"""
Unit Tests for Crawl Cancellation, Terminal States, Project Name Propagation, and File Isolation.
"""

import asyncio
from pathlib import Path
from threading import Event
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.schemas.automation_schema import (
    CrawlAndGenerateRequest,
    CrawlApplicationRequest,
    GenerateScriptsRequest,
    DiscoveredElement,
    CrawlGenerationResponse,
    CrawlAnalysisResponse,
)
from app.services.automation_service import AutomationService
from app.services.project_structure_generator import ProjectStructureGenerator
from app.core.config import settings


@pytest.fixture
def automation_service():
    return AutomationService()


@pytest.mark.asyncio
async def test_crawl_job_cancellation_lifecycle(automation_service):
    """Test immediate cancellation transitions: queued -> running -> stopping -> stopped."""
    request = CrawlAndGenerateRequest(
        url="https://example.com",
        page_limit=10,
    )

    # Mock crawl_and_generate to wait for cancellation
    async def mock_crawl(*args, **kwargs):
        cancel_event = kwargs.get("cancel_event")
        if cancel_event:
            # Wait for cancellation signal
            while not cancel_event.is_set():
                await asyncio.sleep(0.01)
        return CrawlGenerationResponse(
            crawl_id="test-crawl-id",
            url="https://example.com",
            pages_crawled=1,
            elements_found=0,
            scripts=[],
        )

    with patch.object(automation_service, "crawl_and_generate", side_effect=mock_crawl):
        job_resp = await automation_service.start_crawl_job(request)
        assert job_resp.job_id.startswith("crawl-job-")
        assert job_resp.status in {"queued", "running"}

        # Request stop
        stop_resp = automation_service.stop_crawl_job(job_resp.job_id)
        assert stop_resp.status in {"stopping", "stopped"}
        assert stop_resp.stop_requested is True

        # Let the task finish processing cancellation
        job = automation_service._crawl_jobs[job_resp.job_id]
        if "task" in job:
            await job["task"]

        final_resp = automation_service.crawl_job(job_resp.job_id)
        assert final_resp.status == "stopped"


@pytest.mark.asyncio
async def test_workflow_crawl_job_cancellation(automation_service):
    """Test workflow crawl job cancellation gracefully marks status as stopped."""
    import uuid
    workflow_id = uuid.uuid4()
    request = CrawlApplicationRequest(
        workflow_id=workflow_id,
        application_url="https://example.com",
        page_limit=10,
        project_name="My Custom Project",
    )

    async def mock_analyze(*args, **kwargs):
        cancel_event = kwargs.get("cancel_event")
        if cancel_event:
            while not cancel_event.is_set():
                await asyncio.sleep(0.01)
        return CrawlAnalysisResponse(
            crawl_id="test-crawl-id",
            application_url="https://example.com",
            crawl_status="crawl_incomplete",
            pages_crawled=2,
            elements_found=0,
            discovered_elements=[],
            page_inventory=[],
        )

    with patch.object(automation_service, "analyze_application", side_effect=mock_analyze):
        job_resp = await automation_service.start_workflow_crawl_job(request)
        assert job_resp.status in {"queued", "running"}

        # Request stop
        stop_resp = automation_service.stop_workflow_crawl_job(job_resp.job_id)
        assert stop_resp.status in {"stopping", "stopped"}
        assert stop_resp.stop_requested is True

        job = automation_service._workflow_crawl_jobs[job_resp.job_id]
        if "task" in job:
            await job["task"]

        final_resp = automation_service.workflow_crawl_job(job_resp.job_id)
        assert final_resp.status == "stopped"


def test_project_name_propagation_exact():
    """Verify user project name is used exactly without falling back to title or domain."""
    generator = ProjectStructureGenerator(app_name="Custom User Project Name")
    project = generator.generate_project(
        base_url="https://example.com",
        discovered_elements=[{"tag": "button", "name": "Submit", "page_url": "https://example.com"}],
        page_inventory=[{"url": "https://example.com", "title": "Random Page Title"}],
        test_cases=[{"test_case_id": "TC_001", "title": "Login Flow", "steps": []}],
    )

    assert project.project_name == "custom_user_project_name"
    readme_file = next(f for f in project.files if f.relative_path == "README.md")
    assert "CUSTOM_USER_PROJECT_NAME" in readme_file.content


def test_generated_file_isolation_outside_backend_app(automation_service):
    """Verify generated automation path is isolated outside backend/app source."""
    artifacts_path = automation_service.artifact_root
    generated_path = automation_service.generated_automation_root

    # Ensure neither path contains "backend/app"
    assert "backend\\app" not in str(artifacts_path).lower()
    assert "backend/app" not in str(artifacts_path).lower()
    assert "backend\\app" not in str(generated_path).lower()
    assert "backend/app" not in str(generated_path).lower()
