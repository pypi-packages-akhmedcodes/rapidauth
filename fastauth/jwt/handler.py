from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Set

import jwt


class JWTHandler:
    """
    JWT access + refresh token manager.

    Security notes:
    - Every token carries a unique `jti` (JWT ID) for revocation.
    - Blacklist is in-memory; swap for Redis/DB in production.
    - Tokens are signed with HMAC-SHA256 (HS256) by default.
    """

    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        access_expire: int = 900,
        refresh_expire: int = 604800,
    ) -> None:
        if not secret or len(secret) < 16:
            raise ValueError("JWT secret must be at least 16 characters")
        self.secret = secret
        self.algorithm = algorithm
        self.access_expire = access_expire
        self.refresh_expire = refresh_expire
        self._blacklist: Set[str] = set()

    # ── Token creation ───────────────────────────────────────────────────────

    def create_access_token(self, payload: Dict[str, Any]) -> str:
        return self._encode(payload, self.access_expire, token_type="access")

    def create_refresh_token(self, payload: Dict[str, Any]) -> str:
        return self._encode(payload, self.refresh_expire, token_type="refresh")

    def _encode(self, data: Dict[str, Any], expire_seconds: int, token_type: str) -> str:
        now = datetime.now(timezone.utc)
        claims = {
            **data,
            "iat": now,
            "exp": now + timedelta(seconds=expire_seconds),
            "type": token_type,
            "jti": secrets.token_urlsafe(16),
        }
        return jwt.encode(claims, self.secret, algorithm=self.algorithm)

    # ── Token verification ───────────────────────────────────────────────────

    def decode(self, token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
        from fastauth.exceptions import (
            TokenBlacklistedError,
            TokenExpiredError,
            TokenInvalidError,
            InvalidTokenTypeError,
        )
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError()
        except jwt.InvalidTokenError:
            raise TokenInvalidError()

        jti = payload.get("jti")
        if jti and jti in self._blacklist:
            raise TokenBlacklistedError()

        if expected_type and payload.get("type") != expected_type:
            raise InvalidTokenTypeError(expected_type)

        return payload

    def decode_access(self, token: str) -> Dict[str, Any]:
        return self.decode(token, expected_type="access")

    def decode_refresh(self, token: str) -> Dict[str, Any]:
        return self.decode(token, expected_type="refresh")

    # ── Revocation ───────────────────────────────────────────────────────────

    def revoke(self, token: str) -> None:
        """Add token's jti to the in-memory blacklist."""
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                options={"verify_exp": False},
            )
            jti = payload.get("jti")
            if jti:
                self._blacklist.add(jti)
        except jwt.InvalidTokenError:
            pass

    def revoke_jti(self, jti: str) -> None:
        self._blacklist.add(jti)

    def is_revoked(self, jti: str) -> bool:
        return jti in self._blacklist
