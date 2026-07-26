from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.schemas.automation_schema import (
    CompareExecutionRequest,
    CrawlAndGenerateRequest,
    ExecuteScriptsRequest,
    GenerateScriptsRequest,
)
from app.services.automation_service import automation_service

router = APIRouter(prefix="/automation", tags=["Test automation"])


@router.get("/health", summary="Check Playwright, browser, and optional Seacrawl readiness")
async def health():
    return await automation_service.health()


@router.post("/url-crawl", summary="Crawl a URL and generate Playwright test scripts for every discovered page")
async def crawl_and_generate(request: CrawlAndGenerateRequest):
    """Standalone endpoint: no workflow required.

    Provide a URL and the system will crawl all reachable same-origin pages,
    discover interactive elements, and return a Playwright test script per page.
    """
    return await automation_service.crawl_and_generate(request)


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


@router.get("/scripts/{generation_id}/{script_id}/download", summary="Download a script")
async def download_script(generation_id: str, script_id: str):
    path = await automation_service.script_path(generation_id, script_id)
    return FileResponse(path, filename=f"{script_id}.py", media_type="text/x-python")


@router.post("/executions", summary="Run scripts automatically or prepare a manual report")
async def execute_scripts(request: ExecuteScriptsRequest):
    return await automation_service.execute(request)


@router.post("/executions/compare", summary="Compare an execution with scenarios and test cases")
async def compare_execution(request: CompareExecutionRequest):
    return await automation_service.compare(request.execution_id)


@router.get("/executions/{execution_id}", summary="Get execution dashboard data")
async def execution_report(execution_id: str):
    return automation_service.report(execution_id)
