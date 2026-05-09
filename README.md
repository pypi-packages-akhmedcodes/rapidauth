# FastAuth

**Professional plug-and-play authentication framework for FastAPI.**

[![PyPI version](https://img.shields.io/pypi/v/fastauth-framework?color=6366f1&label=PyPI&style=flat-square)](https://pypi.org/project/fastauth-framework/)
[![Python](https://img.shields.io/pypi/pyversions/fastauth-framework?color=22d3ee&style=flat-square)](https://pypi.org/project/fastauth-framework/)
[![Downloads](https://img.shields.io/pypi/dm/fastauth-framework?color=34d399&style=flat-square)](https://pypi.org/project/fastauth-framework/)
[![License: MIT](https://img.shields.io/badge/license-MIT-fbbf24?style=flat-square)](LICENSE)
[![Author](https://img.shields.io/badge/author-akhmedcodes-6366f1?style=flat-square)](https://beacons.ai/akhmedcodes)

FastAuth is a **pure backend** authentication framework. It exposes a clean JSON REST API — no HTML pages, no form rendering. You plug it into FastAPI and immediately get a complete, production-grade auth system. Your frontend (React, Vue, Next.js, mobile app) talks to the endpoints over HTTP.

---

## Philosophy

- **Backend only.** Every endpoint returns JSON. Your frontend handles the UI.
- **Zero configuration to start.** One line mounts the full auth system.
- **Scales from dev to production.** Sensible defaults during development; explicit configuration for production.
- **ORM-agnostic.** Tortoise ORM, SQLAlchemy async, SQLAlchemy sync — auto-detected.
- **Secure by default.** bcrypt/argon2, refresh rotation, rate limiting, token blacklisting out of the box.

---

## Install

```bash
pip install fastauth-framework

# Tortoise ORM (recommended for async):
pip install "fastauth-framework[tortoise]"

# SQLAlchemy async or sync:
pip install "fastauth-framework[sqlalchemy]"

# Everything:
pip install "fastauth-framework[all]"
```

---

## Quickstart

```python
from fastapi import FastAPI, Depends
from fastauth import FastAuth
from your_models import User          # any ORM model

app  = FastAPI()
auth = FastAuth(user_model=User, jwt_secret="your-secret-min-32-chars")
app.include_router(auth.router)

# Protected route
get_current_user = auth.get_current_user()

@app.get("/profile")
async def profile(user = Depends(get_current_user)):
    return {"id": user.id, "username": user.username}
```

That one `include_router` call mounts **14 endpoints** instantly.

---

## CLI Scaffold

Generate a complete project in seconds:

```bash
fastauth --default-setup sqlite              # Tortoise ORM + SQLite (async)
fastauth --default-setup sqlalchemy --async  # SQLAlchemy async + SQLite
fastauth --default-setup postgresql --async  # SQLAlchemy async + PostgreSQL
fastauth --default-setup postgresql --sync   # SQLAlchemy sync  + PostgreSQL
```

Each command writes `database.py` + `models.py` + `main.py`.

---

## All Endpoints

Mounted under `/auth` by default (configurable via `router_prefix`).

| Method | Endpoint | Auth required | Description |
|--------|----------|---------------|-------------|
| `POST` | `/auth/register` | — | Create account, returns token pair |
| `POST` | `/auth/login` | — | Login with username **or** email + password |
| `GET` | `/auth/me` | Bearer | Return current user |
| `POST` | `/auth/refresh` | Refresh token | Issue new token pair; old refresh token revoked |
| `POST` | `/auth/logout` | Bearer | Blacklist current access token |
| `POST` | `/auth/change-password` | Bearer | Change password (old password required) |
| `POST` | `/auth/reset-password` | — | Request password reset email |
| `POST` | `/auth/reset-password/confirm` | — | Confirm reset with token + new password |
| `GET` | `/auth/verify-email?token=…` | — | Verify email inline — returns JSON |
| `POST` | `/auth/verify-email` | — | Verify email with token in body |
| `POST` | `/auth/resend-verification` | Bearer **or** email body | Resend verification email |
| `POST` | `/auth/revoke-all` | Bearer | Revoke all refresh tokens for this user |
| `GET` | `/auth/{provider}/login` | — | Redirect to OAuth2 provider |
| `GET` | `/auth/{provider}/callback` | — | Handle OAuth2 callback, return token pair |

---

## Tortoise ORM

```python
from fastapi import FastAPI, Depends
from tortoise import fields
from tortoise.contrib.fastapi import register_tortoise
from tortoise.models import Model
from fastauth import FastAuth

class User(Model):
    id          = fields.IntField(pk=True)
    username    = fields.CharField(max_length=100, unique=True)
    email       = fields.CharField(max_length=254, unique=True)
    password    = fields.CharField(max_length=200)
    is_active   = fields.BooleanField(default=True)
    is_verified = fields.BooleanField(default=True)
    roles       = fields.JSONField(default=list)
    permissions = fields.JSONField(default=list)

    class Meta:
        table = "users"

app  = FastAPI()
auth = FastAuth(user_model=User, jwt_secret="super-secret-key-32chars!!")
app.include_router(auth.router)

register_tortoise(
    app,
    db_url="sqlite://./app.db",
    modules={"models": ["__main__"]},
    generate_schemas=True,
)
```

---

## SQLAlchemy Async (recommended for production)

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
auth = FastAuth(user_model=User, jwt_secret="super-secret-key-32chars!!", get_db=get_db)
app.include_router(auth.router)
```

---

## SQLAlchemy Sync

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

> **Note:** sync sessions block the event loop. Use async for production.

---

## Full Configuration

```python
auth = FastAuth(
    user_model=User,

    # ── JWT ───────────────────────────────────────────────────────────────────
    jwt_secret="your-long-secret-key-at-least-32-chars",   # shorthand
    # — or full dict —
    jwt={
        "secret":         "your-long-secret-key-at-least-32-chars",
        "algorithm":      "HS256",     # default
        "access_expire":  900,         # seconds, default 15 min
        "refresh_expire": 604800,      # seconds, default 7 days
    },

    # ── Field name overrides (if your model uses different names) ─────────────
    username_field="login",
    email_field="mail",
    password_field="passwd",
    id_field="id",
    is_active_field="is_active",
    is_verified_field="is_verified",
    roles_field="roles",
    permissions_field="permissions",

    # ── Token delivery ────────────────────────────────────────────────────────
    refresh_token_mode="body",      # "body" | "cookie" | "both"

    # ── Cookie (when refresh_token_mode is "cookie" or "both") ───────────────
    cookie={
        "httponly": True,
        "secure":   True,           # True in production (HTTPS)
        "samesite": "lax",          # "lax" | "strict" | "none"
        "domain":   None,
        "max_age":  None,           # defaults to refresh_token_expire
    },

    # ── Password hashing ──────────────────────────────────────────────────────
    password_hasher="bcrypt",       # "bcrypt" (default) | "argon2"

    # ── Email ─────────────────────────────────────────────────────────────────
    email={
        "host":       "smtp.gmail.com",
        "port":       587,
        "username":   "you@gmail.com",
        "password":   "xxxx xxxx xxxx xxxx",   # Gmail App Password
        "from_email": "you@gmail.com",
        "use_tls":    True,         # STARTTLS (default)
        "use_ssl":    False,        # SSL — use port 465 if True
        "timeout":    30,
    },

    # ── URL config ────────────────────────────────────────────────────────────
    # base_url        : URL of this backend. Used as fallback for email links.
    base_url="https://api.myapp.com",

    # verify_email_url: Where email verification links point.
    #   Default (None) → {base_url}/auth/verify-email?token=TOKEN
    #   GET /auth/verify-email always returns JSON — clickable in dev, called
    #   programmatically by the frontend in production.
    #   Production: set to your frontend verify page.
    verify_email_url="https://myapp.com/verify-email",

    # reset_password_url: Where password-reset email links point.
    #   Default (None) → dev mode: email shows raw token + curl example.
    #   Production: set to your frontend reset page.
    reset_password_url="https://myapp.com/reset-password",

    # ── Feature flags ─────────────────────────────────────────────────────────
    email_verification_required=True,   # block login until email verified
    enable_refresh_rotation=True,        # revoke old refresh on use (default)

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit={
        "enabled":           True,
        "max_login_attempts": 5,
        "lockout_seconds":   300,   # 5-minute lockout
    },

    # ── Social OAuth ──────────────────────────────────────────────────────────
    social_auth={
        "google": {
            "client_id":     "...",
            "client_secret": "...",
            "redirect_uri":  "https://api.myapp.com/auth/google/callback",
        },
        "github": {
            "client_id":     "...",
            "client_secret": "...",
            "redirect_uri":  "https://api.myapp.com/auth/github/callback",
        },
        "discord": {
            "client_id":     "...",
            "client_secret": "...",
            "redirect_uri":  "https://api.myapp.com/auth/discord/callback",
        },
    },

    # ── Router ────────────────────────────────────────────────────────────────
    router_prefix="/auth",          # default
    router_tags=["Authentication"], # default

    # ── SQLAlchemy session dependency ─────────────────────────────────────────
    get_db=get_db,                  # omit for Tortoise ORM

    # ── Custom token store (e.g. Redis) ───────────────────────────────────────
    token_store=None,               # defaults to in-memory store
)
```

---

## Configuration Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `user_model` | `type` | **required** | Your ORM model class |
| `jwt_secret` | `str` | **required** | JWT signing secret (min 16 chars) |
| `jwt` | `dict` | `None` | Full JWT config: `secret`, `algorithm`, `access_expire`, `refresh_expire` |
| `username_field` | `str` | `"username"` | Field name for username in your model |
| `email_field` | `str` | `"email"` | Field name for email |
| `password_field` | `str` | `"password"` | Field name for hashed password |
| `id_field` | `str` | `"id"` | Field name for primary key |
| `is_active_field` | `str` | `"is_active"` | Field name for active flag |
| `is_verified_field` | `str` | `"is_verified"` | Field name for verified flag |
| `roles_field` | `str` | `"roles"` | Field name for roles list |
| `permissions_field` | `str` | `"permissions"` | Field name for permissions list |
| `refresh_token_mode` | `str` | `"body"` | `"body"` · `"cookie"` · `"both"` |
| `cookie` | `dict` | `{}` | Cookie flags: `httponly`, `secure`, `samesite`, `domain`, `max_age` |
| `password_hasher` | `str` | `"bcrypt"` | `"bcrypt"` or `"argon2"` |
| `email` | `dict` | `None` | SMTP config: `host`, `port`, `username`, `password`, `from_email`, `use_tls`, `use_ssl`, `timeout` |
| `base_url` | `str` | `"http://localhost:8000"` | Backend URL; used as fallback base for email links |
| `verify_email_url` | `str` | `None` | URL for verification email links. Token appended as `?token=TOKEN`. Default → `{base_url}/auth/verify-email` |
| `reset_password_url` | `str` | `None` | URL for reset email links. Token appended as `?token=TOKEN`. Default → dev mode email (raw token shown) |
| `email_verification_required` | `bool` | `False` | Block login until email is verified |
| `enable_refresh_rotation` | `bool` | `True` | Revoke old refresh token when issuing a new pair |
| `rate_limit` | `dict` | `{}` | `enabled`, `max_login_attempts`, `lockout_seconds` |
| `social_auth` | `dict` | `None` | OAuth: `google`, `github`, `discord` |
| `get_db` | `callable` | `None` | FastAPI dependency yielding DB session (SQLAlchemy) |
| `router_prefix` | `str` | `"/auth"` | URL prefix for all auth endpoints |
| `router_tags` | `list` | `["Authentication"]` | OpenAPI tags |
| `token_store` | `any` | `None` | Custom token store. Must implement `save/get/delete/revoke_all_for_user` |

---

## Email Setup

Without `email` config the auth endpoints still work — no emails are sent, and tokens can be tested directly via the API (Swagger/curl). Add the `email` dict when you're ready to test real email delivery.

### Password reset flow

```
Development (reset_password_url not set):
  POST /auth/reset-password  {"email": "user@example.com"}
  → FastAuth creates a 1-hour token
  → Sends a dev email showing the raw token + curl example
  → Use the token directly: POST /auth/reset-password/confirm

Production (reset_password_url set):
  POST /auth/reset-password  {"email": "user@example.com"}
  → FastAuth creates a 1-hour token
  → Sends email with link: {reset_password_url}?token=TOKEN
  → User opens the link, your frontend reads ?token= from URL
  → Frontend calls: POST /auth/reset-password/confirm
                    {"token": "...", "new_password": "NewPass1!"}
```

```python
# Development — no reset_password_url
auth = FastAuth(user_model=User, jwt_secret="...", email={...})
# Reset email shows: token + curl example for Swagger testing

# Production
auth = FastAuth(
    user_model=User, jwt_secret="...", email={...},
    reset_password_url="https://myapp.com/reset-password",
)
# Reset email link → https://myapp.com/reset-password?token=TOKEN
```

### Email verification flow

```
Development (verify_email_url not set):
  POST /auth/register
  → FastAuth sends verification email with link:
    {base_url}/auth/verify-email?token=TOKEN
  → User clicks link → GET /auth/verify-email?token=TOKEN
  → Returns JSON: {"message": "Email verified successfully"}

Production (verify_email_url set):
  POST /auth/register
  → FastAuth sends verification email with link:
    {verify_email_url}?token=TOKEN
  → User opens frontend page, frontend reads ?token= from URL
  → Frontend calls: POST /auth/verify-email  {"token": "..."}
              or:   GET  /auth/verify-email?token=...
  → Both return JSON: {"message": "Email verified successfully"}
```

```python
# Development — no verify_email_url (link goes to backend GET endpoint)
auth = FastAuth(user_model=User, jwt_secret="...", email={...})

# Production
auth = FastAuth(
    user_model=User, jwt_secret="...", email={...},
    verify_email_url="https://myapp.com/verify-email",
)
# Verification email link → https://myapp.com/verify-email?token=TOKEN
```

### Resending verification

```python
# With a Bearer token (user is logged in):
POST /auth/resend-verification
Authorization: Bearer <access_token>

# Without auth (user can't log in because email isn't verified):
POST /auth/resend-verification
{"email": "user@example.com"}

# Always returns 200 with a generic message (no user enumeration)
```

### Gmail App Password

1. **myaccount.google.com** → **Security** → enable **2-Step Verification**
2. Search **App passwords** → App: Mail / Device: Other → name it → **Generate**
3. Copy the 16-character password into `"password"` in your email config

### SMTP providers

| Provider | `host` | `port` | Notes |
|----------|--------|--------|-------|
| Gmail | `smtp.gmail.com` | `587` | App Password required |
| Outlook / Hotmail | `smtp.office365.com` | `587` | Account password |
| Yahoo | `smtp.mail.yahoo.com` | `587` | App Password required |
| Yandex | `smtp.yandex.com` | `587` | — |
| Mailgun | `smtp.mailgun.org` | `587` | Dashboard SMTP creds |
| SendGrid | `smtp.sendgrid.net` | `587` | `username="apikey"`, password=API key |
| Amazon SES | `email-smtp.<region>.amazonaws.com` | `587` | AWS SMTP creds |
| Custom VPS | your hostname | `25`/`587`/`465` | port 465 → `use_ssl=True` |

---

## Role-Based Access Control (RBAC)

```python
from fastapi import Depends
from fastauth.exceptions import PermissionDeniedError

def require_role(*roles: str):
    async def dep(user = Depends(auth.get_current_user())):
        for role in roles:
            if role not in (user.roles or []):
                raise PermissionDeniedError(f"Role '{role}' required")
        return user
    return dep

@app.get("/admin")
async def admin_panel(user = Depends(require_role("admin"))):
    return {"message": f"Hello, {user.username}"}

@app.get("/moderator")
async def mod_panel(user = Depends(require_role("admin", "moderator"))):
    return {"message": "Mod panel"}
```

---

## Auth Middleware

Makes the current user available on every request as `request.state.user` without needing a `Depends`:

```python
auth.add_middleware(app)

@app.get("/")
async def home(request: Request):
    if request.state.user.is_authenticated:
        return {"hello": request.state.user.username}
    return {"hello": "anonymous"}
```

---

## User Manager API

```python
# Create a user programmatically (e.g. seed data)
user = await auth.create_user("alice", "alice@example.com", "password123")
user = await auth.create_user(
    "alice", "alice@example.com", "password123",
    extra={"roles": ["admin"]},
)

# Authenticate
user = await auth.authenticate("alice", "password123")     # username
user = await auth.authenticate("alice@example.com", "password123")  # email

# Password hashing
hashed = auth.hash_password("mypassword")
ok     = auth.verify_password("mypassword", hashed)

# Token operations
access, refresh = await auth.manager.create_token_pair(user)

# Direct manager access
manager = auth.manager
await manager.revoke_all_tokens(user)
```

---

## Social Auth (OAuth2)

Configure providers and the routes are added automatically:

```python
auth = FastAuth(
    user_model=User,
    jwt_secret="...",
    social_auth={
        "google": {
            "client_id":     "YOUR_GOOGLE_CLIENT_ID",
            "client_secret": "YOUR_GOOGLE_SECRET",
            "redirect_uri":  "https://api.myapp.com/auth/google/callback",
        },
        "github": {
            "client_id":     "YOUR_GITHUB_CLIENT_ID",
            "client_secret": "YOUR_GITHUB_SECRET",
            "redirect_uri":  "https://api.myapp.com/auth/github/callback",
        },
    },
)

# Routes added:
# GET /auth/google/login    → redirect to Google
# GET /auth/google/callback → exchange code, create/login user, return tokens
# GET /auth/github/login    → redirect to GitHub
# GET /auth/github/callback → exchange code, create/login user, return tokens
```

OAuth users are created automatically with a random password. `is_verified` is set to `True`.

---

## Custom Token Store (Redis)

By default tokens are stored in memory. Swap in Redis for multi-process/multi-server deployments:

```python
class RedisTokenStore:
    def __init__(self, redis):
        self.redis = redis

    async def save(self, token_hash: str, user_id: str, expires_at) -> None:
        ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        await self.redis.setex(f"rt:{token_hash}", ttl, user_id)

    async def get(self, token_hash: str):
        val = await self.redis.get(f"rt:{token_hash}")
        return {"user_id": val.decode()} if val else None

    async def delete(self, token_hash: str) -> None:
        await self.redis.delete(f"rt:{token_hash}")

    async def revoke_all_for_user(self, user_id: str) -> None:
        pass  # implement with a user→tokens index if needed

auth = FastAuth(
    user_model=User,
    jwt_secret="...",
    token_store=RedisTokenStore(redis_client),
)
```

---

## Security

| Feature | Implementation |
|---------|----------------|
| Password hashing | bcrypt (cost 12) or argon2; timing-safe verify |
| JWT | Per-token `jti`, in-memory blacklist on logout |
| Refresh rotation | Old token revoked the moment a new pair is issued |
| Brute-force protection | Sliding-window: 5 attempts → 5-min IP lockout |
| Email enumeration | Reset + resend always return 200 regardless of email existence |
| Timing attacks | Dummy hash verify on unknown usernames |
| Cookie flags | `httpOnly`, `secure`, `sameSite` — all configurable |
| Reset tokens | 1-hour expiry, single-use (deleted on confirm) |
| Verify tokens | 24-hour expiry, single-use |

---

## Development Tips

**Test email flows without SMTP:**

```python
@app.post("/dev/get-verify-token")   # REMOVE IN PRODUCTION
async def dev_verify_token(email: str):
    user = await auth.manager.get_by_email(email)
    token = await auth.manager.create_verification_token(user)
    return {"token": token, "url": f"/auth/verify-email?token={token}"}

@app.post("/dev/get-reset-token")    # REMOVE IN PRODUCTION
async def dev_reset_token(email: str):
    token = await auth.manager.create_reset_token(email)
    return {"token": token}
```

**Full reset flow via curl:**

```bash
# 1. Request reset
curl -X POST http://localhost:8000/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'

# 2. Get token (dev endpoint above) or from dev-mode email
# 3. Confirm reset
curl -X POST http://localhost:8000/auth/reset-password/confirm \
  -H "Content-Type: application/json" \
  -d '{"token": "TOKEN_HERE", "new_password": "NewPass1!"}'
```

---

## CLI

```bash
fastauth --default-setup sqlite              # Tortoise ORM + SQLite async
fastauth --default-setup sqlite --async      # same
fastauth --default-setup sqlite --sync       # SQLAlchemy sync + SQLite
fastauth --default-setup sqlalchemy --async  # SQLAlchemy async + SQLite
fastauth --default-setup sqlalchemy --sync   # SQLAlchemy sync  + SQLite
fastauth --default-setup postgresql --async  # SQLAlchemy async + asyncpg
fastauth --default-setup postgresql --sync   # SQLAlchemy sync  + psycopg2
fastauth init                                # scaffold .env.example + auth_config.py
fastauth version                             # print version
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
