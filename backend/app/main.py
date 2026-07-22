from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI,Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.middleware import RequestIDMiddleware
from app.database.health import database_is_healthy
from app.database.session import engine
from app.services.cache_service import cache

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    app.state.database_available = await database_is_healthy(engine)
    if app.state.database_available:
        logger.info("Database connection established")
    else:
        from sqlalchemy.engine import make_url

        database_url = make_url(settings.database_url)
        logger.error(
            "Database connection failed: PostgreSQL is not reachable at %s:%s",
            database_url.host or "127.0.0.1",
            database_url.port or 5432,
        )
    try:
        yield
    finally:
        await engine.dispose()
app=FastAPI(title=settings.app_name,description="Persistence and review API for generated test scenarios and test cases",version="1.0.0",lifespan=lifespan)
app.add_middleware(RequestIDMiddleware);app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.exception_handler(AppError)
async def app_error(request:Request,exc:AppError): return JSONResponse(status_code=exc.status_code,content={"error_code":exc.error_code,"message":exc.message,"details":exc.details,"request_id":getattr(request.state,"request_id",None)})
@app.exception_handler(RequestValidationError)
async def validation_error(request:Request,exc:RequestValidationError): return JSONResponse(status_code=422,content={"error_code":"REQUEST_VALIDATION_ERROR","message":"Request validation failed","details":{"errors":exc.errors()},"request_id":getattr(request.state,"request_id",None)})
@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.exception("Unhandled request error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected server error occurred.",
            "details": {},
            "request_id": getattr(request.state, "request_id", None),
        },
    )
@app.get("/")
async def root(): return {"name":settings.app_name,"docs":"/docs"}
@app.get("/health")
async def health(): return {"status":"healthy","mode":"mock" if settings.app_mock_mode else "live"}
@app.get("/health/database")
async def db_health():
    healthy = await database_is_healthy(engine)
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "healthy" if healthy else "unhealthy",
            "database": "connected" if healthy else "disconnected",
        },
    )
@app.get("/health/cache")
async def cache_health():
    healthy = await cache.health()
    return JSONResponse(status_code=200 if healthy else 503,content={"status":"healthy" if healthy else "unavailable","enabled":settings.redis_cache_enabled,"backend":"redis"})
app.include_router(api_router)
