"""
Integration test suite for FastAuth.
Run: python3.10 test/test_fastauth.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from tortoise import fields
from tortoise.contrib.fastapi import register_tortoise
from tortoise.models import Model

from fastauth import FastAuth
from fastauth.exceptions import PermissionDeniedError


class User(Model):
    id: int = fields.IntField(pk=True)
    username: str = fields.CharField(max_length=100, unique=True)
    email: str = fields.CharField(max_length=254, unique=True)
    password: str = fields.CharField(max_length=200)
    is_active: bool = fields.BooleanField(default=True)
    is_verified: bool = fields.BooleanField(default=True)
    roles: list = fields.JSONField(default=list)
    permissions: list = fields.JSONField(default=list)

    class Meta:
        table = "users"


app = FastAPI(title="FastAuth Test")

auth = FastAuth(
    user_model=User,
    jwt_secret="test-secret-key-minimum-16-chars!!",
    password_hasher="bcrypt",
    refresh_token_mode="body",
)

app.include_router(auth.router)
auth.add_middleware(app)

get_current_user = auth.get_current_user()


def require_role(*roles: str):
    async def dep(user: User = Depends(get_current_user)) -> User:
        for role in roles:
            if role not in (user.roles or []):
                raise PermissionDeniedError(f"Role '{role}' required")
        return user
    return dep


@app.get("/profile")
async def profile(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username, "email": user.email}


@app.get("/admin")
async def admin_only(user: User = Depends(require_role("admin"))):
    return {"message": f"Hello admin {user.username}"}


@app.post("/test/set-role/{username}/{role}", include_in_schema=False)
async def set_role(username: str, role: str):
    u = await User.get_or_none(username=username)
    if u is None:
        return {"error": "not found"}
    roles = list(u.roles or [])
    if role not in roles:
        roles.append(role)
        u.roles = roles
        await u.save()
    return {"username": username, "roles": u.roles}


@app.on_event("startup")
async def seed() -> None:
    await auth.create_user(
        username="superadmin",
        email="superadmin@example.com",
        password="SuperAdmin1!",
        extra={"roles": ["admin"]},
    )


register_tortoise(
    app,
    db_url="sqlite://:memory:",
    modules={"models": [__name__]},
    generate_schemas=True,
    add_exception_handlers=True,
)


def run_tests() -> bool:
    passed = 0
    failed = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal passed, failed
        if condition:
            print(f"  PASS  {name}")
            passed += 1
        else:
            print(f"  FAIL  {name}  →  {detail}")
            failed += 1

    print("\n── FastAuth Integration Tests ──────────────────────────────────────")

    with TestClient(app, raise_server_exceptions=True) as client:

        r = client.post("/auth/register", json={"username": "alice", "email": "alice@example.com", "password": "AlicePass1!"})
        check("POST /auth/register → 201", r.status_code == 201, f"{r.status_code}: {r.text}")
        access = r.json().get("access_token", "")
        refresh = r.json().get("refresh_token", "")

        r = client.post("/auth/register", json={"username": "alice", "email": "alice2@example.com", "password": "AlicePass1!"})
        check("POST /auth/register duplicate username → 409", r.status_code == 409, r.text)

        r = client.post("/auth/login", json={"username": "alice", "password": "AlicePass1!"})
        check("POST /auth/login → 200", r.status_code == 200, r.text)
        access = r.json().get("access_token", access)
        refresh = r.json().get("refresh_token", refresh)

        r = client.post("/auth/login", json={"username": "alice@example.com", "password": "AlicePass1!"})
        check("POST /auth/login with email → 200", r.status_code == 200, r.text)

        r = client.post("/auth/login", json={"username": "alice", "password": "WRONG"})
        check("POST /auth/login wrong password → 401", r.status_code == 401, r.text)

        r = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
        check("GET /auth/me → 200", r.status_code == 200 and r.json().get("username") == "alice", r.text)

        r = client.get("/auth/me")
        check("GET /auth/me no token → 401", r.status_code == 401, r.text)

        r = client.get("/profile", headers={"Authorization": f"Bearer {access}"})
        check("GET /profile authenticated → 200", r.status_code == 200, r.text)

        r = client.post("/auth/refresh", json={"refresh_token": refresh})
        check("POST /auth/refresh → 200", r.status_code == 200, r.text)
        new_access = r.json().get("access_token", "")
        new_refresh = r.json().get("refresh_token", "")

        r = client.post("/auth/refresh", json={"refresh_token": refresh})
        check("Old refresh token revoked after rotation → 401", r.status_code == 401, r.text)

        r = client.get("/auth/me", headers={"Authorization": f"Bearer {new_access}"})
        check("New access token valid after refresh → 200", r.status_code == 200, r.text)

        r = client.post("/auth/register", json={"username": "bob", "email": "bob@example.com", "password": "BobPass1!"})
        check("POST /auth/register bob → 201", r.status_code == 201, r.text)

        r = client.post("/test/set-role/bob/admin")
        check("Grant admin role to bob", r.json().get("roles") == ["admin"], r.text)

        r = client.post("/auth/login", json={"username": "bob", "password": "BobPass1!"})
        bob_access = r.json().get("access_token", "")

        r = client.get("/admin", headers={"Authorization": f"Bearer {bob_access}"})
        check("GET /admin with admin role → 200", r.status_code == 200, r.text)

        r = client.get("/admin", headers={"Authorization": f"Bearer {new_access}"})
        check("GET /admin without admin role → 403", r.status_code == 403, r.text)

        r = client.post("/auth/change-password",
            json={"old_password": "AlicePass1!", "new_password": "NewAlice2!"},
            headers={"Authorization": f"Bearer {new_access}"})
        check("POST /auth/change-password → 200", r.status_code == 200, r.text)

        r = client.post("/auth/change-password",
            json={"old_password": "AlicePass1!", "new_password": "Xxx12345!"},
            headers={"Authorization": f"Bearer {new_access}"})
        check("POST /auth/change-password wrong old password → 401", r.status_code == 401, r.text)

        r = client.post("/auth/login", json={"username": "alice", "password": "NewAlice2!"})
        check("Login with new password → 200", r.status_code == 200, r.text)

        r = client.post("/auth/reset-password", json={"email": "alice@example.com"})
        check("POST /auth/reset-password → 200", r.status_code == 200, r.text)

        r = client.post("/auth/reset-password", json={"email": "ghost@example.com"})
        check("POST /auth/reset-password unknown email → 200 (no enumeration)", r.status_code == 200, r.text)

        r = client.post("/auth/reset-password/confirm", json={"token": "badtoken", "new_password": "X12345678!"})
        check("POST /auth/reset-password/confirm bad token → 401", r.status_code == 401, r.text)

        r = client.post("/auth/login", json={"username": "superadmin", "password": "SuperAdmin1!"})
        check("Startup-seeded superadmin login → 200", r.status_code == 200, r.text)
        superadmin_access = r.json().get("access_token", "")

        r = client.get("/admin", headers={"Authorization": f"Bearer {superadmin_access}"})
        check("superadmin can access /admin → 200", r.status_code == 200, r.text)

        r = client.post("/auth/login", json={"username": "alice", "password": "NewAlice2!"})
        last_access = r.json()["access_token"]
        r = client.post("/auth/logout", headers={"Authorization": f"Bearer {last_access}"})
        check("POST /auth/logout → 200", r.status_code == 200, r.text)
        r = client.get("/auth/me", headers={"Authorization": f"Bearer {last_access}"})
        check("Revoked token after logout → 401", r.status_code == 401, r.text)

        for _ in range(5):
            client.post("/auth/login", json={"username": "alice", "password": "WRONG"})
        r = client.post("/auth/login", json={"username": "alice", "password": "WRONG"})
        check("Rate limit after 5+ failed attempts → 429", r.status_code == 429, r.text)

    total = passed + failed
    print(f"\n{'─' * 55}")
    print(f"Results: {passed}/{total} passed  |  {failed} failed")
    print("ALL TESTS PASSED" if failed == 0 else "SOME TESTS FAILED")
    print("─" * 55)
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
