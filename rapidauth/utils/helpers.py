from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone


def generate_token(length: int = 32) -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(length)


def generate_otp(digits: int = 6) -> str:
    """Generate a numeric OTP code."""
    return str(secrets.randbelow(10**digits)).zfill(digits)


def hash_token(token: str) -> str:
    """SHA-256 hash a token for safe DB storage (one-way)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_expired(created_at: datetime, expire_seconds: int) -> bool:
    """Return True if `created_at` is older than `expire_seconds`."""
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return (now - created_at).total_seconds() > expire_seconds
