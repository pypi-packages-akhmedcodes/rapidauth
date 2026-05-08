from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Dict, List

from fastauth.exceptions import RateLimitExceededError


class RateLimiter:
    """
    In-memory sliding-window rate limiter for login endpoints.

    Key: IP address (or any string identifier).
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300) -> None:
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._attempts: Dict[str, List[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        """Raise RateLimitExceededError if the key has exceeded the allowed attempts."""
        async with self._lock:
            now = time.monotonic()
            window_start = now - self.window
            # Keep only attempts within the window
            self._attempts[key] = [t for t in self._attempts[key] if t > window_start]
            if len(self._attempts[key]) >= self.max_attempts:
                raise RateLimitExceededError()
            self._attempts[key].append(now)

    async def reset(self, key: str) -> None:
        """Clear attempts for a key (e.g., after successful login)."""
        async with self._lock:
            self._attempts.pop(key, None)
