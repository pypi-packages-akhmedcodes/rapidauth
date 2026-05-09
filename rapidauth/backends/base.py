from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type


def detect_orm(model_class: type) -> str:
    """Inspect model MRO to determine which ORM backs it."""
    for klass in model_class.__mro__:
        module = getattr(klass, "__module__", "") or ""
        if "tortoise" in module:
            return "tortoise"
        if "sqlmodel" in module:
            return "sqlmodel"
        if "sqlalchemy" in module:
            return "sqlalchemy"
    return "generic"


class BaseAdapter(ABC):
    """Abstract ORM adapter — implement one per ORM backend."""

    def __init__(self, model: type, id_field: str = "id") -> None:
        self.model = model
        self.id_field = id_field

    @abstractmethod
    async def get_by_field(self, field: str, value: Any, **kwargs: Any) -> Optional[Any]:
        """Return single user matching field=value, or None."""

    @abstractmethod
    async def create(self, data: Dict[str, Any], **kwargs: Any) -> Any:
        """Create and return a new user."""

    @abstractmethod
    async def update(self, instance: Any, data: Dict[str, Any], **kwargs: Any) -> Any:
        """Persist field updates to an existing user and return it."""

    async def get_by_id(self, user_id: Any, **kwargs: Any) -> Optional[Any]:
        return await self.get_by_field(self.id_field, user_id, **kwargs)
