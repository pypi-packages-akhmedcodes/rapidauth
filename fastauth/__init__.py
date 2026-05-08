"""
FastAuth — Professional plug-and-play authentication framework for FastAPI.

Minimal usage::

    from fastapi import FastAPI
    from fastauth import FastAuth

    app = FastAPI()
    auth = FastAuth(user_model=User, jwt_secret="supersecret")
    app.include_router(auth.router)

    @app.get("/me")
    async def me(user=Depends(auth.get_current_user())):
        return user
"""

from fastauth.core import FastAuth
from fastauth.decorators.auth import login_required, permission_required, role_required
from fastauth.exceptions import (
    AccountInactiveError,
    AuthException,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    PermissionDeniedError,
    RateLimitExceededError,
    TokenExpiredError,
    TokenInvalidError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from fastauth.schemas.auth import (
    LoginSchema,
    MessageSchema,
    RegisterSchema,
    TokenSchema,
    UserBaseSchema,
)

__version__ = "0.2.3"
__all__ = [
    "FastAuth",
    # Decorators
    "login_required",
    "role_required",
    "permission_required",
    # Exceptions
    "AuthException",
    "InvalidCredentialsError",
    "TokenExpiredError",
    "TokenInvalidError",
    "UserNotFoundError",
    "UserAlreadyExistsError",
    "PermissionDeniedError",
    "EmailNotVerifiedError",
    "RateLimitExceededError",
    "AccountInactiveError",
    # Schemas
    "LoginSchema",
    "RegisterSchema",
    "TokenSchema",
    "UserBaseSchema",
    "MessageSchema",
]
