from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.repositories.testcase_repository import TestCaseRepository


@pytest.mark.asyncio
async def test_create_steps_normalizes_order_and_ignores_client_numbers() -> None:
    session = SimpleNamespace(add_all=Mock(), flush=AsyncMock())
    repository = TestCaseRepository(session)
    version = SimpleNamespace(id=uuid4())

    rows = await repository.create_steps(
        version,
        [
            {"step_number": 20, "action": "Open form", "expected_result": "Form opens"},
            {"step_number": 10, "action": "Submit", "expected_result": "Saved"},
        ],
    )

    assert [row.step_number for row in rows] == [1, 2]
    session.add_all.assert_called_once_with(rows)
    session.flush.assert_awaited_once()
