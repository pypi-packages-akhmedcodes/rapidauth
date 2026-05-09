from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class TokenStore(Protocol):
    """
    Interface for refresh-token persistence.

    Replace InMemoryTokenStore with a Redis or DB-backed implementation
    for multi-process / persistent deployments.
    """

    async def save(self, token_hash: str, user_id: str, expires_at: datetime) -> None: ...
    async def get(self, token_hash: str) -> Optional[Dict[str, Any]]: ...
    async def delete(self, token_hash: str) -> None: ...
    async def revoke_all_for_user(self, user_id: str) -> None: ...


class InMemoryTokenStore:
    """
    Thread-safe in-memory refresh token store.

    NOTE: tokens are lost on process restart.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def save(self, token_hash: str, user_id: str, expires_at: datetime) -> None:
        async with self._lock:
            self._store[token_hash] = {
                "user_id": user_id,
                "expires_at": expires_at,
                "revoked": False,
            }

    async def get(self, token_hash: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            entry = self._store.get(token_hash)
            if not entry:
                return None
            if entry["revoked"]:
                return None
            now = datetime.now(timezone.utc)
            exp = entry["expires_at"]
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if now > exp:
                del self._store[token_hash]
                return None
            return entry

    async def delete(self, token_hash: str) -> None:
        async with self._lock:
            self._store.pop(token_hash, None)

    async def revoke_all_for_user(self, user_id: str) -> None:
        async with self._lock:
            for entry in self._store.values():
                if entry["user_id"] == str(user_id):
                    entry["revoked"] = True
