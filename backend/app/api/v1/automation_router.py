from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.schemas.automation_schema import (
    CompareExecutionRequest,
    ExecuteScriptsRequest,
    GenerateScriptsRequest,
)
from app.services.automation_service import automation_service

router = APIRouter(prefix="/automation", tags=["Test automation"])


@router.get("/health", summary="Check Playwright, browser, and optional Skyvern readiness")
async def health():
    return await automation_service.health()


@router.post("/scripts/generate", summary="Crawl the application and generate UI-derived Playwright scripts")
async def generate_scripts(request: GenerateScriptsRequest):
    return await automation_service.generate(request)


@router.get("/scripts/{generation_id}/{script_id}/download", summary="Download a script")
async def download_script(generation_id: str, script_id: str):
    path = await automation_service.script_path(generation_id, script_id)
    return FileResponse(path, filename=f"{script_id}.py", media_type="text/x-python")


@router.post("/executions", summary="Run scripts automatically or prepare a manual report")
async def execute_scripts(request: ExecuteScriptsRequest):
    return await automation_service.execute(request)


@router.get("/executions/{execution_id}", summary="Get execution dashboard data")
async def execution_report(execution_id: str):
    return automation_service.report(execution_id)


@router.post(
    "/executions/{execution_id}/compare",
    summary="Compare executed UI-derived scripts with generated scenarios and test cases",
)
async def compare_execution(execution_id: str, request: CompareExecutionRequest):
    return await automation_service.compare(execution_id, request.workflow_id)
