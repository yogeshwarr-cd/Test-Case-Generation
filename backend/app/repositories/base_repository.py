import uuid
from typing import Generic, TypeVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.base import Base
T = TypeVar("T", bound=Base)
class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def get(self, entity_id: uuid.UUID) -> T | None:
        return await self.session.get(self.model, entity_id)

    async def add(self, entity: T) -> T:
        """Stage and flush an entity without owning the transaction commit."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def list(self) -> list[T]:
        return list((await self.session.scalars(select(self.model))).all())
