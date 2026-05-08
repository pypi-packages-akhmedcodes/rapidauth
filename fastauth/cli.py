"""fastauth CLI

Commands
--------
fastauth init                         – scaffold .env.example + auth_config.py + main.py
fastauth --default-setup sqlite       – generate database.py + models.py (Tortoise + SQLite)
fastauth --default-setup sqlalchemy   – generate database.py + models.py (SQLAlchemy + SQLite)
fastauth --default-setup postgresql   – generate database.py + models.py (SQLAlchemy + PostgreSQL)
fastauth version                      – print version
"""

from __future__ import annotations

import os
import sys
import textwrap


# ── Templates ─────────────────────────────────────────────────────────────────

_ENV_EXAMPLE = textwrap.dedent("""\
    # FastAuth environment variables
    JWT_SECRET=change-me-to-a-long-random-string-min-32-chars
    JWT_ALGORITHM=HS256
    ACCESS_TOKEN_EXPIRE=900
    REFRESH_TOKEN_EXPIRE=604800

    # Email (optional)
    EMAIL_HOST=smtp.gmail.com
    EMAIL_PORT=587
    EMAIL_USER=you@example.com
    EMAIL_PASS=yourpassword
    EMAIL_FROM=you@example.com

    # Google OAuth (optional)
    GOOGLE_CLIENT_ID=
    GOOGLE_CLIENT_SECRET=
    GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

    # Database (PostgreSQL)
    DATABASE_URL=postgresql+asyncpg://user:password@localhost/dbname
""")

_AUTH_CONFIG_PY = textwrap.dedent("""\
    import os
    from dotenv import load_dotenv

    load_dotenv()

    JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE = int(os.getenv("ACCESS_TOKEN_EXPIRE", 900))
    REFRESH_TOKEN_EXPIRE = int(os.getenv("REFRESH_TOKEN_EXPIRE", 604800))
""")


# ── database.py templates ─────────────────────────────────────────────────────

_DB_TORTOISE_SQLITE = textwrap.dedent("""\
    # database.py  –  Tortoise ORM + SQLite
    from fastapi import FastAPI
    from tortoise.contrib.fastapi import register_tortoise


    def init_db(app: FastAPI, db_url: str = "sqlite://./app.db") -> None:
        register_tortoise(
            app,
            db_url=db_url,
            modules={"models": ["models"]},
            generate_schemas=True,
            add_exception_handlers=True,
        )
""")

_DB_SQLALCHEMY_SQLITE = textwrap.dedent("""\
    # database.py  –  SQLAlchemy 2.x async + SQLite
    import os
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import DeclarativeBase, sessionmaker

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")

    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


    class Base(DeclarativeBase):
        pass


    async def get_db():
        async with AsyncSessionLocal() as session:
            yield session


    async def create_tables() -> None:
        \"\"\"Call this on startup to create all tables.\"\"\"
        async with engine.begin() as conn:
            from models import User  # noqa: F401 – ensure model is registered
            await conn.run_sync(Base.metadata.create_all)
""")

_DB_SQLALCHEMY_POSTGRES = textwrap.dedent("""\
    # database.py  –  SQLAlchemy 2.x async + PostgreSQL
    import os
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import DeclarativeBase, sessionmaker

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@localhost/dbname",
    )

    engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )


    class Base(DeclarativeBase):
        pass


    async def get_db():
        async with AsyncSessionLocal() as session:
            yield session


    async def create_tables() -> None:
        \"\"\"Call this on startup to create all tables.\"\"\"
        async with engine.begin() as conn:
            from models import User  # noqa: F401 – ensure model is registered
            await conn.run_sync(Base.metadata.create_all)
""")


# ── models.py templates ───────────────────────────────────────────────────────

_MODELS_TORTOISE = textwrap.dedent("""\
    # models.py  –  Tortoise ORM User model
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

        def __str__(self) -> str:
            return f"<User id={self.id} username={self.username}>"
""")

_MODELS_SQLALCHEMY = textwrap.dedent("""\
    # models.py  –  SQLAlchemy 2.x User model
    from typing import List, Optional
    from sqlalchemy import Boolean, DateTime, Integer, String, func
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.types import JSON
    from sqlalchemy.orm import Mapped, mapped_column

    from database import Base


    class User(Base):
        __tablename__ = "users"

        id:          Mapped[int]           = mapped_column(Integer, primary_key=True, index=True)
        username:    Mapped[str]           = mapped_column(String(100), unique=True, index=True, nullable=False)
        email:       Mapped[str]           = mapped_column(String(254), unique=True, index=True, nullable=False)
        password:    Mapped[str]           = mapped_column(String(200), nullable=False)
        is_active:   Mapped[bool]          = mapped_column(Boolean, default=True)
        is_verified: Mapped[bool]          = mapped_column(Boolean, default=False)
        roles:       Mapped[list]          = mapped_column(JSON, default=list)
        permissions: Mapped[list]          = mapped_column(JSON, default=list)
        created_at:  Mapped[DateTime]      = mapped_column(DateTime(timezone=True), server_default=func.now())

        def __repr__(self) -> str:
            return f"<User id={self.id} username={self.username}>"
""")

