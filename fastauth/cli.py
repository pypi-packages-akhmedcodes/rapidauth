"""fastauth CLI — `fastauth init` scaffolds a new auth setup."""

from __future__ import annotations

import os
import sys
import textwrap


_ENV_EXAMPLE = textwrap.dedent("""\
    # FastAuth environment variables
    JWT_SECRET=change-me-to-a-long-random-string
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
""")

_CONFIG_PY = textwrap.dedent("""\
    import os
    from dotenv import load_dotenv

    load_dotenv()

    JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE = int(os.getenv("ACCESS_TOKEN_EXPIRE", 900))
    REFRESH_TOKEN_EXPIRE = int(os.getenv("REFRESH_TOKEN_EXPIRE", 604800))

    EMAIL_CONFIG = {
        "host": os.getenv("EMAIL_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("EMAIL_PORT", 587)),
        "username": os.getenv("EMAIL_USER", ""),
        "password": os.getenv("EMAIL_PASS", ""),
        "from_email": os.getenv("EMAIL_FROM", ""),
    }
""")

_MAIN_PY = textwrap.dedent("""\
    from fastapi import FastAPI, Depends
    from fastauth import FastAuth
    # from your_app.models import User  # import your user model
    # from your_app.config import JWT_SECRET

    app = FastAPI(title="My App")

    # auth = FastAuth(user_model=User, jwt_secret=JWT_SECRET)
    # app.include_router(auth.router)

    @app.get("/")
    async def root():
        return {"message": "FastAuth is ready. Uncomment the lines above."}
""")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] == "init":
        _init()
    elif args[0] == "version":
        from fastauth import __version__
        print(f"fastauth {__version__}")
    else:
        print(f"Unknown command: {args[0]}")
        print("Usage: fastauth init | fastauth version")
        sys.exit(1)


def _init() -> None:
    cwd = os.getcwd()

    files = {
        ".env.example": _ENV_EXAMPLE,
        "auth_config.py": _CONFIG_PY,
        "main.py": _MAIN_PY,
    }

    for filename, content in files.items():
        path = os.path.join(cwd, filename)
        if os.path.exists(path):
            print(f"  skip  {filename}  (already exists)")
            continue
        with open(path, "w") as f:
            f.write(content)
        print(f"  created  {filename}")

    print("\nFastAuth initialized. Next steps:")
    print("  1. Copy .env.example → .env and fill in your secrets")
    print("  2. Define your User model")
    print("  3. Wire auth into main.py")
