from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

if TYPE_CHECKING:
    from rapidauth.managers.user import UserManager
    from rapidauth.jwt.handler import JWTHandler


class _AnonymousUser:
    is_authenticated = False
    id = None
    username = "anonymous"


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that populates `request.state.user`.

    - On valid Bearer token → sets request.state.user to the DB user object.
    - On missing/invalid token → sets request.state.user to _AnonymousUser().
    - request.state.user.is_authenticated gives a clean bool check.
    """

    def __init__(self, app, jwt_handler: "JWTHandler", user_manager: "UserManager") -> None:
        super().__init__(app)
        self._jwt = jwt_handler
        self._mgr = user_manager

    async def dispatch(self, request: Request, call_next) -> Response:
        user = _AnonymousUser()

        token = self._extract_token(request)
        if token:
            try:
                payload = self._jwt.decode_access(token)
                db_user = await self._mgr.get_by_id(payload.get("sub"))
                if db_user is not None:
                    db_user.is_authenticated = True  # type: ignore[attr-defined]
                    user = db_user
            except Exception:
                pass  # Any auth failure → anonymous

        request.state.user = user
        return await call_next(request)

    @staticmethod
    def _extract_token(request: Request) -> Optional[str]:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        # Fallback: cookie-based access token
        return request.cookies.get("access_token")
