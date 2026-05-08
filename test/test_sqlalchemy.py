"""
SQLAlchemy adapter tests — both async and sync sessions.
Run: python3.10 test/test_sqlalchemy.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Boolean, Integer, String, JSON, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from fastauth import FastAuth
from fastauth.exceptions import PermissionDeniedError


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users_test"

    id          : Mapped[int]  = mapped_column(Integer, primary_key=True)
    username    : Mapped[str]  = mapped_column(String(100), unique=True)
    email       : Mapped[str]  = mapped_column(String(254), unique=True)
    password    : Mapped[str]  = mapped_column(String(200))
    is_active   : Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified : Mapped[bool] = mapped_column(Boolean, default=True)
    roles       : Mapped[list] = mapped_column(JSON, default=list)
    permissions : Mapped[list] = mapped_column(JSON, default=list)


# ─────────────────────────────────────────────────────────────────────────────
# ASYNC app
# ─────────────────────────────────────────────────────────────────────────────

async_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session


async_app = FastAPI(title="FastAuth Async Test")

async_auth = FastAuth(
    user_model=User,
    jwt_secret="test-secret-async-min-32-chars!!",
    password_hasher="bcrypt",
    refresh_token_mode="body",
    get_db=get_async_db,
)
async_app.include_router(async_auth.router)

get_async_user = async_auth.get_current_user()


@async_app.get("/profile")
async def async_profile(user: User = Depends(get_async_user)):
    return {"username": user.username, "email": user.email}


def require_role_async(*roles):
    async def dep(user: User = Depends(get_async_user)):
        for r in roles:
            if r not in (user.roles or []):
                raise PermissionDeniedError(f"Role '{r}' required")
        return user
    return dep


@async_app.get("/admin")
async def async_admin(user: User = Depends(require_role_async("admin"))):
    return {"msg": f"admin: {user.username}"}


@async_app.on_event("startup")
async def async_create_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ─────────────────────────────────────────────────────────────────────────────
# SYNC app
# ─────────────────────────────────────────────────────────────────────────────

sync_engine = create_engine(
    "sqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


def get_sync_db():
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


sync_app = FastAPI(title="FastAuth Sync Test")

sync_auth = FastAuth(
    user_model=User,
    jwt_secret="test-secret-sync--min-32-chars!!",
    password_hasher="bcrypt",
    refresh_token_mode="body",
    get_db=get_sync_db,
)
sync_app.include_router(sync_auth.router)

get_sync_user = sync_auth.get_current_user()


@sync_app.get("/profile")
async def sync_profile(user: User = Depends(get_sync_user)):
    return {"username": user.username, "email": user.email}


@sync_app.on_event("startup")
def sync_create_tables():
    Base.metadata.create_all(bind=sync_engine)


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def _run_suite(client: TestClient, label: str) -> tuple[int, int]:
    passed = failed = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if ok:
            print(f"  PASS  {name}")
            passed += 1
        else:
            print(f"  FAIL  {name}  →  {detail}")
            failed += 1

    print(f"\n── {label} ──────────────────────────────────────────────────────")

    # Register
    r = client.post("/auth/register", json={
        "username": "alice", "email": "alice@test.com", "password": "AlicePass1!",
    })
    check("POST /auth/register → 201", r.status_code == 201, f"{r.status_code}: {r.text}")
    access  = r.json().get("access_token", "")
    refresh = r.json().get("refresh_token", "")

    # Duplicate
    r = client.post("/auth/register", json={
        "username": "alice", "email": "alice2@test.com", "password": "AlicePass1!",
    })
    check("Duplicate username → 409", r.status_code == 409, r.text)

    # Login
    r = client.post("/auth/login", json={"username": "alice", "password": "AlicePass1!"})
    check("POST /auth/login → 200", r.status_code == 200, r.text)
    access  = r.json().get("access_token", access)
    refresh = r.json().get("refresh_token", refresh)

    # Login by email
    r = client.post("/auth/login", json={"username": "alice@test.com", "password": "AlicePass1!"})
    check("Login by email → 200", r.status_code == 200, r.text)

    # Wrong password
    r = client.post("/auth/login", json={"username": "alice", "password": "WRONG"})
    check("Wrong password → 401", r.status_code == 401, r.text)

    # /auth/me
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
    check("GET /auth/me → 200", r.status_code == 200 and r.json().get("username") == "alice", r.text)

    # /auth/me no token
    r = client.get("/auth/me")
    check("GET /auth/me no token → 401", r.status_code == 401, r.text)

    # /profile
    r = client.get("/profile", headers={"Authorization": f"Bearer {access}"})
    check("GET /profile → 200", r.status_code == 200, r.text)

    # Refresh
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    check("POST /auth/refresh → 200", r.status_code == 200, r.text)
    new_access  = r.json().get("access_token", "")
    new_refresh = r.json().get("refresh_token", "")

    # Old refresh revoked
    r = client.post("/auth/refresh", json={"refresh_token": refresh})
    check("Old refresh token revoked → 401", r.status_code == 401, r.text)

    # New access token works
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    check("New access token valid → 200", r.status_code == 200, r.text)

    # Change password
    r = client.post("/auth/change-password",
        json={"old_password": "AlicePass1!", "new_password": "NewAlice2!"},
        headers={"Authorization": f"Bearer {new_access}"})
    check("POST /auth/change-password → 200", r.status_code == 200, r.text)

    r = client.post("/auth/change-password",
        json={"old_password": "AlicePass1!", "new_password": "Xxx1234!"},
        headers={"Authorization": f"Bearer {new_access}"})
    check("Change password wrong old → 401", r.status_code == 401, r.text)

    r = client.post("/auth/login", json={"username": "alice", "password": "NewAlice2!"})
    check("Login with new password → 200", r.status_code == 200, r.text)
    fresh_access = r.json().get("access_token", "")

    # Password reset
    r = client.post("/auth/reset-password", json={"email": "alice@test.com"})
    check("POST /auth/reset-password → 200", r.status_code == 200, r.text)

    r = client.post("/auth/reset-password", json={"email": "ghost@test.com"})
    check("Reset unknown email → 200 (no enumeration)", r.status_code == 200, r.text)

    r = client.post("/auth/reset-password/confirm", json={"token": "bad", "new_password": "X1234567!"})
    check("Reset bad token → 401", r.status_code == 401, r.text)

    # Logout + revocation
    r = client.post("/auth/logout", headers={"Authorization": f"Bearer {fresh_access}"})
    check("POST /auth/logout → 200", r.status_code == 200, r.text)

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {fresh_access}"})
    check("Revoked token after logout → 401", r.status_code == 401, r.text)

    # Rate limit
    for _ in range(5):
        client.post("/auth/login", json={"username": "alice", "password": "WRONG"})
    r = client.post("/auth/login", json={"username": "alice", "password": "WRONG"})
    check("Rate limit after 5+ failures → 429", r.status_code == 429, r.text)

    return passed, failed


def run_tests() -> bool:
    total_passed = total_failed = 0

    print("\n══════════════════════════════════════════════════════")
    print("  FastAuth — SQLAlchemy Adapter Tests (async + sync)")
    print("══════════════════════════════════════════════════════")

    with TestClient(async_app, raise_server_exceptions=True) as client:
        p, f = _run_suite(client, "AsyncSession (aiosqlite)")
        total_passed += p
        total_failed += f

    with TestClient(sync_app, raise_server_exceptions=True) as client:
        p, f = _run_suite(client, "Sync Session (sqlite3)")
        total_passed += p
        total_failed += f

    print(f"\n{'─' * 55}")
    print(f"Total: {total_passed}/{total_passed + total_failed} passed  |  {total_failed} failed")
    print("ALL TESTS PASSED ✓" if total_failed == 0 else "SOME TESTS FAILED ✗")
    print("─" * 55)
    return total_failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
