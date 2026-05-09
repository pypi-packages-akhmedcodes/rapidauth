from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from rapidauth.config.settings import RapidAuthSettings
from rapidauth.exceptions import UserNotFoundError
from rapidauth.managers.rate_limit import RateLimiter
from rapidauth.managers.user import UserManager
from rapidauth.schemas.auth import (
    ChangePasswordSchema,
    EmailVerifySchema,
    LoginSchema,
    MessageSchema,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    RefreshSchema,
    RegisterSchema,
    ResendVerificationSchema,
    TokenSchema,
)

_security = HTTPBearer(auto_error=False)


def _get_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> Optional[str]:
    return credentials.credentials if credentials else None


# ── URL helpers ───────────────────────────────────────────────────────────────

def _build_verify_url(settings: RapidAuthSettings, token: str) -> str:
    """Return the full email verification link.

    Uses verify_email_url if set; otherwise falls back to the backend
    GET /auth/verify-email endpoint which verifies the token inline and
    returns JSON — useful during development without a frontend.
    """
    base = (settings.verify_email_url or f"{settings.base_url.rstrip('/')}/auth/verify-email").rstrip("/")
    return f"{base}?token={token}"


def _build_reset_url(settings: RapidAuthSettings, token: str) -> Optional[str]:
    """Return the full password-reset link, or None if no URL is configured.

    When None is returned the caller should send a dev-mode email that
    shows the raw token so the developer can test via Swagger / curl.
    """
    if settings.reset_password_url:
        return f"{settings.reset_password_url.rstrip('/')}?token={token}"
    return None


# ── Router builder ────────────────────────────────────────────────────────────

