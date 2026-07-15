from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.exceptions import DatabaseUnavailable
from app.database.health import database_is_healthy
from app.main import app
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_database_health_success() -> None:
    connection = AsyncMock()
    connection.execute = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = connection
    engine = SimpleNamespace(connect=lambda: context)

    assert await database_is_healthy(engine) is True


@pytest.mark.asyncio
async def test_database_health_unavailable() -> None:
    context = AsyncMock()
    context.__aenter__.side_effect = OSError("connection refused")
    engine = SimpleNamespace(connect=lambda: context)

    assert await database_is_healthy(engine) is False


@pytest.mark.asyncio
async def test_project_creation_rolls_back_on_database_failure() -> None:
    session = AsyncMock()
    service = ProjectService(session)
    service.repo.add = AsyncMock(side_effect=OSError("connection refused"))

    with pytest.raises(DatabaseUnavailable):
        await service.create({"name": "Example"})

    session.rollback.assert_awaited_once()


def test_request_id_is_in_success_response() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.headers["X-Request-ID"] == "test-request-id"
