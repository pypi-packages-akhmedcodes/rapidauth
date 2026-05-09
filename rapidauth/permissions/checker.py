from __future__ import annotations

from typing import Any, Callable, List

from fastapi import Depends

from rapidauth.exceptions import PermissionDeniedError


class PermissionChecker:
    """FastAPI dependency class for role/permission gating."""

    def __init__(
        self,
        roles: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
        get_current_user: Optional[Callable] = None,
    ) -> None:
        self.required_roles = roles or []
        self.required_permissions = permissions or []
        self._get_current_user = get_current_user

    def __call__(self, user: Any) -> Any:
        user_roles = getattr(user, "roles", []) or []
        user_perms = getattr(user, "permissions", []) or []

        for role in self.required_roles:
            if role not in user_roles:
                raise PermissionDeniedError(f"Role '{role}' required")

        for perm in self.required_permissions:
            if perm not in user_perms:
                raise PermissionDeniedError(f"Permission '{perm}' required")

        return user


from typing import Optional


def require_roles(*roles: str) -> Callable:
    """
    Returns a dependency factory that checks the current user's roles.

    Usage:
        @router.get("/admin")
        async def admin(user=Depends(require_roles("admin"))):
            ...
    """
    def factory(get_current_user: Callable) -> Callable:
        async def dep(user: Any = Depends(get_current_user)) -> Any:
            user_roles = getattr(user, "roles", []) or []
            for role in roles:
                if role not in user_roles:
                    raise PermissionDeniedError(f"Role '{role}' required")
            return user
        return dep
    return factory


def require_permissions(*permissions: str) -> Callable:
    """Returns a dependency factory that checks the current user's permissions."""
    def factory(get_current_user: Callable) -> Callable:
        async def dep(user: Any = Depends(get_current_user)) -> Any:
            user_perms = getattr(user, "permissions", []) or []
            for perm in permissions:
                if perm not in user_perms:
                    raise PermissionDeniedError(f"Permission '{perm}' required")
            return user
        return dep
    return factory
