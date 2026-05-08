from __future__ import annotations

import functools
from typing import Any, Callable, List

from fastapi import Depends

from fastauth.exceptions import PermissionDeniedError, TokenInvalidError


def login_required(func: Callable) -> Callable:
    """
    Decorator that injects the current user into the first positional arg.

    Usage (FastAPI path operation):
        @router.get("/profile")
        @login_required
        async def profile(user, request: Request):
            ...

    NOTE: The `user` argument must be the first parameter after `self` (if any).
    For a cleaner FastAPI-native approach, use `Depends(auth.get_current_user)`.
    """
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Starlette/FastAPI injects request via 'request' kwarg; check state.user
        request = kwargs.get("request") or (args[0] if args else None)
        if request is None or not hasattr(request, "state"):
            raise TokenInvalidError()
        user = getattr(request.state, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            raise TokenInvalidError()
        return await func(user, *args, **kwargs)
    return wrapper


def role_required(*roles: str) -> Callable:
    """
    Decorator factory that checks the user has all given roles.

    Usage:
        @router.get("/admin")
        @role_required("admin")
        async def admin_page(user, request: Request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = kwargs.get("request") or (args[0] if args else None)
            if request is None or not hasattr(request, "state"):
                raise TokenInvalidError()
            user = getattr(request.state, "user", None)
            if user is None or not getattr(user, "is_authenticated", False):
                raise TokenInvalidError()
            user_roles = getattr(user, "roles", []) or []
            for role in roles:
                if role not in user_roles:
                    raise PermissionDeniedError(f"Role '{role}' required")
            return await func(user, *args, **kwargs)
        return wrapper
    return decorator


def permission_required(*permissions: str) -> Callable:
    """Decorator factory that checks the user has all given permissions."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request = kwargs.get("request") or (args[0] if args else None)
            if request is None or not hasattr(request, "state"):
                raise TokenInvalidError()
            user = getattr(request.state, "user", None)
            if user is None or not getattr(user, "is_authenticated", False):
                raise TokenInvalidError()
            user_perms = getattr(user, "permissions", []) or []
            for perm in permissions:
                if perm not in user_perms:
                    raise PermissionDeniedError(f"Permission '{perm}' required")
            return await func(user, *args, **kwargs)
        return wrapper
    return decorator
