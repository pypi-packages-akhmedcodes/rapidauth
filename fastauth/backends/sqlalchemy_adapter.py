from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .base import BaseAdapter


class SQLAlchemyAdapter(BaseAdapter):
    """
    ORM adapter for SQLAlchemy 2.x / SQLModel async sessions.

    Usage:
        auth = FastAuth(user_model=User, get_db=get_async_session, ...)

    `get_db` must be a FastAPI dependency that *yields* an AsyncSession.
    """

    def __init__(self, model: type, get_db: Callable, id_field: str = "id") -> None:
        super().__init__(model, id_field)
        self.get_db = get_db

    async def get_by_field(self, field: str, value: Any, session: Any = None) -> Optional[Any]:
        if session is None:
            raise RuntimeError("SQLAlchemyAdapter requires a `session` kwarg")
        from sqlalchemy import select

        stmt = select(self.model).where(getattr(self.model, field) == value)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: Dict[str, Any], session: Any = None) -> Any:
        if session is None:
            raise RuntimeError("SQLAlchemyAdapter requires a `session` kwarg")
        instance = self.model(**data)
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance

    async def update(self, instance: Any, data: Dict[str, Any], session: Any = None) -> Any:
        if session is None:
            raise RuntimeError("SQLAlchemyAdapter requires a `session` kwarg")
        for key, val in data.items():
            setattr(instance, key, val)
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance
