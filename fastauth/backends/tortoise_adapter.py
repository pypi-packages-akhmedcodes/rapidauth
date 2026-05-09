from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseAdapter

_TORTOISE_CONTEXT_ERROR = """\
Tortoise ORM is not initialized or the request context is not available.

This error happens with Tortoise ORM 1.x when the database is initialized
without enabling the global context fallback that request handlers need.

Fix — use RegisterTortoise inside a FastAPI lifespan (recommended):

    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from tortoise.contrib.fastapi import RegisterTortoise
    from fastauth import FastAuth
    from models import User

    @asynccontextmanager
    async def lifespan(app):
        async with RegisterTortoise(
            app,
            db_url="sqlite://./app.db",
            modules={"models": ["models"]},
            generate_schemas=True,
        ):
            yield

    app = FastAPI(lifespan=lifespan)
    auth = FastAuth(user_model=User, jwt_secret="your-secret")
    app.include_router(auth.router)

Alternatively, call Tortoise.init() with _enable_global_fallback=True:

    async with lifespan(app):
        await Tortoise.init(
            db_url="...",
            modules={"models": ["models"]},
            _enable_global_fallback=True,
        )
        await Tortoise.generate_schemas()
        yield
        await Tortoise.close_connections()

Original error: {original}
"""


def _raise_tortoise_error(exc: Exception) -> None:
    """Raise a helpful RuntimeError explaining the Tortoise ORM init problem."""
    raise RuntimeError(_TORTOISE_CONTEXT_ERROR.format(original=exc)) from exc


def _is_tortoise_context_error(exc: Exception) -> bool:
    """Return True if exc is a Tortoise ORM initialisation / context error."""
    msg = str(exc).lower()
    return (
        "tortoisecontext" in msg
        or "no tortoisecontext" in msg
        or "context" in msg
        or "db configuration not initialised" in msg
        or "configuration not initialised" in msg
    )


class TortoiseAdapter(BaseAdapter):
    """ORM adapter for Tortoise-ORM models.

    Works with all Tortoise ORM versions:

    - **Tortoise ORM < 0.21** — uses a global connection pool; no special
      context required.  Initialize with ``register_tortoise`` or
      ``Tortoise.init()``.

    - **Tortoise ORM >= 0.21 / 1.x** — requires a ``TortoiseContext`` to be
      active on the current asyncio task.  Use ``RegisterTortoise`` inside a
      FastAPI ``lifespan`` (which sets up the global fallback context) or call
      ``Tortoise.init(_enable_global_fallback=True)``.

    If initialization is missing or incorrect, every method raises a
    :class:`RuntimeError` with step-by-step instructions.
    """

    async def get_by_field(self, field: str, value: Any, **_: Any) -> Optional[Any]:
        """Return the first record where ``field == value``, or ``None``.

        Args:
            field: Model field name (e.g. ``"username"``, ``"email"``).
            value: The value to match against.

        Returns:
            The model instance, or ``None`` when not found.

        Raises:
            RuntimeError: If Tortoise ORM is not properly initialized.
        """
        try:
            return await self.model.get_or_none(**{field: value})
        except RuntimeError as exc:
            if _is_tortoise_context_error(exc):
                _raise_tortoise_error(exc)
            raise
        except Exception:
            # get_or_none raises no exception for missing records, but other
            # DB errors (wrong field, locked table, etc.) can surface here.
            # Return None so the caller can handle "user not found" normally;
            # the error is logged by the ORM itself.
            return None

    async def create(self, data: Dict[str, Any], **_: Any) -> Any:
        """Create and return a new model instance.

        Args:
            data: Mapping of field names to values for the new record.

        Returns:
            The newly created and persisted model instance.

        Raises:
            RuntimeError: If Tortoise ORM is not properly initialized.
            Exception: DB-level errors such as unique-constraint violations.
        """
        try:
            return await self.model.create(**data)
        except RuntimeError as exc:
            if _is_tortoise_context_error(exc):
                _raise_tortoise_error(exc)
            raise

    async def update(self, instance: Any, data: Dict[str, Any], **_: Any) -> Any:
        """Apply ``data`` to ``instance`` fields and persist changes.

        Sets each key in ``data`` as an attribute on ``instance``, then calls
        ``instance.save()``.

        Args:
            instance: Existing model instance to update.
            data: Mapping of field names to new values.

        Returns:
            The updated instance (same object, mutated in place).

        Raises:
            RuntimeError: If Tortoise ORM is not properly initialized.
        """
        for key, val in data.items():
            setattr(instance, key, val)
        try:
            await instance.save()
        except RuntimeError as exc:
            if _is_tortoise_context_error(exc):
                _raise_tortoise_error(exc)
            raise
        return instance
