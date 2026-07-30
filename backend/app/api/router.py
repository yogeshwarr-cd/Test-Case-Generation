import importlib
import sys
from pathlib import Path

from fastapi import APIRouter

from app.api.v1 import (
    automation_router,
    document_router,
    image_router,
    input_router,
    project_router,
    scenario_router,
    testcase_router,
    validation_router,
    workflow_router,
)

repository_root = Path(__file__).resolve().parents[3]
if str(repository_root) not in sys.path:
    sys.path.insert(0, str(repository_root))
human_execution_router = importlib.import_module("human_execution.api").router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(project_router.router)
api_router.include_router(input_router.router)
api_router.include_router(scenario_router.router)
api_router.include_router(testcase_router.router)
api_router.include_router(workflow_router.router)
api_router.include_router(validation_router.router)
api_router.include_router(image_router.router)
api_router.include_router(document_router.router)
api_router.include_router(automation_router.router)
# The extension keeps its implementation isolated while sharing the host API.
api_router.include_router(human_execution_router)