_MAIN_PY_TORTOISE = textwrap.dedent("""\
    # main.py  –  FastAPI + FastAuth + Tortoise ORM
    from fastapi import Depends, FastAPI
    from fastauth import FastAuth
    from fastauth.exceptions import PermissionDeniedError
    from database import init_db
    from models import User

    app = FastAPI(title="My App")
    init_db(app)

    auth = FastAuth(
        user_model=User,
        jwt_secret="change-me-min-32-chars-secret-key!!",
    )
    app.include_router(auth.router)

    get_current_user = auth.get_current_user()


    @app.get("/profile")
    async def profile(user: User = Depends(get_current_user)):
        return {"id": user.id, "username": user.username, "email": user.email}
""")

_MAIN_PY_SQLALCHEMY = textwrap.dedent("""\
    # main.py  –  FastAPI + FastAuth + SQLAlchemy
    from contextlib import asynccontextmanager
    from fastapi import Depends, FastAPI
    from fastauth import FastAuth
    from database import create_tables, get_db
    from models import User


    @asynccontextmanager
    async def lifespan(app):
        await create_tables()
        yield


    app = FastAPI(title="My App", lifespan=lifespan)

    auth = FastAuth(
        user_model=User,
        jwt_secret="change-me-min-32-chars-secret-key!!",
        get_db=get_db,
    )
    app.include_router(auth.router)

    get_current_user = auth.get_current_user()


    @app.get("/profile")
    async def profile(user: User = Depends(get_current_user)):
        return {"id": user.id, "username": user.username, "email": user.email}
""")


# ── CLI entry point ───────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]

    if not args:
        _print_help()
        return

    if args[0] == "version":
        from fastauth import __version__
        print(f"fastauth-framework {__version__}")
        return

    if args[0] == "init":
        _init()
        return

    if args[0] == "--default-setup":
        if len(args) < 2:
            print("Usage: fastauth --default-setup sqlite|sqlalchemy|postgresql")
            sys.exit(1)
        _default_setup(args[1].lower())
        return

    print(f"Unknown command: {args[0]}")
    _print_help()
    sys.exit(1)


def _print_help() -> None:
    print(textwrap.dedent("""\
        fastauth-framework CLI

        Commands:
          fastauth init                          Scaffold .env.example, auth_config.py, main.py
          fastauth --default-setup sqlite        Generate database.py + models.py (Tortoise + SQLite)
          fastauth --default-setup sqlalchemy    Generate database.py + models.py (SQLAlchemy + SQLite)
          fastauth --default-setup postgresql    Generate database.py + models.py (SQLAlchemy + PostgreSQL)
          fastauth version                       Print version
    """))


def _init() -> None:
    cwd = os.getcwd()
    files = {
        ".env.example": _ENV_EXAMPLE,
        "auth_config.py": _AUTH_CONFIG_PY,
    }
    for filename, content in files.items():
        _write_if_missing(cwd, filename, content)
    print("\nNext steps:")
    print("  1. cp .env.example .env  and fill in your secrets")
    print("  2. Run: fastauth --default-setup sqlite  (or sqlalchemy / postgresql)")
    print("  3. Define your FastAPI app and call auth.router")


def _default_setup(backend: str) -> None:
    cwd = os.getcwd()

    if backend == "sqlite":
        files = {
            "database.py": _DB_TORTOISE_SQLITE,
            "models.py": _MODELS_TORTOISE,
            "main.py": _MAIN_PY_TORTOISE,
        }
        pip_hint = 'pip install "fastauth-framework[tortoise]" uvicorn[standard]'

    elif backend == "sqlalchemy":
        files = {
            "database.py": _DB_SQLALCHEMY_SQLITE,
            "models.py": _MODELS_SQLALCHEMY,
            "main.py": _MAIN_PY_SQLALCHEMY,
        }
        pip_hint = 'pip install "fastauth-framework[sqlalchemy]" aiosqlite uvicorn[standard]'

    elif backend == "postgresql":
        files = {
            "database.py": _DB_SQLALCHEMY_POSTGRES,
            "models.py": _MODELS_SQLALCHEMY,
            "main.py": _MAIN_PY_SQLALCHEMY,
        }
        pip_hint = 'pip install "fastauth-framework[sqlalchemy]" asyncpg uvicorn[standard]'

    else:
        print(f"Unknown backend '{backend}'. Choose: sqlite | sqlalchemy | postgresql")
        sys.exit(1)

    for filename, content in files.items():
        _write_if_missing(cwd, filename, content)

    print(f"\nSetup complete for '{backend}'.")
    print(f"Install deps:  {pip_hint}")
    print("Run server:    uvicorn main:app --reload")


def _write_if_missing(cwd: str, filename: str, content: str) -> None:
    path = os.path.join(cwd, filename)
    if os.path.exists(path):
        print(f"  skip     {filename}  (already exists)")
    else:
        with open(path, "w") as f:
            f.write(content)
        print(f"  created  {filename}")
