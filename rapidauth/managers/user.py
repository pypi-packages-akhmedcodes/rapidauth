from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from rapidauth.backends.base import BaseAdapter
from rapidauth.config.settings import RapidAuthSettings
from rapidauth.exceptions import (
    AccountInactiveError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from rapidauth.hashing.handler import HashingHandler
from rapidauth.jwt.handler import JWTHandler
from rapidauth.jwt.store import InMemoryTokenStore
from rapidauth.utils.helpers import generate_token, hash_token, is_expired


class UserManager:
    """
    High-level auth manager — orchestrates all auth operations.

    All methods are ORM-agnostic; they delegate DB access to the adapter.
    """

    def __init__(
        self,
        adapter: BaseAdapter,
        settings: RapidAuthSettings,
        jwt: JWTHandler,
        hasher: HashingHandler,
        token_store: Optional[Any] = None,
    ) -> None:
        self._db = adapter
        self._cfg = settings
        self._jwt = jwt
        self._hasher = hasher
        self._token_store = token_store or InMemoryTokenStore()
        # In-memory stores for email/reset tokens
        self._verify_tokens: Dict[str, Dict[str, Any]] = {}
        self._reset_tokens: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    # ── Field helpers ────────────────────────────────────────────────────────

    def _f(self, user: Any, field_key: str) -> Any:
        field_name = getattr(self._cfg, field_key)
        return getattr(user, field_name, None)

    def get_id(self, user: Any) -> Any:
        return self._f(user, "id_field")

    def get_username(self, user: Any) -> str:
        return self._f(user, "username_field")

    def get_email(self, user: Any) -> str:
        return self._f(user, "email_field")

    def get_password(self, user: Any) -> str:
        return self._f(user, "password_field")

    def is_active(self, user: Any) -> bool:
        val = self._f(user, "is_active_field")
        return val if val is not None else True

    def is_verified(self, user: Any) -> bool:
        val = self._f(user, "is_verified_field")
        return val if val is not None else True

    def get_roles(self, user: Any) -> list:
        val = self._f(user, "roles_field")
        return val if val is not None else []

    def get_permissions(self, user: Any) -> list:
        val = self._f(user, "permissions_field")
        return val if val is not None else []

    # ── Core CRUD ────────────────────────────────────────────────────────────

    async def get_by_username(self, username: str, **kw: Any) -> Optional[Any]:
        return await self._db.get_by_field(self._cfg.username_field, username, **kw)

    async def get_by_email(self, email: str, **kw: Any) -> Optional[Any]:
        return await self._db.get_by_field(self._cfg.email_field, email, **kw)

    async def get_by_id(self, user_id: Any, **kw: Any) -> Optional[Any]:
        return await self._db.get_by_id(user_id, **kw)

    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        extra: Optional[Dict[str, Any]] = None,
        **kw: Any,
    ) -> Any:
        """Create a user after checking uniqueness and hashing the password."""
        if await self.get_by_username(username, **kw):
            raise UserAlreadyExistsError("Username")
        if await self.get_by_email(email, **kw):
            raise UserAlreadyExistsError("Email")

        data: Dict[str, Any] = {
            self._cfg.username_field: username,
            self._cfg.email_field: email,
            self._cfg.password_field: self._hasher.hash(password),
            self._cfg.is_active_field: True,
            self._cfg.is_verified_field: not self._cfg.email_verification_required,
        }
        if extra:
            data.update(extra)

        return await self._db.create(data, **kw)

    # ── Authentication ───────────────────────────────────────────────────────

    async def authenticate(
        self,
        username_or_email: str,
        password: str,
        **kw: Any,
    ) -> Any:
        """
        Authenticate by username OR email.
        Raises InvalidCredentialsError, AccountInactiveError, EmailNotVerifiedError.
        """
        user = await self.get_by_username(username_or_email, **kw)
        if user is None:
            user = await self.get_by_email(username_or_email, **kw)
        if user is None:
            # Perform a dummy verify to defeat timing attacks
            self._hasher.verify("dummy", "$2b$12$dummyhashpadding..............")
            raise InvalidCredentialsError()

        if not self._hasher.verify(password, self.get_password(user)):
            raise InvalidCredentialsError()

        if not self.is_active(user):
            raise AccountInactiveError()

        if self._cfg.email_verification_required and not self.is_verified(user):
            raise EmailNotVerifiedError()

        return user

    # ── Token pair ───────────────────────────────────────────────────────────

    def _build_token_payload(self, user: Any) -> Dict[str, Any]:
        return {
            "sub": str(self.get_id(user)),
            "username": self.get_username(user),
        }

    async def create_token_pair(self, user: Any) -> Tuple[str, str]:
        """Return (access_token, refresh_token) and persist the refresh token."""
        payload = self._build_token_payload(user)
        access = self._jwt.create_access_token(payload)
        refresh = self._jwt.create_refresh_token(payload)

        # Persist refresh token hash
        rt_hash = hash_token(refresh)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=self._cfg.refresh_token_expire
        )
        await self._token_store.save(rt_hash, str(self.get_id(user)), expires_at)

        return access, refresh

    async def refresh_tokens(self, refresh_token: str, **kw: Any) -> Tuple[str, str]:
        """Rotate refresh token — old token is revoked, new pair issued."""
        payload = self._jwt.decode_refresh(refresh_token)

        rt_hash = hash_token(refresh_token)
        entry = await self._token_store.get(rt_hash)
        if entry is None:
            raise InvalidCredentialsError("Refresh token is invalid or expired")

        user = await self.get_by_id(payload["sub"], **kw)
        if user is None:
            raise UserNotFoundError()

        # Rotate: revoke old, issue new
        await self._token_store.delete(rt_hash)
        if self._cfg.enable_refresh_rotation:
            self._jwt.revoke(refresh_token)

        return await self.create_token_pair(user)

    async def revoke_all_tokens(self, user: Any) -> None:
        await self._token_store.revoke_all_for_user(str(self.get_id(user)))

    # ── Password helpers ─────────────────────────────────────────────────────

    def hash_password(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return self._hasher.verify(plain, hashed)

    async def change_password(self, user: Any, old_password: str, new_password: str, **kw: Any) -> Any:
        if not self._hasher.verify(old_password, self.get_password(user)):
            raise InvalidCredentialsError("Old password is incorrect")
        new_hash = self._hasher.hash(new_password)
        return await self._db.update(user, {self._cfg.password_field: new_hash}, **kw)

    # ── Email verification ───────────────────────────────────────────────────

    async def create_verification_token(self, user: Any) -> str:
        token = generate_token(32)
        async with self._lock:
            self._verify_tokens[hash_token(token)] = {
                "user_id": str(self.get_id(user)),
                "created_at": datetime.now(timezone.utc),
            }
        return token

    async def verify_email_token(self, token: str, **kw: Any) -> Any:
        from rapidauth.exceptions import TokenInvalidError

        key = hash_token(token)
        async with self._lock:
            entry = self._verify_tokens.get(key)
        if not entry:
            raise InvalidCredentialsError("Invalid verification token")
        if is_expired(entry["created_at"], 86400):  # 24 hours
            async with self._lock:
                self._verify_tokens.pop(key, None)
            raise InvalidCredentialsError("Verification token has expired")

        user = await self.get_by_id(entry["user_id"], **kw)
        if user is None:
            raise UserNotFoundError()

        await self._db.update(user, {self._cfg.is_verified_field: True}, **kw)
        async with self._lock:
            self._verify_tokens.pop(key, None)
        return user

    # ── Password reset ───────────────────────────────────────────────────────

    async def create_reset_token(self, email: str, **kw: Any) -> Optional[str]:
        """Returns the raw token (or None if email not found)."""
        user = await self.get_by_email(email, **kw)
        if not user:
            return None
        token = generate_token(32)
        async with self._lock:
            self._reset_tokens[hash_token(token)] = {
                "user_id": str(self.get_id(user)),
                "created_at": datetime.now(timezone.utc),
            }
        return token

    async def confirm_reset(self, token: str, new_password: str, **kw: Any) -> Any:
        key = hash_token(token)
        async with self._lock:
            entry = self._reset_tokens.get(key)
        if not entry:
            raise InvalidCredentialsError("Invalid password reset token")
        if is_expired(entry["created_at"], 3600):  # 1 hour
            async with self._lock:
                self._reset_tokens.pop(key, None)
            raise InvalidCredentialsError("Password reset token has expired")

        user = await self.get_by_id(entry["user_id"], **kw)
        if user is None:
            raise UserNotFoundError()

        new_hash = self._hasher.hash(new_password)
        await self._db.update(user, {self._cfg.password_field: new_hash}, **kw)
        async with self._lock:
            self._reset_tokens.pop(key, None)
        return user
