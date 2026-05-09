"""fastauth CLI

Commands
--------
fastauth init                                    – scaffold .env.example + auth_config.py
fastauth --default-setup sqlite     [--async|--sync]  – Tortoise async | SQLAlchemy sync + SQLite
fastauth --default-setup sqlalchemy [--async|--sync]  – SQLAlchemy + SQLite (async or sync)
fastauth --default-setup postgresql [--async|--sync]  – SQLAlchemy + PostgreSQL (async or sync)
fastauth version                                 – print version

Default mode when no flag given: --async
"""

from __future__ import annotations

import os
import sys
import textwrap


# ── Shared templates ──────────────────────────────────────────────────────────

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

    # Database
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


# ── ASYNC templates ───────────────────────────────────────────────────────────

# sqlite --async  →  Tortoise ORM + aiosqlite
_DB_SQLITE_ASYNC = textwrap.dedent("""\
    # database.py  –  Tortoise ORM + SQLite (async)
    # Uses RegisterTortoise (Tortoise ORM 1.x compatible).
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from tortoise.contrib.fastapi import RegisterTortoise


    @asynccontextmanager
    async def tortoise_lifespan(app: FastAPI):
        \"\"\"Initialize Tortoise ORM on startup, close connections on shutdown.

        RegisterTortoise sets _enable_global_fallback=True so that request
        handlers can access the DB without an explicit TortoiseContext.
        \"\"\"
        async with RegisterTortoise(
            app,
            db_url="sqlite://./app.db",
            modules={"models": ["models"]},
            generate_schemas=True,
        ):
            yield
""")

_MODELS_TORTOISE = textwrap.dedent("""\
    # models.py  –  Tortoise ORM User model (async)
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
""")

_MAIN_SQLITE_ASYNC = textwrap.dedent("""\
    # main.py  –  FastAPI + FastAuth + Tortoise ORM (async)
    from fastapi import Depends, FastAPI
    from fastauth import FastAuth
    from database import tortoise_lifespan
    from models import User

    # tortoise_lifespan initializes Tortoise ORM on startup via RegisterTortoise
    app = FastAPI(title="My App", lifespan=tortoise_lifespan)

    auth = FastAuth(
        user_model=User,
        jwt_secret="super-secret-key-change-it",  # change in production!
    )
    app.include_router(auth.router)

    get_current_user = auth.get_current_user()


    @app.get("/profile")
    async def profile(user: User = Depends(get_current_user)):
        return {"id": user.id, "username": user.username, "email": user.email}
""")

# sqlalchemy --async  →  SQLAlchemy 2.x + aiosqlite
_DB_SQLALCHEMY_ASYNC = textwrap.dedent("""\
    # database.py  –  SQLAlchemy 2.x async + SQLite
    import os
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import DeclarativeBase, sessionmaker

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./app.db")
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


    class Base(DeclarativeBase):
        pass


    async def get_db():
        async with AsyncSessionLocal() as session:
            yield session


    async def create_tables() -> None:
        from models import User  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
""")

_MODELS_SQLALCHEMY = textwrap.dedent("""\
    # models.py  –  SQLAlchemy 2.x User model
    from sqlalchemy import Boolean, DateTime, Integer, String, JSON, func
    from sqlalchemy.orm import Mapped, mapped_column
    from database import Base


    class User(Base):
        __tablename__ = "users"

        id          : Mapped[int]  = mapped_column(Integer, primary_key=True, index=True)
        username    : Mapped[str]  = mapped_column(String(100), unique=True, index=True)
        email       : Mapped[str]  = mapped_column(String(254), unique=True, index=True)
        password    : Mapped[str]  = mapped_column(String(200))
        is_active   : Mapped[bool] = mapped_column(Boolean, default=True)
        is_verified : Mapped[bool] = mapped_column(Boolean, default=False)
        roles       : Mapped[list] = mapped_column(JSON, default=list)
        permissions : Mapped[list] = mapped_column(JSON, default=list)
        created_at               = mapped_column(DateTime(timezone=True), server_default=func.now())
""")

_MAIN_SQLALCHEMY_ASYNC = textwrap.dedent("""\
    # main.py  –  FastAPI + FastAuth + SQLAlchemy (async)
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
        jwt_secret="super-secret-key-change-it",
        get_db=get_db,
    )
    app.include_router(auth.router)

    get_current_user = auth.get_current_user()


    @app.get("/profile")
    async def profile(user: User = Depends(get_current_user)):
        return {"id": user.id, "username": user.username, "email": user.email}
""")

