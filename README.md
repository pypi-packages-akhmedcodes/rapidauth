# FastAuth

**Professional plug-and-play authentication framework for FastAPI.**

[![PyPI version](https://img.shields.io/pypi/v/fastauth-framework?color=6366f1&label=PyPI&style=flat-square)](https://pypi.org/project/fastauth-framework/)
[![Python](https://img.shields.io/pypi/pyversions/fastauth-framework?color=22d3ee&style=flat-square)](https://pypi.org/project/fastauth-framework/)
[![Downloads](https://img.shields.io/pypi/dm/fastauth-framework?color=34d399&style=flat-square)](https://pypi.org/project/fastauth-framework/)
[![License: MIT](https://img.shields.io/badge/license-MIT-fbbf24?style=flat-square)](LICENSE)
[![Author](https://img.shields.io/badge/author-akhmedcodes-6366f1?style=flat-square)](https://beacons.ai/akhmedcodes)

---

## Goal

Django-level auth simplicity with FastAPI performance.  
One import. One line. Full auth system.

```python
from fastauth import FastAuth

auth = FastAuth(user_model=User, jwt_secret="your-secret")
app.include_router(auth.router)
```

---

## Install

```bash
pip install fastauth-framework

# With Tortoise ORM (recommended for async):
pip install "fastauth-framework[tortoise]"

# With SQLAlchemy / SQLModel:
pip install "fastauth-framework[sqlalchemy]"

# Everything:
pip install "fastauth-framework[all]"
```

---

## Quick Start — CLI scaffold

The fastest way to get started:

```bash
# SQLite
fastauth --default-setup sqlite              # Tortoise ORM + SQLite (async, default)
fastauth --default-setup sqlite --async      # Tortoise ORM + SQLite (async)
fastauth --default-setup sqlite --sync       # SQLAlchemy sync + SQLite

# SQLAlchemy
fastauth --default-setup sqlalchemy          # SQLAlchemy + SQLite (async, default)
fastauth --default-setup sqlalchemy --async  # SQLAlchemy async + SQLite
fastauth --default-setup sqlalchemy --sync   # SQLAlchemy sync  + SQLite

# PostgreSQL
fastauth --default-setup postgresql          # SQLAlchemy + PostgreSQL (async, default)
fastauth --default-setup postgresql --async  # SQLAlchemy async + PostgreSQL (asyncpg)
fastauth --default-setup postgresql --sync   # SQLAlchemy sync  + PostgreSQL (psycopg2)
```

Each command generates: `database.py` + `models.py` + `main.py`

---

## Minimal Example

```python
from fastapi import FastAPI, Depends
from fastauth import FastAuth

# 1. Define your User model (any ORM)
class User(Model):
    id       = fields.IntField(pk=True)
    username = fields.CharField(max_length=100, unique=True)
    email    = fields.CharField(max_length=254, unique=True)
    password = fields.CharField(max_length=200)

# 2. Create FastAuth
app  = FastAPI()
auth = FastAuth(user_model=User, jwt_secret="super-secret")

# 3. Mount router — done!
app.include_router(auth.router)

# 4. Protect your routes
@app.get("/profile")
async def profile(user=Depends(auth.get_current_user())):
    return {"username": user.username}
```

**Auto-registered endpoints:**

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | — | Create account, return token pair |
| POST | `/auth/login` | — | Login with username or email + password |
| GET | `/auth/me` | Bearer | Return current authenticated user |
| POST | `/auth/refresh` | Refresh token | Issue new token pair, rotate old refresh |
| POST | `/auth/logout` | Bearer | Blacklist current access token |
| POST | `/auth/change-password` | Bearer | Change password (requires old password) |
| POST | `/auth/reset-password` | — | Request password reset email |
| **GET** | **`/auth/reset-password/confirm`** | — | **Show HTML reset form** (user clicks email link) |
| POST | `/auth/reset-password/confirm` | — | Submit token + new password |
| GET | `/auth/verify-email` | — | backend: verify + HTML page · frontend: 302 redirect |
| POST | `/auth/verify-email` | — | Programmatic verify (frontend calls after redirect) |
| POST | `/auth/resend-verification` | Bearer **or email body** | Re-send verification email |
| POST | `/auth/revoke-all` | Bearer | Revoke all refresh tokens for this user |
| GET | `/auth/{provider}/login` | — | Redirect to OAuth2 provider |
| GET | `/auth/{provider}/callback` | — | Handle OAuth2 callback, return token pair |

---

## Tortoise ORM Example

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

    class Meta:
        table = "users"

app  = FastAPI()
auth = FastAuth(user_model=User, jwt_secret="super-secret-key-32chars!!")
app.include_router(auth.router)

register_tortoise(app, db_url="sqlite://./app.db",
                  modules={"models": ["__main__"]}, generate_schemas=True)

get_current_user = auth.get_current_user()

@app.get("/profile")
async def profile(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username}
```

---

## Advanced Example

```python
auth = FastAuth(
    user_model=User,

    # Custom field names (if your model uses different names)
    username_field="login",
    email_field="mail",
    password_field="passwd",

    # JWT
    jwt={
        "secret": "your-long-secret-key",
        "algorithm": "HS256",
        "access_expire": 900,      # 15 min
        "refresh_expire": 604800,  # 7 days
    },

    # Refresh token delivery: "body" | "cookie" | "both"
    refresh_token_mode="cookie",

    # Cookie settings
    cookie={"httponly": True, "secure": True, "samesite": "lax"},

    # Password hashing: "bcrypt" (default) | "argon2"
    password_hasher="argon2",

    # Email (for verification + password reset)
    email={
        "host": "smtp.gmail.com",
        "port": 587,
        "username": "you@gmail.com",
        "password": "app-password",
        "from_email": "you@gmail.com",
    },

    # Social OAuth
    social_auth={
        "google": {
            "client_id":     "...",
            "client_secret": "...",
            "redirect_uri":  "http://localhost:8000/auth/google/callback",
        },
        "github": {
            "client_id":     "...",
            "client_secret": "...",
            "redirect_uri":  "http://localhost:8000/auth/github/callback",
        },
    },

    # URLs
    base_url="https://api.myapp.com",      # backend URL for email links
    frontend_url="https://myapp.com",       # SPA URL (used with verify_type='frontend')
    verify_type="frontend",                 # 'backend' | 'frontend'

    # Custom URL for password-reset emails — token appended as ?token=TOKEN
    # If not set, defaults to {base_url}/auth/reset-password/confirm?token=TOKEN
    reset_password_url="https://myapp.com/reset-password",

    # Require email verification before login
    email_verification_required=True,
)
```

---

## Role-Based Access Control (RBAC)

```python
from fastapi import Depends
from fastauth.exceptions import PermissionDeniedError

def require_role(*roles):
    async def dep(user=Depends(auth.get_current_user())):
        for role in roles:
            if role not in (user.roles or []):
                raise PermissionDeniedError(f"Role '{role}' required")
        return user
    return dep

@app.get("/admin")
async def admin(user=Depends(require_role("admin"))):
    return {"message": f"Hello, {user.username}"}
```

---

## SQLAlchemy / SQLModel

FastAuth auto-detects whether your session is **async** or **sync** at runtime.

### Async (recommended)

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

engine = create_async_engine("sqlite+aiosqlite:///./app.db")
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session  # generator — FastAPI handles lifecycle

auth = FastAuth(user_model=User, jwt_secret="your-secret", get_db=get_db)
```

### Sync

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

> **Note:** sync sessions block the FastAPI event loop. Use async for production.

---

## User Manager API

```python
# Create user programmatically
user = await auth.create_user("alice", "alice@example.com", "password123")

# Authenticate
user = await auth.authenticate("alice", "password123")

# Hash / verify
hashed = auth.hash_password("mypassword")
ok     = auth.verify_password("mypassword", hashed)

# Token pair
access, refresh = await auth.manager.create_token_pair(user)
```

---

## Middleware — `request.state.user`

```python
auth.add_middleware(app)

@app.get("/")
async def home(request: Request):
    if request.state.user.is_authenticated:
        return {"hello": request.state.user.username}
    return {"hello": "anonymous"}
```

---

## Email Setup (Password Reset & Verification)

Without email config the endpoints still work, but **no email is sent**.  
To enable real delivery, pass the `email` dict, set `base_url` / `frontend_url`, and choose `verify_type`.

### Password Reset Flow

```
1. POST /auth/reset-password   {"email": "user@example.com"}
   → FastAuth creates a token (1-hour expiry), sends reset email
   → Always returns 200 (no email enumeration)

2a. Backend mode  (reset_password_url not set)
    Email link: GET {base_url}/auth/reset-password/confirm?token=TOKEN
    → FastAuth shows a styled HTML form for entering a new password
    → User submits form → POST /auth/reset-password/confirm   (via JavaScript fetch)

2b. Frontend mode  (reset_password_url set)
    Email link: GET {reset_password_url}?token=TOKEN
    → Your SPA reads ?token= from URL
    → SPA calls POST /auth/reset-password/confirm {"token":"...","new_password":"..."}

3. POST /auth/reset-password/confirm  {"token": "...", "new_password": "NewPass1!"}
   → Token verified, password updated, token invalidated
```

### Email Verification Flow

```
1. POST /auth/register
   → Account created, verification email sent (if email_verification_required=True)
   → Token expires in 24 hours

2. User clicks link in email
   → verify_type='backend': GET /auth/verify-email?token=TOKEN
        FastAuth verifies token and shows HTML "Email Verified!" page
   → verify_type='frontend': email link goes to {frontend_url}/...
        Your SPA reads token, calls POST /auth/verify-email {"token":"..."}

3. Re-send verification:
   POST /auth/resend-verification
   → With Bearer token:  {"Authorization": "Bearer <access_token>"}
   → Without token:      {"email": "user@example.com"}   (no auth required)
   → Always returns generic message (prevents enumeration)
```

### `verify_type` — backend vs frontend

| `verify_type` | Email link points to | `GET /auth/verify-email?token=…` |
|---|---|---|
| `'backend'` (default) | `{base_url}/auth/verify-email?token=…` | Verifies token, shows **HTML success page** |
| `'frontend'` | `{frontend_url}/auth/verify-email?token=…` | **302 redirect** to frontend; frontend calls `POST /auth/verify-email` |

### `reset_password_url` — custom reset link

```python
# Backend mode (default) — email link → GET /auth/reset-password/confirm?token=TOKEN
# FastAuth shows an HTML form, user enters new password, form POSTs via JavaScript
auth = FastAuth(
    ...
    base_url="http://localhost:8000",
)

# Frontend / SPA mode — email link → your custom reset page
auth = FastAuth(
    ...
    reset_password_url="https://myapp.com/reset-password",
    # Email link becomes: https://myapp.com/reset-password?token=TOKEN
)
```

### Backend mode (default) — full stack or API-only

```python
auth = FastAuth(
    user_model=User,
    jwt_secret="your-secret",
    email={
        "host":       "smtp.gmail.com",
        "port":       587,
        "username":   "you@gmail.com",
        "password":   "xxxx xxxx xxxx xxxx",  # Gmail App Password
        "from_email": "you@gmail.com",
    },
    base_url="http://localhost:8000",
    verify_type="backend",                     # default
    email_verification_required=True,
)
# Reset email link → GET http://localhost:8000/auth/reset-password/confirm?token=...
# → FastAuth shows HTML form, user enters new password
# → form submits via JavaScript → POST /auth/reset-password/confirm

# Verify email link → GET http://localhost:8000/auth/verify-email?token=...
# → FastAuth verifies token, shows HTML "Email Verified!" page
```

### Frontend mode — SPA (React, Vue, Next.js…)

```python
auth = FastAuth(
    user_model=User,
    jwt_secret="your-secret",
    email={
        "host":       "smtp.gmail.com",
        "port":       587,
        "username":   "you@gmail.com",
        "password":   "xxxx xxxx xxxx xxxx",
        "from_email": "you@gmail.com",
    },
    base_url="https://api.domain.uz",          # your backend
    frontend_url="https://domain.uz",          # your SPA (for verify links)
    verify_type="frontend",
    reset_password_url="https://domain.uz/reset-password",  # SPA reset page
    email_verification_required=True,
)
# Verify email link  → GET https://domain.uz/auth/verify-email?token=...
# Reset email link   → GET https://domain.uz/reset-password?token=...
```

### Frontend flow (what your SPA does)

```javascript
// Email verification — user lands on /verify-email?token=...
const token = new URLSearchParams(window.location.search).get("token");
const res = await fetch("https://api.domain.uz/auth/verify-email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
});
const data = await res.json();
// data.message === "Email verified successfully"

// Password reset — user lands on /reset-password?token=...
const token = new URLSearchParams(window.location.search).get("token");
await fetch("https://api.domain.uz/auth/reset-password/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: "NewPass123!" }),
});
```

### Gmail — App Password (step by step)

> Gmail blocks plain passwords for SMTP. You need an **App Password**.

1. Go to **myaccount.google.com** → **Security**
2. Enable **2-Step Verification** (required)
3. Go to **Security** → **App passwords**
4. Select app: **Mail** / device: **Other** → name it `fastauth`
5. Copy the generated 16-character password → paste as `"password"` above

### Other SMTP providers

| Provider | host | port | note |
|---|---|---|---|
| Gmail | `smtp.gmail.com` | 587 | App Password required |
| Outlook / Hotmail | `smtp.office365.com` | 587 | regular password |
| Yahoo Mail | `smtp.mail.yahoo.com` | 587 | App Password required |
| Yandex | `smtp.yandex.com` | 587 | — |
| Mailgun | `smtp.mailgun.org` | 587 | SMTP credentials from dashboard |
| SendGrid | `smtp.sendgrid.net` | 587 | username=`apikey`, password=API key |
| Amazon SES | `email-smtp.<region>.amazonaws.com` | 587 | SMTP credentials from AWS Console |
| Custom VPS | your server hostname | 25 / 587 / 465 | port 465 → `use_ssl: True` |

### Testing without real SMTP

While developing, get the reset token directly from the manager:

```python
@app.post("/dev/reset-token")          # remove in production!
async def dev_reset_token(email: str):
    token = await auth._manager.create_reset_token(email)
    return {"token": token}            # use this in /auth/reset-password/confirm
```

---

## Social Auth

Adds OAuth2 routes automatically:

```
GET  /auth/google/login      → redirect to Google
GET  /auth/google/callback   → exchange code, create/login user, return tokens
```

Same pattern for `github`, `discord`.

---

## Configuration Reference

All parameters are optional except `user_model` and `jwt_secret`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `user_model` | `type` | required | Your ORM User model class |
| `jwt_secret` | `str` | required | Secret key for signing JWTs (min 16 chars) |
| `jwt` | `dict` | `None` | `secret`, `algorithm`, `access_expire`, `refresh_expire` |
| `username_field` | `str` | `"username"` | Field name for username in your model |
| `email_field` | `str` | `"email"` | Field name for email in your model |
| `password_field` | `str` | `"password"` | Field name for hashed password |
| `password_hasher` | `str` | `"bcrypt"` | `"bcrypt"` or `"argon2"` |
| `refresh_token_mode` | `str` | `"body"` | `"body"` · `"cookie"` · `"both"` |
| `cookie` | `dict` | `{}` | `httponly`, `secure`, `samesite`, `domain` |
| `email` | `dict` | `None` | SMTP: `host`, `port`, `username`, `password`, `from_email` |
| `base_url` | `str` | `"http://localhost:8000"` | Backend URL for email verification links |
| `frontend_url` | `str` | `None` | SPA URL; used when `verify_type="frontend"` |
| `verify_type` | `str` | `"backend"` | `"backend"` verify directly · `"frontend"` redirect to SPA |
| `reset_password_url` | `str` | `None` | Custom URL for reset emails. Token appended as `?token=TOKEN`. If not set, defaults to `{base_url}/auth/reset-password/confirm` where a built-in HTML form is served |
| `email_verification_required` | `bool` | `False` | Block login until email is verified |
| `social_auth` | `dict` | `None` | OAuth providers: `google`, `github`, `discord` |
| `get_db` | `callable` | `None` | FastAPI dependency yielding DB session (SQLAlchemy async or sync) |
| `router_prefix` | `str` | `"/auth"` | URL prefix for all auth endpoints |
| `rate_limit` | `dict` | `{}` | `enabled`, `max_login_attempts`, `lockout_seconds` |
| `token_store` | `any` | `None` | Custom token store (e.g. Redis). Must implement `save/get/delete/revoke_all` |

---

## Security

| Feature | Details |
|---|---|
| Password hashing | bcrypt (cost 12) or argon2 |
| JWT tokens | Per-token `jti`, in-memory blacklist |
| Refresh rotation | Old refresh token revoked on use |
| Brute-force protection | Sliding-window rate limiter (5 attempts / 5 min) |
| Email enumeration | Password reset always returns 200 |
| Timing attacks | Dummy hash verify on unknown username |
| Cookie flags | `httponly`, `secure`, `samesite` configurable |
| Reset form | GET `/auth/reset-password/confirm` serves HTML form, not raw JSON |

---

## CLI

```bash
# SQLite
fastauth --default-setup sqlite              # Tortoise ORM async (default)
fastauth --default-setup sqlite --async      # Tortoise ORM + aiosqlite
fastauth --default-setup sqlite --sync       # SQLAlchemy sync + sqlite3

# SQLAlchemy + SQLite
fastauth --default-setup sqlalchemy          # async (default)
fastauth --default-setup sqlalchemy --async  # SQLAlchemy async + aiosqlite
fastauth --default-setup sqlalchemy --sync   # SQLAlchemy sync  + sqlite3

# PostgreSQL
fastauth --default-setup postgresql          # async (default)
fastauth --default-setup postgresql --async  # SQLAlchemy async + asyncpg
fastauth --default-setup postgresql --sync   # SQLAlchemy sync  + psycopg2

# Other
fastauth init                                # scaffold .env.example + auth_config.py
fastauth version                             # print installed version
```

> Default mode is `--async`. Use `--sync` only for simple scripts or prototypes —
> sync DB calls block the FastAPI event loop.

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
