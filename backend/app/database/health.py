import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def database_is_healthy(engine: AsyncEngine) -> bool:
    try:
        async def check_connection() -> None:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

        await asyncio.wait_for(check_connection(), timeout=5)
        return True
    except Exception as exc:
        logger.warning("Database health check failed: %s", type(exc).__name__)
        return False
