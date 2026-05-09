from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class JWTConfig(BaseModel):
    secret: str
    algorithm: str = "HS256"
    access_expire: int = 900       # 15 minutes
    refresh_expire: int = 604800   # 7 days


class CookieConfig(BaseModel):
    httponly: bool = True
    secure: bool = False           # Set True in production (HTTPS)
    samesite: Literal["lax", "strict", "none"] = "lax"
    domain: Optional[str] = None
    path: str = "/"
    max_age: Optional[int] = None


class EmailConfig(BaseModel):
    host: str = "smtp.gmail.com"
    port: int = 587
    username: str = ""
    password: str = ""
    from_email: str = ""
    use_tls: bool = True
    use_ssl: bool = False
    timeout: int = 30


class RateLimitConfig(BaseModel):
    enabled: bool = True
    max_login_attempts: int = 5
    lockout_seconds: int = 300     # 5-minute lockout


class FastAuthSettings(BaseModel):
    # ── Field mappings ──────────────────────────────────────────────────────
    username_field: str = "username"
    email_field: str = "email"
    password_field: str = "password"
    id_field: str = "id"
    is_active_field: str = "is_active"
    is_verified_field: str = "is_verified"
    roles_field: str = "roles"
    permissions_field: str = "permissions"

    # ── JWT ─────────────────────────────────────────────────────────────────
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire: int = 900
    refresh_token_expire: int = 604800

    # ── Token delivery ───────────────────────────────────────────────────────
    refresh_token_mode: Literal["cookie", "body", "both"] = "body"

    # ── Cookie ───────────────────────────────────────────────────────────────
    cookie: CookieConfig = Field(default_factory=CookieConfig)

    # ── Password hashing ─────────────────────────────────────────────────────
    password_hasher: Literal["bcrypt", "argon2"] = "bcrypt"

    # ── Email ────────────────────────────────────────────────────────────────
    email: Optional[EmailConfig] = None

    # ── Social OAuth ─────────────────────────────────────────────────────────
    social_auth: Optional[Dict[str, Dict[str, str]]] = None

    # ── Rate limiting ────────────────────────────────────────────────────────
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)

    # ── Feature flags ────────────────────────────────────────────────────────
    email_verification_required: bool = False
    enable_refresh_rotation: bool = True

    # ── URL config ────────────────────────────────────────────────────────────
    # base_url        : URL of THIS backend.  Used as fallback for verify_email_url.
    #
    # verify_email_url: Where email verification links point.
    #                   Token appended as ?token=TOKEN.
    #                   Default (None) → {base_url}/auth/verify-email?token=TOKEN
    #                   GET /auth/verify-email always verifies and returns JSON.
    #                   Production: set to your frontend page, e.g.
    #                       "https://myapp.com/verify-email"
    #
    # reset_password_url: Where password-reset email links point.
    #                   Token appended as ?token=TOKEN.
    #                   Default (None) → dev mode: email shows raw token + curl example
    #                   Production: set to your frontend page, e.g.
    #                       "https://myapp.com/reset-password"
    base_url: str = "http://localhost:8000"
    verify_email_url: Optional[str] = None
    reset_password_url: Optional[str] = None

    # ── Router ───────────────────────────────────────────────────────────────
    router_prefix: str = "/auth"
    router_tags: List[str] = Field(default_factory=lambda: ["Authentication"])
