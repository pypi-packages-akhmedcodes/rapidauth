from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseAdapter


class TortoiseAdapter(BaseAdapter):
    """ORM adapter for Tortoise-ORM models."""

    async def get_by_field(self, field: str, value: Any, **_: Any) -> Optional[Any]:
        try:
            return await self.model.get_or_none(**{field: value})
        except Exception:
            return None

    async def create(self, data: Dict[str, Any], **_: Any) -> Any:
        return await self.model.create(**data)

    async def update(self, instance: Any, data: Dict[str, Any], **_: Any) -> Any:
        for key, val in data.items():
            setattr(instance, key, val)
        await instance.save()
        return instance