def build_router(
    user_manager: UserManager,
    settings: RapidAuthSettings,
    rate_limiter: Optional[RateLimiter] = None,
    email_sender: Optional[Any] = None,
    oauth_providers: Optional[Dict[str, Any]] = None,
    extra_kwargs_factory: Optional[Callable[..., Dict[str, Any]]] = None,
) -> APIRouter:

    router = APIRouter(prefix=settings.router_prefix, tags=settings.router_tags)

    # ── DB session dependency ─────────────────────────────────────────────────
    if extra_kwargs_factory is not None:
        async def get_extra(db=Depends(extra_kwargs_factory)) -> Dict[str, Any]:
            return {"session": db}
    else:
        async def get_extra() -> Dict[str, Any]:  # type: ignore[misc]
            return {}

    # ── Current user ──────────────────────────────────────────────────────────
    async def get_current_user(
        token: Optional[str] = Depends(_get_token),
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        from rapidauth.exceptions import TokenInvalidError
        if token is None:
            raise TokenInvalidError()
        payload = user_manager._jwt.decode_access(token)
        user = await user_manager.get_by_id(payload["sub"], **extra)
        if user is None:
            raise UserNotFoundError()
        return user

    # ── POST /register ────────────────────────────────────────────────────────
    @router.post("/register", response_model=TokenSchema, status_code=status.HTTP_201_CREATED)
    async def register(
        body: RegisterSchema,
        response: Response,
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        user = await user_manager.create_user(
            username=body.username,
            email=body.email,
            password=body.password,
            **extra,
        )
        access, refresh = await user_manager.create_token_pair(user)

        if email_sender and settings.email_verification_required:
            vtoken = await user_manager.create_verification_token(user)
            verify_url = _build_verify_url(settings, vtoken)
            await email_sender.send_verification(
                to=user_manager.get_email(user),
                verify_url=verify_url,
            )
        elif email_sender:
            await email_sender.send_welcome(
                to=user_manager.get_email(user),
                username=user_manager.get_username(user),
            )

        _set_cookies(response, settings, access, refresh)
        return _token_response(settings, access, refresh)

    # ── POST /login ───────────────────────────────────────────────────────────
    @router.post("/login", response_model=TokenSchema)
    async def login(
        body: LoginSchema,
        request: Request,
        response: Response,
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        ip = _get_client_ip(request)
        if rate_limiter and settings.rate_limit.enabled:
            await rate_limiter.check(ip)

        user = await user_manager.authenticate(body.username, body.password, **extra)

        if rate_limiter:
            await rate_limiter.reset(ip)

        access, refresh = await user_manager.create_token_pair(user)
        _set_cookies(response, settings, access, refresh)
        return _token_response(settings, access, refresh)

    # ── POST /logout ──────────────────────────────────────────────────────────
    @router.post("/logout", response_model=MessageSchema)
    async def logout(
        response: Response,
        token: Optional[str] = Depends(_get_token),
    ) -> Any:
        if token:
            user_manager._jwt.revoke(token)
        _clear_cookies(response, settings)
        return MessageSchema(message="Logged out successfully")

    # ── GET /me ───────────────────────────────────────────────────────────────
    @router.get("/me")
    async def me(user: Any = Depends(get_current_user)) -> Any:
        return _serialize_user(user, user_manager)

    # ── POST /refresh ─────────────────────────────────────────────────────────
    @router.post("/refresh", response_model=TokenSchema)
    async def refresh(
        body: Optional[RefreshSchema] = None,
        response: Response = None,
        refresh_cookie: Optional[str] = Cookie(default=None, alias="refresh_token"),
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        rt = (body.refresh_token if body else None) or refresh_cookie
        if not rt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refresh token required",
            )
        access, new_refresh = await user_manager.refresh_tokens(rt, **extra)
        _set_cookies(response, settings, access, new_refresh)
        return _token_response(settings, access, new_refresh)

    # ── GET /verify-email ─────────────────────────────────────────────────────
    # Verifies the token and returns JSON.
    # When verify_email_url is not set, email links point here directly —
    # the user clicks and sees {"message": "Email verified successfully"}.
    # When verify_email_url is set (e.g. a frontend page), this endpoint is
    # called programmatically by the frontend after reading ?token= from the URL.
    @router.get("/verify-email", response_model=MessageSchema)
    async def verify_email_get(
        token: str,
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        await user_manager.verify_email_token(token, **extra)
        return MessageSchema(message="Email verified successfully")

    # ── POST /verify-email ────────────────────────────────────────────────────
    @router.post("/verify-email", response_model=MessageSchema)
    async def verify_email_post(
        body: EmailVerifySchema,
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        await user_manager.verify_email_token(body.token, **extra)
        return MessageSchema(message="Email verified successfully")

    # ── POST /resend-verification ─────────────────────────────────────────────
    # Accepts a Bearer token (logged-in user) OR {"email": "..."} body.
    # Useful when email_verification_required=True and the user cannot log in.
    # Always returns a generic message to prevent user enumeration.
    @router.post("/resend-verification", response_model=MessageSchema)
    async def resend_verification(
        body: Optional[ResendVerificationSchema] = None,
        token: Optional[str] = Depends(_get_token),
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        if not email_sender:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email service not configured",
            )
        user = None
        if token:
            try:
                payload = user_manager._jwt.decode_access(token)
                user = await user_manager.get_by_id(payload["sub"], **extra)
            except Exception:
                pass
        elif body and body.email:
            user = await user_manager.get_by_email(body.email, **extra)

        if user and not user_manager.is_verified(user):
            vtoken = await user_manager.create_verification_token(user)
            verify_url = _build_verify_url(settings, vtoken)
            await email_sender.send_verification(
                to=user_manager.get_email(user),
                verify_url=verify_url,
            )
        return MessageSchema(
            message="If that account exists and is unverified, a verification email has been sent"
        )

    # ── POST /reset-password ──────────────────────────────────────────────────
    @router.post("/reset-password", response_model=MessageSchema)
    async def request_password_reset(
        body: PasswordResetRequestSchema,
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        token = await user_manager.create_reset_token(body.email, **extra)
        if token and email_sender:
            reset_url = _build_reset_url(settings, token)
            if reset_url:
                await email_sender.send_reset(to=body.email, reset_url=reset_url)
            else:
                # Dev mode: no reset_password_url configured.
                # Send the raw token so the developer can test via Swagger / curl.
                await email_sender.send_reset_dev(
                    to=body.email, token=token, base_url=settings.base_url
                )
        return MessageSchema(message="If that email exists, a reset link has been sent")

    # ── POST /reset-password/confirm ──────────────────────────────────────────
    @router.post("/reset-password/confirm", response_model=MessageSchema)
    async def confirm_password_reset(
        body: PasswordResetConfirmSchema,
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        await user_manager.confirm_reset(body.token, body.new_password, **extra)
        return MessageSchema(message="Password reset successfully")

    # ── POST /change-password ─────────────────────────────────────────────────
    @router.post("/change-password", response_model=MessageSchema)
    async def change_password(
        body: ChangePasswordSchema,
        user: Any = Depends(get_current_user),
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        await user_manager.change_password(user, body.old_password, body.new_password, **extra)
        return MessageSchema(message="Password changed successfully")

    # ── POST /revoke-all ──────────────────────────────────────────────────────
    @router.post("/revoke-all", response_model=MessageSchema)
    async def revoke_all(user: Any = Depends(get_current_user)) -> Any:
        await user_manager.revoke_all_tokens(user)
        return MessageSchema(message="All tokens revoked")

    # ── OAuth routes ──────────────────────────────────────────────────────────
    if oauth_providers:
        for provider_name, provider in oauth_providers.items():
            _register_oauth_routes(
                router, provider_name, provider,
                user_manager, settings, extra_kwargs_factory,
            )

    return router


# ── OAuth helper ──────────────────────────────────────────────────────────────

def _register_oauth_routes(
    router: APIRouter,
    name: str,
    provider: Any,
    user_manager: UserManager,
    settings: RapidAuthSettings,
    extra_kwargs_factory: Optional[Callable],
) -> None:
    import secrets as _secrets

    async def get_extra_inner() -> Dict[str, Any]:
        if extra_kwargs_factory is None:
            return {}
        return await extra_kwargs_factory() if callable(extra_kwargs_factory) else {}

    @router.get(f"/{name}/login", name=f"{name}_login")
    async def oauth_login() -> Any:
        state = _secrets.token_urlsafe(16)
        return RedirectResponse(url=provider.get_auth_redirect_url(state=state))

    @router.get(f"/{name}/callback", name=f"{name}_callback", response_model=TokenSchema)
    async def oauth_callback(
        code: str,
        response: Response,
        extra: Dict[str, Any] = Depends(get_extra_inner),
    ) -> Any:
        token_data = await provider.exchange_code(code)
        access_token = token_data.get("access_token")
        user_info = await provider.get_user_info(access_token)

        email = user_info.get("email")
        username = (
            user_info.get("username")
            or (email.split("@")[0] if email else f"{name}_user")
        )

        user = await user_manager.get_by_email(email, **extra) if email else None
        if user is None:
            import re
            from rapidauth.utils.helpers import generate_token

            safe_username = re.sub(r"[^a-zA-Z0-9_-]", "_", username)[:30]
            base_name = safe_username
            counter = 0
            while await user_manager.get_by_username(safe_username, **extra):
                counter += 1
                safe_username = f"{base_name}{counter}"

            user = await user_manager._db.create(
                {
                    settings.username_field: safe_username,
                    settings.email_field: email or f"{safe_username}@{name}.oauth",
                    settings.password_field: user_manager.hash_password(generate_token(16)),
                    settings.is_active_field: True,
                    settings.is_verified_field: True,
                },
                **extra,
            )

        at, rt = await user_manager.create_token_pair(user)
        _set_cookies(response, settings, at, rt)
        return _token_response(settings, at, rt)


# ── Cookie helpers ────────────────────────────────────────────────────────────

def _set_cookies(
    response: Response,
    settings: RapidAuthSettings,
    access: str,
    refresh: str,
) -> None:
    if settings.refresh_token_mode in ("cookie", "both"):
        c = settings.cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh,
            httponly=c.httponly,
            secure=c.secure,
            samesite=c.samesite,
            max_age=c.max_age or settings.refresh_token_expire,
            path=c.path,
            domain=c.domain,
        )


def _clear_cookies(response: Response, settings: RapidAuthSettings) -> None:
    response.delete_cookie("refresh_token")
    response.delete_cookie("access_token")


def _token_response(settings: RapidAuthSettings, access: str, refresh: str) -> TokenSchema:
    include_refresh = settings.refresh_token_mode in ("body", "both")
    return TokenSchema(
        access_token=access,
        refresh_token=refresh if include_refresh else None,
    )


def _serialize_user(user: Any, mgr: UserManager) -> Dict[str, Any]:
    return {
        "id": str(mgr.get_id(user)),
        "username": mgr.get_username(user),
        "email": mgr.get_email(user),
        "is_active": mgr.is_active(user),
        "is_verified": mgr.is_verified(user),
        "roles": mgr.get_roles(user),
    }


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
