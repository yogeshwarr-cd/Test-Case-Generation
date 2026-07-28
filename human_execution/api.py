from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from human_execution.models import StartSessionRequest
from human_execution.services.persistence import HumanPersistence, MemoryPersistence
from human_execution.services.session_service import (
    HumanExecutionService,
    HumanSessionError,
    HumanSessionNotFound,
)


def _persistence():
    if os.getenv("HUMAN_EXECUTION_MEMORY_STORE", "").lower() in {"1", "true", "yes"}:
        return MemoryPersistence()
    return HumanPersistence()


persistence = _persistence()
service = HumanExecutionService(persistence)
router = APIRouter(prefix="/human-execution", tags=["Human execution"])
_initialization_lock = asyncio.Lock()
_initialized = False


async def _ensure_initialized() -> None:
    global _initialized
    if _initialized:
        return
    async with _initialization_lock:
        if not _initialized:
            await persistence.initialize()
            _initialized = True


def _payload(session):
    return session.public()


@router.post("/sessions", status_code=202)
async def start_session(request: StartSessionRequest):
    try:
        await _ensure_initialized()
        return _payload(await service.start(request))
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Human execution session could not be stored or started: {exc}",
        ) from exc


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    try:
        return _payload(service.get(session_id))
    except HumanSessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/finish", status_code=202)
async def finish_session(session_id: str):
    try:
        return _payload(await service.finish(session_id))
    except HumanSessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HumanSessionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(session_id: str):
    try:
        return _payload(await service.cancel(session_id))
    except HumanSessionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.websocket("/sessions/{session_id}/live")
async def live_session(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        previous = None
        while True:
            payload = _payload(service.get(session_id))
            marker = (
                payload["state"],
                payload["browser_status"],
                payload["recorded_action_count"],
                payload.get("error"),
            )
            if marker != previous:
                await websocket.send_json(payload)
                previous = marker
            if payload["state"] in {"completed", "failed", "cancelled"}:
                return
            await asyncio.sleep(0.4)
    except HumanSessionNotFound:
        await websocket.send_json({"error": "Session not found"})
        await websocket.close(code=4404)
    except WebSocketDisconnect:
        return


UI_ROOT = Path(__file__).resolve().parent / "ui"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await persistence.initialize()
        yield
        for session_id in list(service.sessions):
            await service.cancel(session_id)

    app = FastAPI(
        title="Human Execution",
        description="Headed Playwright recording extension",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    app.mount("/assets", StaticFiles(directory=UI_ROOT), name="human-execution-assets")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(UI_ROOT / "index.html")

    @app.get("/health")
    async def health():
        return {"status": "healthy", "module": "human_execution"}

    return app


app = create_app()
