from contextlib import asynccontextmanager
from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.middleware import RequestIDMiddleware
from app.database.health import database_is_healthy
from app.database.session import engine
@asynccontextmanager
async def lifespan(app): app.state.database_available=await database_is_healthy(engine);yield;await engine.dispose()
app=FastAPI(title=settings.app_name,description="Persistence and review API for generated test scenarios and test cases",version="1.0.0",lifespan=lifespan)
app.add_middleware(RequestIDMiddleware);app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
@app.exception_handler(AppError)
async def app_error(request:Request,exc:AppError): return JSONResponse(status_code=exc.status_code,content={"error_code":exc.error_code,"message":exc.message,"details":exc.details,"request_id":getattr(request.state,"request_id",None)})
@app.get("/")
async def root(): return {"name":settings.app_name,"docs":"/docs"}
@app.get("/health")
async def health(): return {"status":"healthy"}
@app.get("/health/database")
async def db_health():
    healthy=await database_is_healthy(engine);return JSONResponse(status_code=200 if healthy else 503,content={"status":"healthy" if healthy else "unavailable"})
app.include_router(api_router)