# postgresql --async  →  SQLAlchemy 2.x + asyncpg
_DB_POSTGRESQL_ASYNC = textwrap.dedent("""\
    # database.py  –  SQLAlchemy 2.x async + PostgreSQL
    import os
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import DeclarativeBase, sessionmaker

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://user:password@localhost/dbname",
    )
    engine = create_async_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


    class Base(DeclarativeBase):
        pass


    async def get_db():
        async with AsyncSessionLocal() as session:
            yield session


    async def create_tables() -> None:
        from models import User  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
""")


# ── SYNC templates ────────────────────────────────────────────────────────────

# sqlite --sync  →  SQLAlchemy sync + sqlite3
_DB_SQLITE_SYNC = textwrap.dedent("""\
    # database.py  –  SQLAlchemy sync + SQLite
    # NOTE: sync sessions block the event loop.
    # Use run_in_executor or switch to --async for production.
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


    class Base(DeclarativeBase):
        pass


    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


    def create_tables() -> None:
        from models import User  # noqa: F401
        Base.metadata.create_all(bind=engine)
""")

_MODELS_SQLALCHEMY_SYNC = textwrap.dedent("""\
    # models.py  –  SQLAlchemy User model (sync)
    from sqlalchemy import Boolean, DateTime, Integer, String, JSON, func
    from sqlalchemy.orm import Mapped, mapped_column
    from database import Base


    class User(Base):
        __tablename__ = "users"

        id          : Mapped[int]  = mapped_column(Integer, primary_key=True, index=True)
        username    : Mapped[str]  = mapped_column(String(100), unique=True, index=True)
        email       : Mapped[str]  = mapped_column(String(254), unique=True, index=True)
        password    : Mapped[str]  = mapped_column(String(200))
        is_active   : Mapped[bool] = mapped_column(Boolean, default=True)
        is_verified : Mapped[bool] = mapped_column(Boolean, default=False)
        roles       : Mapped[list] = mapped_column(JSON, default=list)
        permissions : Mapped[list] = mapped_column(JSON, default=list)
        created_at               = mapped_column(DateTime(timezone=True), server_default=func.now())
""")

_MAIN_SYNC = textwrap.dedent("""\
    # main.py  –  FastAPI + FastAuth + SQLAlchemy (sync)
    # NOTE: sync DB calls block the event loop.
    # Wrap with run_in_executor or switch to --async for production.
    from contextlib import asynccontextmanager
    from fastapi import Depends, FastAPI
    from fastauth import FastAuth
    from database import create_tables, get_db
    from models import User


    @asynccontextmanager
    async def lifespan(app):
        create_tables()
        yield


    app = FastAPI(title="My App", lifespan=lifespan)

    auth = FastAuth(
        user_model=User,
        jwt_secret="super-secret-key-change-it",
        get_db=get_db,
    )
    app.include_router(auth.router)

    get_current_user = auth.get_current_user()


    @app.get("/profile")
    async def profile(user: User = Depends(get_current_user)):
        return {"id": user.id, "username": user.username, "email": user.email}
""")

# sqlalchemy --sync  →  SQLAlchemy sync + sqlite3  (same as sqlite --sync)
_DB_SQLALCHEMY_SYNC = _DB_SQLITE_SYNC

