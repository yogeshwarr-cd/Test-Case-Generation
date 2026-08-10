from fastapi import APIRouter
from fastapi import Query
from fastapi.responses import FileResponse, StreamingResponse

from app.schemas.automation_schema import (
    CompareExecutionRequest,
    CrawlApplicationRequest,
    CrawlAndGenerateRequest,
    ExecuteScriptsRequest,
    GenerateScriptsRequest,
)
from app.services.automation_service import automation_service

router = APIRouter(prefix="/automation", tags=["Test automation"])


@router.get("/health", summary="Check Playwright, browser, and optional Seacrawl readiness")
async def health():
    return await automation_service.health()


@router.get("/artifacts", summary="View a Playwright execution evidence artifact")
async def evidence_artifact(path: str = Query(min_length=1)):
    return FileResponse(automation_service.evidence_artifact_path(path))


@router.get("/artifacts/pdf", summary="Download a screenshot evidence artifact as PDF")
async def evidence_artifact_pdf(path: str = Query(min_length=1)):
    content, filename = automation_service.evidence_artifact_pdf(path)
    return StreamingResponse(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/url-crawl", summary="Crawl a URL and generate Playwright test scripts for every discovered page")
async def crawl_and_generate(request: CrawlAndGenerateRequest):
    """Standalone endpoint: no workflow required.

    Provide a URL and the system will crawl all reachable same-origin pages,
    discover interactive elements, and return a Playwright test script per page.
    """
    return await automation_service.crawl_and_generate(request)


@router.post("/url-crawl/jobs", summary="Start a cancellable URL crawl")
async def start_crawl_job(request: CrawlAndGenerateRequest):
    return await automation_service.start_crawl_job(request)


@router.get("/url-crawl/jobs/{job_id}", summary="Get crawl progress and partial result")
async def get_crawl_job(job_id: str):
    return automation_service.crawl_job(job_id)


@router.post("/url-crawl/jobs/{job_id}/stop", summary="Stop a crawl and generate partial scripts")
async def stop_crawl_job(job_id: str):
    return automation_service.stop_crawl_job(job_id)


@router.get(
    "/url-crawl/{crawl_id}/{script_id}/download",
    summary="Download a script from a URL-crawl session",
)
async def download_crawl_script(crawl_id: str, script_id: str):
    path = await automation_service.crawl_script_path(crawl_id, script_id)
    return FileResponse(path, filename=f"{script_id}.py", media_type="text/x-python")


@router.post("/scripts/generate", summary="Generate Playwright scripts from validated test cases")
async def generate_scripts(request: GenerateScriptsRequest):
    return await automation_service.generate(request)


@router.post("/scripts/crawl", summary="Crawl and validate an application before script generation")
async def crawl_application(request: CrawlApplicationRequest):
    return await automation_service.analyze_application(request)


@router.post("/scripts/crawl/jobs", summary="Start a cancellable workflow application crawl")
async def start_workflow_crawl_job(request: CrawlApplicationRequest):
    return await automation_service.start_workflow_crawl_job(request)


@router.get("/scripts/crawl/jobs/{job_id}", summary="Get workflow crawl progress and scripts")
async def get_workflow_crawl_job(job_id: str):
    return automation_service.workflow_crawl_job(job_id)


@router.post("/scripts/crawl/jobs/{job_id}/stop", summary="Stop workflow crawl and generate partial scripts")
async def stop_workflow_crawl_job(job_id: str):
    return automation_service.stop_workflow_crawl_job(job_id)


@router.get("/scripts/{generation_id}/{script_id}/download", summary="Download a script")
async def download_script(generation_id: str, script_id: str):
    path = await automation_service.script_path(generation_id, script_id)
    return FileResponse(path, filename=f"{script_id}.py", media_type="text/x-python")


@router.post("/executions", summary="Run scripts automatically or prepare a manual report")
async def execute_scripts(request: ExecuteScriptsRequest):
    return await automation_service.execute(request)


@router.post("/executions/jobs", summary="Start a background Playwright execution")
async def start_execution_job(request: ExecuteScriptsRequest):
    return await automation_service.start_execution_job(request)


@router.get("/executions/jobs/{job_id}", summary="Get background execution status")
async def execution_job(job_id: str):
    return automation_service.execution_job(job_id)


@router.post("/executions/compare", summary="Compare an execution with scenarios and test cases")
async def compare_execution(request: CompareExecutionRequest):
    return await automation_service.compare(request.execution_id)


@router.get("/executions/{execution_id}", summary="Get execution dashboard data")
async def execution_report(execution_id: str):
    return automation_service.report(execution_id)
