from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastauth.utils.helpers import hash_token


class SessionManager:
    """
    Server-side session store (in-memory).

    For production use, replace with a Redis-backed implementation.
    Sessions are identified by a random session ID stored in a cookie.
    """

    SESSION_COOKIE = "session_id"

    def __init__(self, expire_seconds: int = 3600) -> None:
        self.expire_seconds = expire_seconds
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create(self, user_id: Any, data: Optional[Dict[str, Any]] = None) -> str:
        session_id = secrets.token_urlsafe(32)
        async with self._lock:
            self._sessions[session_id] = {
                "user_id": str(user_id),
                "data": data or {},
                "created_at": datetime.now(timezone.utc),
            }
        return session_id

    async def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with self._lock:
            entry = self._sessions.get(session_id)
        if not entry:
            return None
        now = datetime.now(timezone.utc)
        created = entry["created_at"]
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if (now - created).total_seconds() > self.expire_seconds:
            await self.delete(session_id)
            return None
        return entry

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def revoke_all(self, user_id: Any) -> None:
        async with self._lock:
            to_del = [
                k for k, v in self._sessions.items()
                if v["user_id"] == str(user_id)
            ]
            for k in to_del:
                del self._sessions[k]
