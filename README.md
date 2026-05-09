# FastAuth

**Professional plug-and-play authentication framework for FastAPI.**

[![PyPI version](https://img.shields.io/pypi/v/fastauth-framework?color=6366f1&label=PyPI&style=flat-square)](https://pypi.org/project/fastauth-framework/)
[![Python](https://img.shields.io/pypi/pyversions/fastauth-framework?color=22d3ee&style=flat-square)](https://pypi.org/project/fastauth-framework/)
[![Downloads](https://img.shields.io/pypi/dm/fastauth-framework?color=34d399&style=flat-square)](https://pypi.org/project/fastauth-framework/)
[![License: MIT](https://img.shields.io/badge/license-MIT-fbbf24?style=flat-square)](LICENSE)

FastAuth is a **pure backend** authentication framework. Every endpoint returns JSON. You wire in one router and immediately get a complete, production-grade auth system. Your frontend (React, Vue, mobile app) talks to the API over HTTP.

---

## Table of Contents

1. [Install](#install)
2. [Quick Start](#quick-start)
3. [Tortoise ORM Setup](#tortoise-orm-setup) ← fix for the `No TortoiseContext` error
4. [SQLAlchemy Setup](#sqlalchemy-setup)
5. [All Endpoints](#all-endpoints)
6. [FastAuth() — full parameter reference](#fastauth--full-parameter-reference)
7. [FastAuth methods](#fastauth-methods)
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
pip install fastauth-framework

# Tortoise ORM (recommended async ORM):
pip install "fastauth-framework[tortoise]"

# SQLAlchemy async or sync:
pip install "fastauth-framework[sqlalchemy]"

# Everything:
pip install "fastauth-framework[all]"
```

---

## Quick Start

```python
from fastapi import FastAPI, Depends
from fastauth import FastAuth
from your_models import User

app  = FastAPI()
auth = FastAuth(user_model=User, jwt_secret="your-secret-min-32-chars")
app.include_router(auth.router)

@app.get("/profile")
async def profile(user = Depends(auth.get_current_user())):
    return {"username": user.username}
```

One `include_router` call mounts **14 endpoints** automatically.

---

## Tortoise ORM Setup

### ⚠️ Fix: `RuntimeError: No TortoiseContext is currently active`

**Tortoise ORM 1.x changed how database contexts work.** Using the old
`register_tortoise` or calling `Tortoise.init()` without
`_enable_global_fallback=True` causes this error.

**The fix:** Use `RegisterTortoise` inside a FastAPI `lifespan` context. It
sets up the global fallback context that request handlers need automatically.

```python
# database.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

@asynccontextmanager
async def tortoise_lifespan(app: FastAPI):
    """Initialize Tortoise ORM on startup, close connections on shutdown."""
    async with RegisterTortoise(
        app,
        db_url="sqlite://./app.db",         # or postgresql+asyncpg://...
        modules={"models": ["models"]},      # list of modules with Model classes
        generate_schemas=True,               # creates tables if they don't exist
    ):
        yield  # server runs here
```

```python
# main.py
from fastapi import FastAPI, Depends
from fastauth import FastAuth
from database import tortoise_lifespan
from models import User

app  = FastAPI(lifespan=tortoise_lifespan)   # pass the lifespan here
auth = FastAuth(user_model=User, jwt_secret="your-secret")
app.include_router(auth.router)
```

### ✅ Complete Tortoise ORM example

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
from fastauth import FastAuth
from database import tortoise_lifespan
from models import User

app  = FastAPI(title="My App", lifespan=tortoise_lifespan)
auth = FastAuth(user_model=User, jwt_secret="super-secret-key-change-in-production")
app.include_router(auth.router)

get_current_user = auth.get_current_user()

@app.get("/profile")
async def profile(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "email": user.email}
```

Run: `uvicorn main:app --reload`

### PostgreSQL with Tortoise ORM

```python
@asynccontextmanager
async def tortoise_lifespan(app):
    async with RegisterTortoise(
        app,
        db_url="postgresql+asyncpg://user:password@localhost:5432/mydb",
        modules={"models": ["models"]},
        generate_schemas=True,
    ):
        yield
```

```bash
pip install "fastauth-framework[tortoise]" asyncpg
```

---

## SQLAlchemy Setup

### Async (recommended for production)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy import Boolean, Integer, String, JSON
from fastauth import FastAuth

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
auth = FastAuth(user_model=User, jwt_secret="your-secret", get_db=get_db)
app.include_router(auth.router)
```

### Sync (development only — blocks the event loop)

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

auth = FastAuth(user_model=User, jwt_secret="your-secret", get_db=get_db)
```

---

## All Endpoints

Mounted under `/auth` by default (change via `router_prefix`). All return JSON.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/register` | — | Register a new account. Returns token pair. Sends verification or welcome email if email is configured. |
| `POST` | `/auth/login` | — | Login with username **or** email + password. Returns token pair. Rate-limited. |
| `GET` | `/auth/me` | Bearer | Return current user fields (id, username, email, is_active, is_verified, roles). |
| `POST` | `/auth/refresh` | Refresh token | Issue a new token pair. Old refresh token is immediately revoked. |
| `POST` | `/auth/logout` | Bearer | Blacklist the current access token. Clears cookies if set. |
| `POST` | `/auth/change-password` | Bearer | Change password. Requires `old_password` + `new_password`. |
| `POST` | `/auth/reset-password` | — | Request a password reset email. Always returns 200 (anti-enumeration). |
| `POST` | `/auth/reset-password/confirm` | — | Confirm reset with `{"token":"...","new_password":"..."}`. Token expires in 1 hour. |
| `GET` | `/auth/verify-email?token=…` | — | Verify email inline. Returns JSON `{"message":"Email verified successfully"}`. |
| `POST` | `/auth/verify-email` | — | Verify email with token in body `{"token":"..."}`. |
| `POST` | `/auth/resend-verification` | Bearer **or** `{"email":"..."}` | Resend verification email. Accepts Bearer token OR email in body — no auth needed if email is provided. Always 200. |
| `POST` | `/auth/revoke-all` | Bearer | Revoke all refresh tokens for the current user. |
| `GET` | `/auth/{provider}/login` | — | Redirect to OAuth2 provider (`google` / `github` / `discord`). |
| `GET` | `/auth/{provider}/callback` | — | Handle OAuth2 callback, create/login user, return token pair. |

---

## `FastAuth()` — full parameter reference

```python
auth = FastAuth(
    # ── Required ──────────────────────────────────────────────────────────────
    user_model=User,           # Your ORM model class (Tortoise, SQLAlchemy, SQLModel)
    jwt_secret="...",          # Secret for signing JWTs — min 16 chars, keep in .env

    # ── JWT (full config dict, alternative to jwt_secret) ─────────────────────
    jwt={
        "secret":         "your-secret-min-32-chars",
        "algorithm":      "HS256",   # default
        "access_expire":  900,       # access token lifetime in seconds  (default 15 min)
        "refresh_expire": 604800,    # refresh token lifetime in seconds (default 7 days)
    },

    # ── Field name overrides ───────────────────────────────────────────────────
    # Use these when your model columns have different names than the defaults.
    username_field="username",       # default "username"
    email_field="email",             # default "email"
    password_field="password",       # default "password"
    id_field="id",                   # default "id"
    is_active_field="is_active",     # default "is_active"
    is_verified_field="is_verified", # default "is_verified"
    roles_field="roles",             # default "roles"
    permissions_field="permissions", # default "permissions"

    # ── Refresh token delivery ─────────────────────────────────────────────────
    refresh_token_mode="body",       # "body"   → token in JSON response (default)
                                     # "cookie" → httpOnly cookie only
                                     # "both"   → token in response AND cookie

    # ── Cookie config (used when refresh_token_mode is "cookie" or "both") ────
    cookie={
        "httponly": True,            # default True
        "secure":   True,            # True = HTTPS only (set False for local dev)
        "samesite": "lax",           # "lax" | "strict" | "none"
        "domain":   None,            # set for cross-subdomain cookies
        "max_age":  None,            # seconds; defaults to refresh_token_expire
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
        "use_ssl":    False,         # SSL (set True for port 465)
        "timeout":    30,            # connection timeout in seconds
    },

    # ── URL config ─────────────────────────────────────────────────────────────
    base_url="http://localhost:8000",  # Your backend URL (used in email link defaults)

    # Where verification email links point. Token appended as ?token=TOKEN.
    # Default (None) → {base_url}/auth/verify-email (GET verifies inline, returns JSON)
    # Production: set to your frontend page, e.g. "https://myapp.com/verify-email"
    verify_email_url=None,

    # Where password-reset email links point. Token appended as ?token=TOKEN.
    # Default (None) → dev mode: email shows raw token + curl command for testing
    # Production: set to your frontend page, e.g. "https://myapp.com/reset-password"
    reset_password_url=None,

    # ── Feature flags ──────────────────────────────────────────────────────────
    email_verification_required=False,  # if True: login blocked until email verified
    enable_refresh_rotation=True,        # if True: old refresh token revoked on use

    # ── Rate limiting ──────────────────────────────────────────────────────────
    rate_limit={
        "enabled":             True,
        "max_login_attempts":  5,    # failed attempts before lockout
        "lockout_seconds":     300,  # lockout duration (5 minutes)
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
                                # Omit this for Tortoise ORM.

    # ── Router ─────────────────────────────────────────────────────────────────
    router_prefix="/auth",          # URL prefix for all endpoints (default "/auth")
    router_tags=["Authentication"], # OpenAPI tags shown in Swagger UI

    # ── Custom token store ─────────────────────────────────────────────────────
    token_store=None,           # Use a custom store (e.g. Redis).
                                # Must implement: save/get/delete/revoke_all_for_user
)
```

---

## FastAuth methods

### `auth.router` — property

```python
app.include_router(auth.router)
```

Returns the `APIRouter` containing all 14 auth endpoints.

---

### `auth.get_current_user()` — dependency factory

```python
get_current_user = auth.get_current_user()

@app.get("/profile")
async def profile(user = Depends(get_current_user)):
    return {"username": user.username}
```

Returns a FastAPI dependency function that:
1. Reads `Authorization: Bearer <token>` from the request header
2. Decodes and validates the JWT
3. Fetches the user from the database
4. Raises `HTTP 401` if the token is missing, expired, revoked, or invalid
5. Returns the user model instance

---

### `auth.current_user_dependency()` — alias

```python
# Same as auth.get_current_user()
dep = auth.current_user_dependency()
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

Attaches `AuthMiddleware` so that `request.state.user` is populated on every request.
Anonymous requests get a proxy object with `is_authenticated = False`.

---

### `auth.manager` — property

```python
manager = auth.manager   # returns UserManager instance
```

Access to the full `UserManager` API (see below).

---

### `await auth.create_user(username, email, password, extra=None, **kw)`

```python
# Create a user programmatically (e.g. in seed scripts or tests)
user = await auth.create_user("alice", "alice@example.com", "AlicePass1!")

# With extra fields (roles, permissions, etc.)
user = await auth.create_user(
    "admin", "admin@example.com", "AdminPass1!",
    extra={"roles": ["admin"], "permissions": ["users.write"]},
)
```

Checks username and email uniqueness, hashes the password, and creates the record.
Raises `UserAlreadyExistsError` (HTTP 409) if username or email is taken.

---

### `await auth.authenticate(username_or_email, password, **kw)`

```python
user = await auth.authenticate("alice", "AlicePass1!")           # by username
user = await auth.authenticate("alice@example.com", "AlicePass1!")  # by email
```

Returns the user on success. Raises:
- `InvalidCredentialsError` (401) — wrong password or user not found
- `AccountInactiveError` (403) — `is_active` is False
- `EmailNotVerifiedError` (403) — email not verified and `email_verification_required=True`

---

### `auth.hash_password(password)` → `str`

```python
hashed = auth.hash_password("my-plain-password")
```

Returns the bcrypt or argon2 hash of `password`. Uses the hasher configured by `password_hasher`.

---

### `auth.verify_password(plain, hashed)` → `bool`

```python
ok = auth.verify_password("my-plain-password", hashed)
```

Timing-safe comparison. Returns `True` if the plain password matches the hash.

---

## UserManager methods

Access the manager via `auth.manager`.

### `await manager.get_by_username(username, **kw)` → user or None

```python
user = await auth.manager.get_by_username("alice")
```

Looks up a user by their username field. Returns `None` if not found.

---

### `await manager.get_by_email(email, **kw)` → user or None

```python
user = await auth.manager.get_by_email("alice@example.com")
```

Looks up a user by their email field. Returns `None` if not found.

---

### `await manager.get_by_id(user_id, **kw)` → user or None

```python
user = await auth.manager.get_by_id(42)
```

Looks up a user by primary key. Returns `None` if not found.

---

### `await manager.create_token_pair(user)` → `(access_token, refresh_token)`

```python
access, refresh = await auth.manager.create_token_pair(user)
```

Creates a JWT access token and a refresh token for `user`. Persists the
refresh token hash in the token store. Returns the raw token strings.

---

### `await manager.refresh_tokens(refresh_token, **kw)` → `(access_token, refresh_token)`

```python
access, new_refresh = await auth.manager.refresh_tokens(old_refresh_token)
```

Validates the refresh token, revokes it, and issues a new token pair.
Raises `InvalidCredentialsError` (401) if the token is invalid or already revoked.

---

### `await manager.revoke_all_tokens(user)` → None

```python
await auth.manager.revoke_all_tokens(user)
```

Removes all refresh tokens for `user` from the token store. Useful for "log out everywhere".

---

### `await manager.create_verification_token(user)` → `str`

```python
token = await auth.manager.create_verification_token(user)
# Token is valid for 24 hours
```

Creates and stores a one-time email verification token for `user`.
Returns the raw (unhashed) token string.

---

### `await manager.verify_email_token(token, **kw)` → user

```python
user = await auth.manager.verify_email_token("TOKEN_FROM_URL")
```

Validates the token, marks the user as verified, and deletes the token.
Raises `InvalidCredentialsError` if the token is invalid or expired.

---

### `await manager.create_reset_token(email, **kw)` → `str` or `None`

```python
token = await auth.manager.create_reset_token("alice@example.com")
# Returns None if email not found (safe — don't expose this to users)
```

Creates a one-time password reset token for the user with the given email.
Token expires in 1 hour. Returns `None` if the email is not registered.

---

### `await manager.confirm_reset(token, new_password, **kw)` → user

```python
user = await auth.manager.confirm_reset("TOKEN", "NewPassword1!")
```

Validates the token, hashes `new_password`, updates the user, and deletes the token.
Raises `InvalidCredentialsError` if the token is invalid or expired.

---

### `await manager.change_password(user, old_password, new_password, **kw)` → user

```python
user = await auth.manager.change_password(user, "OldPass1!", "NewPass1!")
```

Verifies `old_password` matches the stored hash, then sets `new_password`.
Raises `InvalidCredentialsError` if `old_password` is wrong.

---

### Field helpers (read-only)

```python
manager.get_id(user)           # → primary key value
manager.get_username(user)     # → str
manager.get_email(user)        # → str
manager.get_password(user)     # → hashed password string
manager.is_active(user)        # → bool (defaults True if field missing)
manager.is_verified(user)      # → bool (defaults True if field missing)
manager.get_roles(user)        # → list[str]
manager.get_permissions(user)  # → list[str]
```

---

## Email Setup

Without the `email` dict the auth endpoints still work — no emails are sent.
Add it when you want real delivery.

### Password reset flow

```
Development (reset_password_url not set):
  POST /auth/reset-password  {"email": "user@example.com"}
  → Token created (1-hour expiry)
  → Email sent showing raw token + curl command for Swagger testing
  → Use token: POST /auth/reset-password/confirm {"token":"...","new_password":"..."}

Production (reset_password_url set):
  POST /auth/reset-password  {"email": "user@example.com"}
  → Token created (1-hour expiry)
  → Email sent with link: {reset_password_url}?token=TOKEN
  → User opens frontend page, reads ?token= from URL
  → Frontend: POST /auth/reset-password/confirm {"token":"...","new_password":"..."}
```

### Email verification flow

```
Development (verify_email_url not set):
  POST /auth/register
  → Email with link: {base_url}/auth/verify-email?token=TOKEN
  → User clicks → GET /auth/verify-email?token=TOKEN
  → Returns JSON {"message": "Email verified successfully"}

Production (verify_email_url set):
  POST /auth/register
  → Email with link: {verify_email_url}?token=TOKEN
  → User opens frontend page, reads ?token= from URL
  → Frontend: POST /auth/verify-email {"token":"..."}
              or GET  /auth/verify-email?token=... (same result)
```

### Resend verification

```python
# With Bearer token (user is logged in):
POST /auth/resend-verification
Authorization: Bearer <access_token>

# Without auth (e.g. user can't log in because email_verification_required=True
# and their access token expired):
POST /auth/resend-verification
{"email": "user@example.com"}

# Both always return 200 (no user enumeration)
```

### Gmail App Password

1. **myaccount.google.com** → **Security** → enable **2-Step Verification**
2. Search **App passwords** → App: Mail / Device: Other → name it `fastauth`
3. Copy the 16-char password → paste as `"password"` in the email config

### SMTP providers

| Provider | `host` | `port` | Notes |
|----------|--------|--------|-------|
| Gmail | `smtp.gmail.com` | 587 | App Password required |
| Outlook / Hotmail | `smtp.office365.com` | 587 | Account password |
| Yahoo | `smtp.mail.yahoo.com` | 587 | App Password required |
| Yandex | `smtp.yandex.com` | 587 | — |
| Mailgun | `smtp.mailgun.org` | 587 | Dashboard SMTP creds |
| SendGrid | `smtp.sendgrid.net` | 587 | `username="apikey"`, password=API key |
| Amazon SES | `email-smtp.<region>.amazonaws.com` | 587 | AWS SMTP creds |
| Custom VPS | your hostname | `25`/`587`/`465` | port 465 → `use_ssl=True` |

---

## Role-Based Access Control

```python
from fastapi import Depends
from fastauth.exceptions import PermissionDeniedError

def require_role(*roles: str):
    """Dependency factory: raises 403 if the user doesn't have all required roles."""
    async def dep(user = Depends(auth.get_current_user())):
        for role in roles:
            if role not in (user.roles or []):
                raise PermissionDeniedError(f"Role '{role}' required")
        return user
    return dep

@app.get("/admin")
async def admin(user = Depends(require_role("admin"))):
    return {"message": f"Welcome admin {user.username}"}

@app.get("/dashboard")
async def dashboard(user = Depends(auth.get_current_user())):
    return {"welcome": user.username}
```

---

## OAuth2 Social Auth

Configure providers and the routes are added automatically:

```python
auth = FastAuth(
    user_model=User,
    jwt_secret="...",
    social_auth={
        "google": {
            "client_id":     "YOUR_CLIENT_ID",
            "client_secret": "YOUR_CLIENT_SECRET",
            "redirect_uri":  "https://api.myapp.com/auth/google/callback",
        },
        "github": {
            "client_id":     "YOUR_CLIENT_ID",
            "client_secret": "YOUR_CLIENT_SECRET",
            "redirect_uri":  "https://api.myapp.com/auth/github/callback",
        },
    },
)
# Adds: GET /auth/google/login, GET /auth/google/callback
#        GET /auth/github/login,  GET /auth/github/callback
```

OAuth users are created automatically on first login. `is_verified` is set to `True`.
A random password is generated for OAuth-only users.

---

## Auth Middleware

```python
auth.add_middleware(app)

@app.get("/")
async def home(request: Request):
    user = request.state.user
    if user.is_authenticated:
        return {"hello": user.username}
    return {"hello": "anonymous"}
```

Attaches `AuthMiddleware` to the app. On every request:
- If a valid Bearer token is present: `request.state.user` is the DB user object,
  with `is_authenticated = True`
- Otherwise: `request.state.user` is an anonymous proxy with `is_authenticated = False`

---

## Custom Token Store

By default, refresh tokens are stored in memory (lost on restart). For multi-process
or persistent deployments, implement a custom store:

```python
from datetime import datetime, timezone

class RedisTokenStore:
    """Refresh token store backed by Redis."""

    def __init__(self, redis_client):
        self.redis = redis_client

    async def save(self, token_hash: str, user_id: str, expires_at: datetime) -> None:
        """Persist a refresh token hash with its owner and expiry."""
        ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        await self.redis.setex(f"rt:{token_hash}", ttl, user_id)

    async def get(self, token_hash: str) -> dict | None:
        """Return {"user_id": "..."} if the token exists, else None."""
        val = await self.redis.get(f"rt:{token_hash}")
        return {"user_id": val.decode()} if val else None

    async def delete(self, token_hash: str) -> None:
        """Delete a single refresh token (called on rotation or logout)."""
        await self.redis.delete(f"rt:{token_hash}")

    async def revoke_all_for_user(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user (POST /auth/revoke-all).
        Implement with a user→tokens reverse index for full support."""
        pass

auth = FastAuth(
    user_model=User,
    jwt_secret="...",
    token_store=RedisTokenStore(redis_client),
)
```

---

## Exception reference

All exceptions are subclasses of `fastauth.exceptions.AuthException` which extends
`fastapi.HTTPException`. They are automatically handled by FastAPI and return
structured JSON responses.

| Exception | HTTP status | Default message |
|-----------|-------------|-----------------|
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

Import from `fastauth.exceptions`:
```python
from fastauth.exceptions import PermissionDeniedError, UserNotFoundError
```

---

## Security

| Feature | Implementation |
|---------|----------------|
| Password hashing | bcrypt (cost 12) or argon2; timing-safe verify |
| JWT | Per-token `jti` in-memory blacklist on logout |
| Refresh rotation | Old token revoked the moment a new pair is issued |
| Brute-force protection | Sliding-window: 5 failed attempts → 5-min IP lockout |
| Email enumeration | Reset + resend always return 200 regardless of email existence |
| Timing attacks | Dummy hash verify on unknown usernames |
| Cookie flags | `httpOnly`, `secure`, `sameSite` — all configurable |
| Reset tokens | 1-hour expiry, single-use (deleted on confirm) |
| Verify tokens | 24-hour expiry, single-use |

---

## CLI

```bash
# Generate a complete project
fastauth --default-setup sqlite              # Tortoise ORM + SQLite (async)
fastauth --default-setup sqlite --sync       # SQLAlchemy sync + SQLite
fastauth --default-setup sqlalchemy --async  # SQLAlchemy async + SQLite
fastauth --default-setup sqlalchemy --sync   # SQLAlchemy sync  + SQLite
fastauth --default-setup postgresql --async  # SQLAlchemy async + PostgreSQL
fastauth --default-setup postgresql --sync   # SQLAlchemy sync  + PostgreSQL

# Other commands
fastauth init       # scaffold .env.example + auth_config.py
fastauth version    # print installed version
```

Each `--default-setup` generates three files: `database.py` + `models.py` + `main.py`.

---

## Development Tips

**Test email flows without SMTP:**

```python
@app.post("/dev/verify-token")    # REMOVE IN PRODUCTION
async def dev_verify_token(email: str):
    user  = await auth.manager.get_by_email(email)
    token = await auth.manager.create_verification_token(user)
    return {"token": token, "url": f"/auth/verify-email?token={token}"}

@app.post("/dev/reset-token")     # REMOVE IN PRODUCTION
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

**Full reset via curl:**

```bash
# 1. Request reset
curl -X POST http://localhost:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'

# 2. Get token from dev endpoint (or dev-mode email)
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
