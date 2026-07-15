from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError

from app.core.config import settings
from app.core.exceptions import DatabaseUnavailable, DuplicateEntity, ProjectNotFound
from app.models.project import Project
from app.repositories.project_repository import ProjectRepository


class ProjectService:
    def __init__(self, session):
        self.session = session
        self.repo = ProjectRepository(session)

    @staticmethod
    def _database_details() -> dict[str, object]:
        url = settings.database_url
        from sqlalchemy.engine import make_url

        parsed = make_url(url)
        return {"host": parsed.host or "127.0.0.1", "port": parsed.port or 5432}

    async def create(self, data):
        try:
            row = await self.repo.add(Project(**data))
            await self.session.commit()
            await self.session.refresh(row)
            return row
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateEntity("A project with the supplied values already exists") from exc
        except (DBAPIError, OSError) as exc:
            await self.session.rollback()
            raise DatabaseUnavailable(
                "Unable to connect to the PostgreSQL database.",
                details=self._database_details(),
            ) from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseUnavailable(
                "Unable to complete the PostgreSQL database operation.",
                details=self._database_details(),
            ) from exc

    async def list(self):
        try:
            return await self.repo.list_active()
        except (SQLAlchemyError, OSError) as exc:
            await self.session.rollback()
            raise DatabaseUnavailable(
                "Unable to connect to the PostgreSQL database.",
                details=self._database_details(),
            ) from exc

    async def get(self, entity_id):
        try:
            row = await self.repo.get(entity_id)
        except (SQLAlchemyError, OSError) as exc:
            await self.session.rollback()
            raise DatabaseUnavailable(
                "Unable to connect to the PostgreSQL database.",
                details=self._database_details(),
            ) from exc
        if not row or not row.is_active:
            raise ProjectNotFound("Project was not found")
        return row

    async def update(self, entity_id, data):
        row = await self.get(entity_id)
        try:
            for key, value in data.items():
                if value is not None:
                    setattr(row, key, value)
            await self.session.commit()
            await self.session.refresh(row)
            return row
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseUnavailable(
                "Unable to complete the PostgreSQL database operation.",
                details=self._database_details(),
            ) from exc

    async def delete(self, entity_id):
        row = await self.get(entity_id)
        try:
            await self.repo.soft_delete(row)
            await self.session.commit()
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise DatabaseUnavailable(
                "Unable to complete the PostgreSQL database operation.",
                details=self._database_details(),
            ) from exc
