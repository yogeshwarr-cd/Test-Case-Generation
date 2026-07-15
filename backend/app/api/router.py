from fastapi import APIRouter
from app.api.v1 import input_router,project_router,scenario_router,testcase_router,workflow_router,validation_router
api_router=APIRouter(prefix="/api/v1")
api_router.include_router(project_router.router);api_router.include_router(input_router.router);api_router.include_router(scenario_router.router);api_router.include_router(testcase_router.router)
api_router.include_router(workflow_router.router);api_router.include_router(validation_router.router)
