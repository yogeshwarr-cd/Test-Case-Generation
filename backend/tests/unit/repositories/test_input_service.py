from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import InputNotFound
from app.services.input_service import InputService


@pytest.mark.asyncio
async def test_update_rejects_input_from_another_project() -> None:
    project_id = uuid4()
    service = InputService(AsyncMock())
    service._ensure_project = AsyncMock()
    service.repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(project_id=uuid4(), source_type="manual")
    )

    with pytest.raises(InputNotFound):
        await service.update_version(project_id, uuid4(), {"user_stories": []})


@pytest.mark.asyncio
async def test_update_creates_a_new_version() -> None:
    project_id = uuid4()
    session = AsyncMock()
    service = InputService(session)
    service._ensure_project = AsyncMock()
    service.repo.get_by_id = AsyncMock(
        return_value=SimpleNamespace(project_id=project_id, source_type="manual")
    )
    new_version = SimpleNamespace(input_version=2)
    service.repo.create_version = AsyncMock(return_value=new_version)

    result = await service.update_version(project_id, uuid4(), {"user_stories": []})

    assert result is new_version
    session.commit.assert_awaited_once()
