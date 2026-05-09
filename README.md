# RapidAuth

**Professional plug-and-play authentication framework for FastAPI.**

[![PyPI version](https://img.shields.io/pypi/v/rapidauth-framework?color=6366f1&label=PyPI&style=flat-square)](https://pypi.org/project/rapidauth-framework/)
[![Python](https://img.shields.io/pypi/pyversions/rapidauth-framework?color=22d3ee&style=flat-square)](https://pypi.org/project/rapidauth-framework/)
[![Downloads](https://img.shields.io/pypi/dm/rapidauth-framework?color=34d399&style=flat-square)](https://pypi.org/project/rapidauth-framework/)
[![License: MIT](https://img.shields.io/badge/license-MIT-fbbf24?style=flat-square)](LICENSE)
[![Author](https://img.shields.io/badge/author-akhmedcodes-6366f1?style=flat-square)](https://beacons.ai/akhmedcodes)

RapidAuth is a **pure backend** authentication framework. Every endpoint returns JSON. Wire in one router and get a complete, production-grade auth system instantly. Your frontend (React, Vue, mobile app) talks to the API over HTTP.

---

## Table of Contents

1. [Install](#install)
2. [Quick Start](#quick-start)
3. [Tortoise ORM Setup](#tortoise-orm-setup)
4. [SQLAlchemy Setup](#sqlalchemy-setup)
5. [All Endpoints](#all-endpoints)
6. [RapidAuth() — full parameter reference](#rapidauth--full-parameter-reference)
7. [RapidAuth methods](#rapidauth-methods)
8. [UserManager methods](#usermanager-methods)
9. [Email Setup](#email-setup)
10. [Role-Based Access Control](#role-based-access-control)
11. [OAuth2 Social Auth](#oauth2-social-auth)
12. [Auth Middleware](#auth-middleware)
13. [Custom Token Store](#custom-token-store)
14. [Exception reference](#exception-reference)
15. [Security](#security)
16. [CLI](#cli)
17. [Development Tips](#development-tips)

---

## Install

```bash
pip install rapidauth-framework

# Tortoise ORM (recommended async ORM):
pip install "rapidauth-framework[tortoise]"

# SQLAlchemy async or sync:
pip install "rapidauth-framework[sqlalchemy]"

# Everything:
pip install "rapidauth-framework[all]"
```

---

## Quick Start

```python
from fastapi import FastAPI, Depends
from rapidauth import RapidAuth
from your_models import User

app  = FastAPI()
auth = RapidAuth(user_model=User, jwt_secret="your-secret-min-32-chars")
app.include_router(auth.router)

@app.get("/profile")
async def profile(user = Depends(auth.get_current_user())):
    return {"username": user.username}
```

One `include_router` call mounts **14 endpoints** automatically.

---

## Tortoise ORM Setup

> **⚠️ Tortoise ORM 1.x users** — use `RegisterTortoise` inside a `lifespan`, not the old
> `register_tortoise` or `Tortoise.init()` alone. See the fix below.

### ✅ Correct setup (works with Tortoise ORM 1.x)

```python
# database.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

@asynccontextmanager
async def tortoise_lifespan(app: FastAPI):
    """Initialize Tortoise ORM on startup; close connections on shutdown."""
    async with RegisterTortoise(
        app,
        db_url="sqlite://./app.db",         # or postgresql+asyncpg://...
        modules={"models": ["models"]},
        generate_schemas=True,
    ):
        yield
```

```python
# main.py
from fastapi import FastAPI
from rapidauth import RapidAuth
from database import tortoise_lifespan
from models import User

app  = FastAPI(lifespan=tortoise_lifespan)
auth = RapidAuth(user_model=User, jwt_secret="your-secret")
app.include_router(auth.router)
```

### ❌ Why the old way fails with Tortoise ORM 1.x

Tortoise ORM 1.x requires a `TortoiseContext` to be active on every async task that
performs DB operations. `RegisterTortoise` sets `_enable_global_fallback=True` which
makes this context available to all request handlers automatically.

Using the old `register_tortoise()` call or plain `Tortoise.init()` without
`_enable_global_fallback=True` causes:

```
RuntimeError: No TortoiseContext is currently active.
```

### Complete Tortoise ORM example

```python
# models.py
from tortoise import fields
from tortoise.models import Model

class User(Model):
    id          = fields.IntField(pk=True)
    username    = fields.CharField(max_length=100, unique=True)
    email       = fields.CharField(max_length=254, unique=True)
    password    = fields.CharField(max_length=200)
    is_active   = fields.BooleanField(default=True)
    is_verified = fields.BooleanField(default=True)
    roles       = fields.JSONField(default=list)
    permissions = fields.JSONField(default=list)
    created_at  = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"
```

```python
# database.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

@asynccontextmanager
async def tortoise_lifespan(app: FastAPI):
    async with RegisterTortoise(
        app,
        db_url="sqlite://./app.db",
        modules={"models": ["models"]},
        generate_schemas=True,
    ):
        yield
```

```python
# main.py
from fastapi import FastAPI, Depends
from rapidauth import RapidAuth
from database import tortoise_lifespan
from models import User

app  = FastAPI(title="My App", lifespan=tortoise_lifespan)
auth = RapidAuth(user_model=User, jwt_secret="change-this-in-production")
app.include_router(auth.router)

get_current_user = auth.get_current_user()

@app.get("/profile")
async def profile(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "email": user.email}
```

Run: `uvicorn main:app --reload`

---

## SQLAlchemy Setup

### Async (recommended)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy import Boolean, Integer, String, JSON
from rapidauth import RapidAuth

engine = create_async_engine("sqlite+aiosqlite:///./app.db")
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = "users"
    id          : Mapped[int]  = mapped_column(Integer, primary_key=True)
    username    : Mapped[str]  = mapped_column(String(100), unique=True)
    email       : Mapped[str]  = mapped_column(String(254), unique=True)
    password    : Mapped[str]  = mapped_column(String(200))
    is_active   : Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified : Mapped[bool] = mapped_column(Boolean, default=False)
    roles       : Mapped[list] = mapped_column(JSON, default=list)
    permissions : Mapped[list] = mapped_column(JSON, default=list)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@asynccontextmanager
async def lifespan(app):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app  = FastAPI(lifespan=lifespan)
auth = RapidAuth(user_model=User, jwt_secret="your-secret", get_db=get_db)
app.include_router(auth.router)
```

### Sync (development only)

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite:///./app.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

auth = RapidAuth(user_model=User, jwt_secret="your-secret", get_db=get_db)
```

> Sync sessions block the event loop. Use async for production.

---

## All Endpoints

Mounted under `/auth` by default (configurable via `router_prefix`). All return JSON.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/register` | — | Register account. Returns token pair. Sends verification or welcome email if configured. |
| `POST` | `/auth/login` | — | Login with username **or** email + password. Returns token pair. Rate-limited. |
| `GET` | `/auth/me` | Bearer | Return current user (id, username, email, is_active, is_verified, roles). |
| `POST` | `/auth/refresh` | Refresh token | Issue new token pair. Old refresh token immediately revoked. |
| `POST` | `/auth/logout` | Bearer | Blacklist current access token. Clears cookies if set. |
| `POST` | `/auth/change-password` | Bearer | Change password. Requires `old_password` + `new_password`. |
| `POST` | `/auth/reset-password` | — | Request password reset email. Always 200 (anti-enumeration). |
| `POST` | `/auth/reset-password/confirm` | — | Confirm reset: `{"token":"…","new_password":"…"}`. 1-hour expiry. |
| `GET` | `/auth/verify-email?token=…` | — | Verify email inline → JSON `{"message":"Email verified successfully"}`. |
| `POST` | `/auth/verify-email` | — | Verify email with `{"token":"…"}` in body. |
| `POST` | `/auth/resend-verification` | Bearer **or** `{"email":"…"}` | Resend verification. No auth needed if email provided in body. Always 200. |
| `POST` | `/auth/revoke-all` | Bearer | Revoke all refresh tokens for the current user. |
| `GET` | `/auth/{provider}/login` | — | Redirect to OAuth2 provider (`google` / `github` / `discord`). |
| `GET` | `/auth/{provider}/callback` | — | Handle OAuth2 callback, create/login user, return token pair. |

---

## `RapidAuth()` — full parameter reference

```python
auth = RapidAuth(
    # ── Required ──────────────────────────────────────────────────────────────
    user_model=User,           # Your ORM model class (Tortoise, SQLAlchemy, SQLModel)
    jwt_secret="...",          # JWT signing secret — min 16 chars, store in .env

    # ── JWT (full config dict, alternative to jwt_secret) ─────────────────────
    jwt={
        "secret":         "your-secret-min-32-chars",
        "algorithm":      "HS256",   # default
        "access_expire":  900,       # access token TTL in seconds  (default 15 min)
        "refresh_expire": 604800,    # refresh token TTL in seconds (default 7 days)
    },

    # ── Field name overrides ───────────────────────────────────────────────────
    # Use these when your model columns differ from the defaults.
    username_field="username",       # default
    email_field="email",             # default
    password_field="password",       # default
    id_field="id",                   # default
    is_active_field="is_active",     # default
    is_verified_field="is_verified", # default
    roles_field="roles",             # default
    permissions_field="permissions", # default

    # ── Refresh token delivery ─────────────────────────────────────────────────
    refresh_token_mode="body",       # "body"   → token in JSON response (default)
                                     # "cookie" → httpOnly cookie only
                                     # "both"   → token in response AND cookie

    # ── Cookie config (used when mode is "cookie" or "both") ──────────────────
    cookie={
        "httponly": True,
        "secure":   True,            # True = HTTPS only (False for local dev)
        "samesite": "lax",           # "lax" | "strict" | "none"
        "domain":   None,
        "max_age":  None,            # defaults to refresh_token_expire
    },

    # ── Password hashing ───────────────────────────────────────────────────────
    password_hasher="bcrypt",        # "bcrypt" (default) | "argon2"

    # ── Email (SMTP) ───────────────────────────────────────────────────────────
    email={
        "host":       "smtp.gmail.com",
        "port":       587,
        "username":   "you@gmail.com",
        "password":   "xxxx xxxx xxxx xxxx",  # Gmail App Password
        "from_email": "you@gmail.com",
        "use_tls":    True,          # STARTTLS (default, port 587)
        "use_ssl":    False,         # SSL (True for port 465)
        "timeout":    30,            # seconds
    },

    # ── URL config ─────────────────────────────────────────────────────────────
    base_url="http://localhost:8000",  # Your backend URL (used in email link defaults)

    # Where verification email links point. Token appended as ?token=TOKEN.
    # Default (None) → {base_url}/auth/verify-email (GET verifies inline, JSON)
    # Production: set to your frontend, e.g. "https://myapp.com/verify-email"
    verify_email_url=None,

    # Where password-reset email links point. Token appended as ?token=TOKEN.
    # Default (None) → dev mode email: shows raw token + curl command
    # Production: set to your frontend, e.g. "https://myapp.com/reset-password"
    reset_password_url=None,

    # ── Feature flags ──────────────────────────────────────────────────────────
    email_verification_required=False,  # True: login blocked until email verified
    enable_refresh_rotation=True,        # True: old refresh token revoked on use

    # ── Rate limiting ──────────────────────────────────────────────────────────
    rate_limit={
        "enabled":             True,
        "max_login_attempts":  5,    # failed attempts before lockout
        "lockout_seconds":     300,  # lockout window (5 minutes)
    },

    # ── Social OAuth ───────────────────────────────────────────────────────────
    social_auth={
        "google": {
            "client_id":     "YOUR_GOOGLE_CLIENT_ID",
            "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
            "redirect_uri":  "https://api.myapp.com/auth/google/callback",
        },
        "github": {
            "client_id":     "YOUR_GITHUB_CLIENT_ID",
            "client_secret": "YOUR_GITHUB_CLIENT_SECRET",
            "redirect_uri":  "https://api.myapp.com/auth/github/callback",
        },
        "discord": {
            "client_id":     "YOUR_DISCORD_CLIENT_ID",
            "client_secret": "YOUR_DISCORD_CLIENT_SECRET",
            "redirect_uri":  "https://api.myapp.com/auth/discord/callback",
        },
    },

    # ── SQLAlchemy ─────────────────────────────────────────────────────────────
    get_db=get_db,              # FastAPI dependency yielding a DB session.
                                # Omit for Tortoise ORM.

    # ── Router ─────────────────────────────────────────────────────────────────
    router_prefix="/auth",          # URL prefix for all endpoints (default)
    router_tags=["Authentication"], # OpenAPI tags in Swagger UI

    # ── Custom token store ─────────────────────────────────────────────────────
    token_store=None,           # Custom store (e.g. Redis).
                                # Must implement: save/get/delete/revoke_all_for_user
)
```

---

## RapidAuth methods

### `auth.router` — property

```python
app.include_router(auth.router)
```

Returns the `APIRouter` with all 14 auth endpoints.

---

### `auth.get_current_user()` — dependency factory

```python
get_current_user = auth.get_current_user()

@app.get("/profile")
async def profile(user = Depends(get_current_user)):
    return {"username": user.username}
```

Returns a FastAPI dependency that:
1. Reads `Authorization: Bearer <token>` from the request header
2. Decodes and validates the JWT
3. Fetches the user from the database
4. Raises `HTTP 401` if missing, expired, revoked, or invalid
5. Returns the user model instance

---

### `auth.current_user_dependency()` — alias for `get_current_user()`

```python
dep = auth.current_user_dependency()   # identical to auth.get_current_user()
```

---

### `auth.add_middleware(app)` — attach AuthMiddleware

```python
auth.add_middleware(app)

@app.get("/")
async def home(request: Request):
    if request.state.user.is_authenticated:
        return {"hello": request.state.user.username}
    return {"hello": "anonymous"}
```

Attaches `AuthMiddleware`. `request.state.user` is populated on every request.
Unauthenticated requests get a proxy object with `is_authenticated = False`.

---

### `auth.manager` — property → `UserManager`

```python
manager = auth.manager
```

Direct access to the `UserManager` instance (see below).

---

### `await auth.create_user(username, email, password, extra=None, **kw)`

```python
user = await auth.create_user("alice", "alice@example.com", "AlicePass1!")

# With extra fields
user = await auth.create_user(
    "admin", "admin@example.com", "AdminPass1!",
    extra={"roles": ["admin"], "permissions": ["users.write"]},
)
```

Checks uniqueness, hashes password, creates and returns the DB record.
Raises `UserAlreadyExistsError` (409) if username or email is taken.

---

### `await auth.authenticate(username_or_email, password, **kw)`

```python
user = await auth.authenticate("alice", "AlicePass1!")
user = await auth.authenticate("alice@example.com", "AlicePass1!")
```

Returns the user on success. Raises:
- `InvalidCredentialsError` (401) — wrong password or user not found
- `AccountInactiveError` (403) — user is deactivated
- `EmailNotVerifiedError` (403) — email unverified + `email_verification_required=True`

---

### `auth.hash_password(password)` → `str`

```python
hashed = auth.hash_password("my-plain-password")
```

Returns the bcrypt/argon2 hash. Uses the `password_hasher` setting.

---

### `auth.verify_password(plain, hashed)` → `bool`

```python
ok = auth.verify_password("my-plain-password", hashed)
```

Timing-safe comparison. Returns `True` if the plain password matches.

---

## UserManager methods

Access via `auth.manager`.

### `await manager.get_by_username(username, **kw)` → user | None

```python
user = await auth.manager.get_by_username("alice")
```

---

### `await manager.get_by_email(email, **kw)` → user | None

```python
user = await auth.manager.get_by_email("alice@example.com")
```

---

### `await manager.get_by_id(user_id, **kw)` → user | None

```python
user = await auth.manager.get_by_id(42)
```

---

### `await manager.create_token_pair(user)` → `(access_token, refresh_token)`

```python
access, refresh = await auth.manager.create_token_pair(user)
```

Creates JWT access + refresh tokens, persists the refresh token hash.

---

### `await manager.refresh_tokens(refresh_token, **kw)` → `(access_token, refresh_token)`

```python
access, new_refresh = await auth.manager.refresh_tokens(old_refresh)
```

Validates, revokes old token, issues new pair.
Raises `InvalidCredentialsError` (401) if invalid or already revoked.

---

### `await manager.revoke_all_tokens(user)` → None

```python
await auth.manager.revoke_all_tokens(user)
```

Removes all refresh tokens for `user`. Use for "log out everywhere".

---

### `await manager.create_verification_token(user)` → `str`

```python
token = await auth.manager.create_verification_token(user)
# Expires in 24 hours
```

Creates and stores a one-time email verification token.

---

### `await manager.verify_email_token(token, **kw)` → user

```python
user = await auth.manager.verify_email_token("TOKEN_FROM_URL")
```

Validates, marks user as verified, deletes the token.
Raises `InvalidCredentialsError` if invalid or expired.

---

### `await manager.create_reset_token(email, **kw)` → `str` | None

```python
token = await auth.manager.create_reset_token("alice@example.com")
# Returns None if email not found — do not expose this to users
```

Creates a 1-hour password reset token. Returns `None` if email not registered.

---

### `await manager.confirm_reset(token, new_password, **kw)` → user

```python
user = await auth.manager.confirm_reset("TOKEN", "NewPassword1!")
```

Validates token, updates password, deletes token.
Raises `InvalidCredentialsError` if invalid or expired.

---

### `await manager.change_password(user, old_password, new_password, **kw)` → user

```python
user = await auth.manager.change_password(user, "OldPass1!", "NewPass1!")
```

Verifies `old_password`, hashes and saves `new_password`.
Raises `InvalidCredentialsError` if `old_password` is wrong.

---

### Field helpers (read-only)

```python
manager.get_id(user)           # primary key
manager.get_username(user)     # str
manager.get_email(user)        # str
manager.get_password(user)     # hashed password string
manager.is_active(user)        # bool (True if field missing)
manager.is_verified(user)      # bool (True if field missing)
manager.get_roles(user)        # list[str]
manager.get_permissions(user)  # list[str]
```

---

## Email Setup

Without the `email` dict the auth endpoints still work — no emails are sent.
Tokens can be tested directly via Swagger/curl. Add the `email` dict for real delivery.

### Password reset flow

```
Development (reset_password_url not set):
  POST /auth/reset-password  {"email": "user@example.com"}
  → 1-hour token created
  → Dev email: shows raw token + curl command for testing
  → POST /auth/reset-password/confirm {"token":"…","new_password":"…"}

Production (reset_password_url set):
  POST /auth/reset-password  {"email": "user@example.com"}
  → 1-hour token created
  → Email link: {reset_password_url}?token=TOKEN
  → Frontend reads ?token= → POST /auth/reset-password/confirm
```

### Email verification flow

```
Development (verify_email_url not set):
  POST /auth/register
  → Email with link: {base_url}/auth/verify-email?token=TOKEN
  → User clicks → GET /auth/verify-email?token=TOKEN
  → JSON {"message": "Email verified successfully"}

Production (verify_email_url set):
  POST /auth/register
  → Email with link: {verify_email_url}?token=TOKEN
  → Frontend reads ?token= → POST /auth/verify-email {"token":"…"}
```

### Resend verification

```python
# With Bearer token (user is logged in):
POST /auth/resend-verification
Authorization: Bearer <access_token>

# Without auth (user can't log in because email_verification_required=True
# and their access token has expired):
POST /auth/resend-verification
{"email": "user@example.com"}

# Both always return 200 (no user enumeration)
```

### Gmail App Password

1. **myaccount.google.com** → **Security** → enable **2-Step Verification**
2. Search **App passwords** → App: Mail / Device: Other → generate
3. Copy 16-char password → paste as `"password"` in email config

### SMTP providers

| Provider | `host` | `port` | Notes |
|----------|--------|--------|-------|
| Gmail | `smtp.gmail.com` | 587 | App Password required |
| Outlook | `smtp.office365.com` | 587 | Account password |
| Yahoo | `smtp.mail.yahoo.com` | 587 | App Password required |
| Yandex | `smtp.yandex.com` | 587 | — |
| Mailgun | `smtp.mailgun.org` | 587 | Dashboard SMTP creds |
| SendGrid | `smtp.sendgrid.net` | 587 | `username="apikey"`, password=API key |
| Amazon SES | `email-smtp.<region>.amazonaws.com` | 587 | AWS SMTP creds |
| Custom VPS | your hostname | 587/465 | port 465 → `use_ssl=True` |

---

## Role-Based Access Control

```python
from fastapi import Depends
from rapidauth.exceptions import PermissionDeniedError

def require_role(*roles: str):
    """Raises HTTP 403 if the user is missing any required role."""
    async def dep(user = Depends(auth.get_current_user())):
        for role in roles:
            if role not in (user.roles or []):
                raise PermissionDeniedError(f"Role '{role}' required")
        return user
    return dep

@app.get("/admin")
async def admin_panel(user = Depends(require_role("admin"))):
    return {"message": f"Hello, {user.username}"}

@app.get("/mod")
async def mod_panel(user = Depends(require_role("admin", "moderator"))):
    return {"ok": True}
```

---

## OAuth2 Social Auth

```python
auth = RapidAuth(
    user_model=User,
    jwt_secret="...",
    social_auth={
        "google":  {"client_id": "...", "client_secret": "...", "redirect_uri": "..."},
        "github":  {"client_id": "...", "client_secret": "...", "redirect_uri": "..."},
        "discord": {"client_id": "...", "client_secret": "...", "redirect_uri": "..."},
    },
)
# Mounts automatically:
# GET /auth/google/login    GET /auth/google/callback
# GET /auth/github/login    GET /auth/github/callback
# GET /auth/discord/login   GET /auth/discord/callback
```

OAuth users are created on first login with `is_verified=True` and a random password.

---

## Auth Middleware

```python
auth.add_middleware(app)

@app.get("/")
async def home(request: Request):
    if request.state.user.is_authenticated:
        return {"hello": request.state.user.username}
    return {"hello": "anonymous"}
```

Every request gets `request.state.user` populated.
Authenticated: the DB user object with `is_authenticated = True`.
Anonymous: a proxy object with `is_authenticated = False`.

---

## Custom Token Store

In-memory by default (lost on restart). Swap in Redis for production:

```python
from datetime import datetime, timezone

class RedisTokenStore:
    def __init__(self, redis):
        self.redis = redis

    async def save(self, token_hash: str, user_id: str, expires_at: datetime) -> None:
        ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        await self.redis.setex(f"rt:{token_hash}", ttl, user_id)

    async def get(self, token_hash: str) -> dict | None:
        val = await self.redis.get(f"rt:{token_hash}")
        return {"user_id": val.decode()} if val else None

    async def delete(self, token_hash: str) -> None:
        await self.redis.delete(f"rt:{token_hash}")

    async def revoke_all_for_user(self, user_id: str) -> None:
        pass  # implement with a reverse index if needed

auth = RapidAuth(user_model=User, jwt_secret="...", token_store=RedisTokenStore(redis))
```

---

## Exception reference

All exceptions extend `rapidauth.exceptions.AuthException` (→ `fastapi.HTTPException`).
FastAPI handles them automatically and returns JSON responses.

| Exception | HTTP | Default detail |
|-----------|------|----------------|
| `InvalidCredentialsError` | 401 | "Invalid credentials" |
| `TokenExpiredError` | 401 | "Token has expired" |
| `TokenInvalidError` | 401 | "Invalid token" |
| `TokenBlacklistedError` | 401 | "Token has been revoked" |
| `InvalidTokenTypeError` | 401 | "Expected {type} token" |
| `UserNotFoundError` | 404 | "User not found" |
| `UserAlreadyExistsError` | 409 | "{field} already exists" |
| `PermissionDeniedError` | 403 | "Permission denied" |
| `EmailNotVerifiedError` | 403 | "Email address is not verified" |
| `AccountInactiveError` | 403 | "Account is inactive" |
| `RateLimitExceededError` | 429 | "Too many login attempts. Please try again later." |

```python
from rapidauth.exceptions import PermissionDeniedError, UserNotFoundError
```

---

## Security

| Feature | Implementation |
|---------|----------------|
| Password hashing | bcrypt (cost 12) or argon2; timing-safe verify |
| JWT | Per-token `jti` in-memory blacklist on logout |
| Refresh rotation | Old token revoked the moment a new pair is issued |
| Brute-force protection | Sliding-window: 5 failed attempts → 5-min IP lockout |
| Email enumeration | Reset + resend always return 200 regardless of email |
| Timing attacks | Dummy hash verify on unknown usernames |
| Cookie flags | `httpOnly`, `secure`, `sameSite` — all configurable |
| Reset tokens | 1-hour expiry, single-use |
| Verify tokens | 24-hour expiry, single-use |

---

## CLI

```bash
# Scaffold a full project (3 files: database.py + models.py + main.py)
rapidauth --default-setup sqlite              # Tortoise ORM + SQLite (async)
rapidauth --default-setup sqlite --sync       # SQLAlchemy sync + SQLite
rapidauth --default-setup sqlalchemy --async  # SQLAlchemy async + SQLite
rapidauth --default-setup sqlalchemy --sync   # SQLAlchemy sync + SQLite
rapidauth --default-setup postgresql --async  # SQLAlchemy async + PostgreSQL
rapidauth --default-setup postgresql --sync   # SQLAlchemy sync + PostgreSQL

rapidauth init       # scaffold .env.example + auth_config.py
rapidauth version    # print installed version
```

---

## Development Tips

**Test auth flows without SMTP:**

```python
@app.post("/dev/verify-token")   # REMOVE IN PRODUCTION
async def dev_verify_token(email: str):
    user  = await auth.manager.get_by_email(email)
    token = await auth.manager.create_verification_token(user)
    return {"token": token, "url": f"/auth/verify-email?token={token}"}

@app.post("/dev/reset-token")    # REMOVE IN PRODUCTION
async def dev_reset_token(email: str):
    token = await auth.manager.create_reset_token(email)
    return {"token": token}
```

**Seed users on startup:**

```python
@asynccontextmanager
async def lifespan(app):
    async with RegisterTortoise(app, db_url="sqlite://./app.db",
                                modules={"models": ["models"]},
                                generate_schemas=True):
        if not await User.exists(username="admin"):
            await auth.create_user(
                "admin", "admin@example.com", "Admin1234!",
                extra={"roles": ["admin"]},
            )
        yield
```

**Full reset flow via curl:**

```bash
# 1. Request
curl -X POST http://localhost:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'

# 2. Get token (dev endpoint or dev-mode email)
curl -X POST "http://localhost:8000/dev/reset-token?email=user@example.com"

# 3. Confirm
curl -X POST http://localhost:8000/auth/reset-password/confirm \
  -H "Content-Type: application/json" \
  -d '{"token": "TOKEN_HERE", "new_password": "NewPass1!"}'
```

---

## Requirements

- Python ≥ 3.10
- FastAPI ≥ 0.100

---

## Author

**akhmedcodes** — [beacons.ai/akhmedcodes](https://beacons.ai/akhmedcodes)

---

## License

MIT © akhmedcodes
