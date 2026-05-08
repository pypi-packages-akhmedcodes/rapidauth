"""
test/main.py — Full FastAPI + FastAuth demo application.

Features demonstrated:
  - User registration & login
  - JWT access + refresh tokens
  - get_current_user dependency
  - Protected routes
  - Role-based access control
  - Password reset flow
  - Tortoise ORM + SQLite

Run:
    pip install "fastauth[tortoise]" uvicorn[standard]

    uvicorn test.main:app --reload
    # (from project root)

Then open: http://localhost:8000/docs

Default accounts (created on startup):
  admin / Admin1234!   → roles: ["admin"]
  alice / Alice1234!   → roles: ["user"]
"""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from tortoise import fields
from tortoise.contrib.fastapi import register_tortoise
from tortoise.models import Model

from fastauth import FastAuth
from fastauth.exceptions import PermissionDeniedError

# ── Database model ────────────────────────────────────────────────────────────


class User(Model):
    """Application user model. Field names match FastAuth defaults."""

    id: int = fields.IntField(pk=True)
    username: str = fields.CharField(max_length=100, unique=True)
    email: str = fields.CharField(max_length=254, unique=True)
    password: str = fields.CharField(max_length=200)
    is_active: bool = fields.BooleanField(default=True)
    is_verified: bool = fields.BooleanField(default=True)
    roles: list = fields.JSONField(default=list)
    permissions: list = fields.JSONField(default=list)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "users"

    def __str__(self) -> str:
        return f"<User id={self.id} username={self.username}>"


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="FastAuth Demo",
    description="Complete authentication demo using FastAuth + Tortoise ORM",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Tortoise ORM (registered BEFORE startup hook so it inits first) ───────────

register_tortoise(
    app,
    db_url="sqlite://./fastauth_demo.db",
    modules={"models": ["test.main"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

# ── FastAuth setup ────────────────────────────────────────────────────────────

auth = FastAuth(
    user_model=User,
    jwt_secret="super-secret-key-change-in-production-please-32chars",
    jwt={
        "secret": "super-secret-key-change-in-production-please-32chars",
        "algorithm": "HS256",
        "access_expire": 900,        # 15 minutes
        "refresh_expire": 604800,    # 7 days
    },
    password_hasher="bcrypt",
    refresh_token_mode="body",
    email_verification_required=False,
    router_prefix="/auth",
    router_tags=["Authentication"],
)

app.include_router(auth.router)
auth.add_middleware(app)

# ── Dependency shortcuts ──────────────────────────────────────────────────────

get_current_user = auth.get_current_user()


def require_role(*roles: str):
    async def dep(user: User = Depends(get_current_user)) -> User:
        user_roles: list = user.roles or []
        for role in roles:
            if role not in user_roles:
                raise PermissionDeniedError(f"Role '{role}' required")
        return user
    return dep


# ── Public routes ─────────────────────────────────────────────────────────────


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "FastAuth Demo",
        "docs": "/docs",
        "endpoints": [
            "POST /auth/register",
            "POST /auth/login",
            "GET  /auth/me",
            "POST /auth/refresh",
            "POST /auth/logout",
            "POST /auth/change-password",
            "POST /auth/reset-password",
            "POST /auth/reset-password/confirm",
            "POST /auth/verify-email",
        ],
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


# ── Protected routes ──────────────────────────────────────────────────────────


@app.get("/profile", tags=["User"])
async def profile(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "roles": user.roles,
        "created_at": str(user.created_at),
    }


@app.get("/dashboard", tags=["User"])
async def dashboard(user: User = Depends(get_current_user)):
    return {"message": f"Welcome, {user.username}!"}


# ── Admin routes ──────────────────────────────────────────────────────────────


@app.get("/admin", tags=["Admin"])
async def admin_panel(user: User = Depends(require_role("admin"))):
    return {"message": f"Admin panel — hello {user.username}", "roles": user.roles}


@app.post("/admin/promote/{username}", tags=["Admin"])
async def promote_user(
    username: str,
    role: str,
    admin: User = Depends(require_role("admin")),
):
    target = await User.get_or_none(username=username)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    roles: list = list(target.roles or [])
    if role not in roles:
        roles.append(role)
        target.roles = roles
        await target.save()
    return {"message": f"Role '{role}' granted to {username}", "roles": roles}


@app.post("/admin/ban/{username}", tags=["Admin"])
async def ban_user(username: str, admin: User = Depends(require_role("admin"))):
    target = await User.get_or_none(username=username)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = False
    await target.save()
    return {"message": f"User '{username}' has been banned"}


@app.get("/admin/users", tags=["Admin"])
async def list_users(admin: User = Depends(require_role("admin"))):
    users = await User.all()
    return [
        {"id": u.id, "username": u.username, "email": u.email,
         "is_active": u.is_active, "roles": u.roles}
        for u in users
    ]


# ── Seed default accounts ──────────────────────────────────────────────────────
# Registered AFTER register_tortoise so Tortoise inits before this hook runs.


@app.on_event("startup")
async def seed_defaults() -> None:
    if not await User.exists(username="admin"):
        await auth.create_user(
            username="admin",
            email="admin@example.com",
            password="Admin1234!",
            extra={"roles": ["admin"], "permissions": ["users.read", "users.write"]},
        )
        print("Created: admin / Admin1234!")

    if not await User.exists(username="alice"):
        await auth.create_user(
            username="alice",
            email="alice@example.com",
            password="Alice1234!",
            extra={"roles": ["user"]},
        )
        print("Created: alice / Alice1234!")
