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

| Endpoint | Method | Auth |
|---|---|---|
| `/auth/register` | POST | — |
| `/auth/login` | POST | — |
| `/auth/me` | GET | Bearer |
| `/auth/refresh` | POST | Refresh token |
| `/auth/logout` | POST | Bearer |
| `/auth/change-password` | POST | Bearer |
| `/auth/reset-password` | POST | — |
| `/auth/reset-password/confirm` | POST | — |
| `/auth/verify-email` | POST | — |
| `/auth/revoke-all` | POST | Bearer |

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

    # Base URL for email links
    base_url="https://myapp.com",

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

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

engine = create_async_engine("sqlite+aiosqlite:///./app.db")
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session  # generator — FastAPI handles the lifecycle

auth = FastAuth(
    user_model=User,
    jwt_secret="secret",
    get_db=get_db,   # ← pass session dependency
)
```

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

## Social Auth

Adds OAuth2 routes automatically:

```
GET  /auth/google/login      → redirect to Google
GET  /auth/google/callback   → exchange code, create/login user, return tokens
```

Same pattern for `github`, `discord`.

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
| Cookie flags | httponly, secure, samesite configurable |

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
