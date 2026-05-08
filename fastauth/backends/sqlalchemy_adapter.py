from __future__ import annotations

import inspect
from typing import Any, Callable, Dict, Optional

from .base import BaseAdapter


async def _exec(coro_or_result: Any) -> Any:
    """Await if coroutine, return directly otherwise (sync session support)."""
    if inspect.isawaitable(coro_or_result):
        return await coro_or_result
    return coro_or_result


class SQLAlchemyAdapter(BaseAdapter):
    """
    ORM adapter for SQLAlchemy 2.x — supports both AsyncSession and sync Session.

    AsyncSession (recommended for FastAPI):
        async def get_db():
            async with AsyncSessionLocal() as session:
                yield session

    Sync Session (simple scripts / --sync setup):
        def get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

    FastAuth auto-detects which one is used at query time via inspect.isawaitable.
    """

    def __init__(self, model: type, get_db: Callable, id_field: str = "id") -> None:
        super().__init__(model, id_field)
        self.get_db = get_db

    async def get_by_field(self, field: str, value: Any, session: Any = None) -> Optional[Any]:
        if session is None:
            raise RuntimeError(
                "SQLAlchemyAdapter requires a `session` kwarg. "
                "Pass get_db=your_session_dependency to FastAuth()."
            )
        from sqlalchemy import select

        stmt = select(self.model).where(getattr(self.model, field) == value)
        result = await _exec(session.execute(stmt))
        return result.scalar_one_or_none()

    async def create(self, data: Dict[str, Any], session: Any = None) -> Any:
        if session is None:
            raise RuntimeError(
                "SQLAlchemyAdapter requires a `session` kwarg. "
                "Pass get_db=your_session_dependency to FastAuth()."
            )
        instance = self.model(**data)
        session.add(instance)
        await _exec(session.commit())
        await _exec(session.refresh(instance))
        return instance

    async def update(self, instance: Any, data: Dict[str, Any], session: Any = None) -> Any:
        if session is None:
            raise RuntimeError(
                "SQLAlchemyAdapter requires a `session` kwarg. "
                "Pass get_db=your_session_dependency to FastAuth()."
            )
        for key, val in data.items():
            setattr(instance, key, val)
        session.add(instance)
        await _exec(session.commit())
        await _exec(session.refresh(instance))
        return instance