# postgresql --sync  →  SQLAlchemy sync + psycopg2
_DB_POSTGRESQL_SYNC = textwrap.dedent("""\
    # database.py  –  SQLAlchemy sync + PostgreSQL (psycopg2)
    # NOTE: sync sessions block the event loop.
    # Use run_in_executor or switch to --async for production.
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import DeclarativeBase, sessionmaker

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://user:password@localhost/dbname",
    )
    engine = create_engine(DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


    class Base(DeclarativeBase):
        pass


    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


    def create_tables() -> None:
        from models import User  # noqa: F401
        Base.metadata.create_all(bind=engine)
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
            print("Usage: fastauth --default-setup sqlite|sqlalchemy|postgresql [--async|--sync]")
            sys.exit(1)

        backend = args[1].lower()

        # Parse mode flag — default to async
        mode = "async"
        if len(args) >= 3:
            flag = args[2].lstrip("-").lower()
            if flag in ("async", "sync"):
                mode = flag
            else:
                print(f"Unknown flag '{args[2]}'. Use --async or --sync.")
                sys.exit(1)

        _default_setup(backend, mode)
        return

    print(f"Unknown command: {args[0]}")
    _print_help()
    sys.exit(1)


def _print_help() -> None:
    print(textwrap.dedent("""\
        fastauth-framework CLI

        Commands:
          fastauth init                                   Scaffold .env.example + auth_config.py
          fastauth --default-setup sqlite   [--async]    Tortoise ORM + SQLite     (default: --async)
          fastauth --default-setup sqlite   --sync       SQLAlchemy sync + SQLite
          fastauth --default-setup sqlalchemy [--async]  SQLAlchemy async + SQLite (default: --async)
          fastauth --default-setup sqlalchemy --sync     SQLAlchemy sync  + SQLite
          fastauth --default-setup postgresql [--async]  SQLAlchemy async + PostgreSQL
          fastauth --default-setup postgresql --sync     SQLAlchemy sync  + PostgreSQL (psycopg2)
          fastauth version                               Print installed version
    """))


def _init() -> None:
    cwd = os.getcwd()
    _write_if_missing(cwd, ".env.example", _ENV_EXAMPLE)
    _write_if_missing(cwd, "auth_config.py", _AUTH_CONFIG_PY)
    print("\nNext steps:")
    print("  1. cp .env.example .env  and fill in your secrets")
    print("  2. fastauth --default-setup sqlite --async")
    print("  3. uvicorn main:app --reload")


def _default_setup(backend: str, mode: str) -> None:
    cwd = os.getcwd()

    if backend == "sqlite":
        if mode == "async":
            files = {
                "database.py": _DB_SQLITE_ASYNC,
                "models.py":   _MODELS_TORTOISE,
                "main.py":     _MAIN_SQLITE_ASYNC,
            }
            pip_hint = 'pip install "fastauth-framework[tortoise]" uvicorn[standard]'
        else:
            files = {
                "database.py": _DB_SQLITE_SYNC,
                "models.py":   _MODELS_SQLALCHEMY_SYNC,
                "main.py":     _MAIN_SYNC,
            }
            pip_hint = 'pip install "fastauth-framework[sqlalchemy]" uvicorn[standard]'

    elif backend == "sqlalchemy":
        if mode == "async":
            files = {
                "database.py": _DB_SQLALCHEMY_ASYNC,
                "models.py":   _MODELS_SQLALCHEMY,
                "main.py":     _MAIN_SQLALCHEMY_ASYNC,
            }
            pip_hint = 'pip install "fastauth-framework[sqlalchemy]" aiosqlite uvicorn[standard]'
        else:
            files = {
                "database.py": _DB_SQLALCHEMY_SYNC,
                "models.py":   _MODELS_SQLALCHEMY_SYNC,
                "main.py":     _MAIN_SYNC,
            }
            pip_hint = 'pip install "fastauth-framework[sqlalchemy]" uvicorn[standard]'

    elif backend == "postgresql":
        if mode == "async":
            files = {
                "database.py": _DB_POSTGRESQL_ASYNC,
                "models.py":   _MODELS_SQLALCHEMY,
                "main.py":     _MAIN_SQLALCHEMY_ASYNC,
            }
            pip_hint = 'pip install "fastauth-framework[sqlalchemy]" asyncpg uvicorn[standard]'
        else:
            files = {
                "database.py": _DB_POSTGRESQL_SYNC,
                "models.py":   _MODELS_SQLALCHEMY_SYNC,
                "main.py":     _MAIN_SYNC,
            }
            pip_hint = 'pip install "fastauth-framework[sqlalchemy]" psycopg2-binary uvicorn[standard]'

    else:
        print(f"Unknown backend '{backend}'. Choose: sqlite | sqlalchemy | postgresql")
        sys.exit(1)

    label = f"{backend} --{mode}"
    for filename, content in files.items():
        _write_if_missing(cwd, filename, content)

    print(f"\nSetup complete: {label}")
    print(f"Install deps : {pip_hint}")
    print("Run server   : uvicorn main:app --reload")
    if mode == "sync":
        print("NOTE         : sync DB calls block the event loop — use --async for production.")


def _write_if_missing(cwd: str, filename: str, content: str) -> None:
    path = os.path.join(cwd, filename)
    if os.path.exists(path):
        print(f"  skip     {filename}  (already exists)")
    else:
        with open(path, "w") as f:
            f.write(content)
        print(f"  created  {filename}")
