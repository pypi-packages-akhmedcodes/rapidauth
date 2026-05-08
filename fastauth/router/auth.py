from __future__ import annotations

from typing import Any, Callable, Dict, List, Literal, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from fastauth.config.settings import FastAuthSettings
from fastauth.exceptions import UserNotFoundError
from fastauth.managers.rate_limit import RateLimiter
from fastauth.managers.user import UserManager
from fastauth.schemas.auth import (
    ChangePasswordSchema,
    EmailVerifySchema,
    LoginSchema,
    MessageSchema,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    RefreshSchema,
    RegisterSchema,
    TokenSchema,
)

_security = HTTPBearer(auto_error=False)


def _get_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> Optional[str]:
    return credentials.credentials if credentials else None


# ── Simple HTML pages returned for backend verify/reset ──────────────────────

_HTML_VERIFIED = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Email Verified</title>
<style>
  body{font-family:'Segoe UI',sans-serif;background:#0a0e1a;color:#e2e8f0;
       display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
  .card{text-align:center;background:#0f1525;border:1px solid rgba(255,255,255,.08);
        border-radius:16px;padding:3rem 2.5rem;max-width:420px;width:90%}
  .icon{font-size:4rem;margin-bottom:1rem}
  h1{font-size:1.6rem;font-weight:800;color:#34d399;margin:.5rem 0}
  p{color:#94a3b8;font-size:.95rem;line-height:1.6}
  .badge{display:inline-block;margin-top:1.2rem;padding:.4rem 1rem;background:rgba(52,211,153,.12);
         color:#34d399;border-radius:99px;font-size:.8rem;font-weight:600}
</style>
</head>
<body>
<div class="card">
  <div class="icon">✅</div>
  <h1>Email Verified!</h1>
  <p>Your email address has been successfully verified.<br>You can now close this tab and log in.</p>
  <span class="badge">Powered by FastAuth</span>
</div>
</body></html>"""

_HTML_VERIFY_ERROR = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verification Failed</title>
<style>
  body{font-family:'Segoe UI',sans-serif;background:#0a0e1a;color:#e2e8f0;
       display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
  .card{text-align:center;background:#0f1525;border:1px solid rgba(255,255,255,.08);
        border-radius:16px;padding:3rem 2.5rem;max-width:420px;width:90%}
  .icon{font-size:4rem;margin-bottom:1rem}
  h1{font-size:1.6rem;font-weight:800;color:#f87171;margin:.5rem 0}
  p{color:#94a3b8;font-size:.95rem;line-height:1.6}
  .badge{display:inline-block;margin-top:1.2rem;padding:.4rem 1rem;background:rgba(248,113,113,.12);
         color:#f87171;border-radius:99px;font-size:.8rem;font-weight:600}
</style>
</head>
<body>
<div class="card">
  <div class="icon">❌</div>
  <h1>Verification Failed</h1>
  <p>{detail}<br>The link may have expired or already been used.<br>Please request a new verification email.</p>
  <span class="badge">Powered by FastAuth</span>
</div>
</body></html>"""


def _build_verify_url(settings: FastAuthSettings, token: str) -> str:
    """Build the email verification URL based on verify_type."""
    if settings.verify_type == "frontend" and settings.frontend_url:
        base = settings.frontend_url.rstrip("/")
    else:
        base = settings.base_url.rstrip("/")
    return f"{base}/auth/verify-email?token={token}"


def _build_reset_url(settings: FastAuthSettings, token: str) -> str:
    """Build the password reset URL based on verify_type."""
    if settings.verify_type == "frontend" and settings.frontend_url:
        base = settings.frontend_url.rstrip("/")
        # frontend typically has its own reset page path
        return f"{base}/auth/reset-password?token={token}"
    else:
        base = settings.base_url.rstrip("/")
        return f"{base}/auth/reset-password/confirm?token={token}"


def build_router(
    user_manager: UserManager,
    settings: FastAuthSettings,
    rate_limiter: Optional[RateLimiter] = None,
    email_sender: Optional[Any] = None,
    oauth_providers: Optional[Dict[str, Any]] = None,
    extra_kwargs_factory: Optional[Callable[..., Dict[str, Any]]] = None,
) -> APIRouter:
    """
    Build and return the FastAuth APIRouter.

    verify_type='backend'  → GET /auth/verify-email verifies token & shows HTML
    verify_type='frontend' → GET /auth/verify-email redirects to frontend_url
    """

    router = APIRouter(prefix=settings.router_prefix, tags=settings.router_tags)

    # ── DB session dependency ─────────────────────────────────────────────────
    if extra_kwargs_factory is not None:
        async def get_extra(db=Depends(extra_kwargs_factory)) -> Dict[str, Any]:
            return {"session": db}
    else:
        async def get_extra() -> Dict[str, Any]:  # type: ignore[misc]
            return {}

    # ── get current user ──────────────────────────────────────────────────────
    async def get_current_user(
        token: Optional[str] = Depends(_get_token),
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        from fastauth.exceptions import TokenInvalidError
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

    # ── GET /verify-email  (backend: verify directly; frontend: redirect) ─────
    @router.get("/verify-email")
    async def verify_email_get(
        token: str,
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        if settings.verify_type == "frontend" and settings.frontend_url:
            # Redirect to the frontend page; frontend calls POST /auth/verify-email
            url = _build_verify_url(settings, token)
            return RedirectResponse(url=url, status_code=302)
        else:
            # Backend mode: verify the token directly and show a nice HTML page
            try:
                await user_manager.verify_email_token(token, **extra)
                return HTMLResponse(content=_HTML_VERIFIED, status_code=200)
            except Exception as exc:
                detail = getattr(exc, "detail", "Invalid or expired token")
                html = _HTML_VERIFY_ERROR.replace("{detail}", str(detail))
                return HTMLResponse(content=html, status_code=400)

    # ── POST /verify-email (programmatic — for frontend) ─────────────────────
    @router.post("/verify-email", response_model=MessageSchema)
    async def verify_email_post(
        body: EmailVerifySchema,
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        await user_manager.verify_email_token(body.token, **extra)
        return MessageSchema(message="Email verified successfully")

    # ── POST /resend-verification ─────────────────────────────────────────────
    @router.post("/resend-verification", response_model=MessageSchema)
    async def resend_verification(
        user: Any = Depends(get_current_user),
    ) -> Any:
        if not email_sender:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email service not configured",
            )
        vtoken = await user_manager.create_verification_token(user)
        verify_url = _build_verify_url(settings, vtoken)
        await email_sender.send_verification(
            to=user_manager.get_email(user),
            verify_url=verify_url,
        )
        return MessageSchema(message="Verification email sent")

    # ── POST /reset-password ──────────────────────────────────────────────────
    @router.post("/reset-password", response_model=MessageSchema)
    async def request_password_reset(
        body: PasswordResetRequestSchema,
        extra: Dict[str, Any] = Depends(get_extra),
    ) -> Any:
        token = await user_manager.create_reset_token(body.email, **extra)
        if token and email_sender:
            reset_url = _build_reset_url(settings, token)
            await email_sender.send_reset(
                to=body.email,
                reset_url=reset_url,
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
    settings: FastAuthSettings,
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
        username = user_info.get("username") or (email.split("@")[0] if email else f"{name}_user")

        user = await user_manager.get_by_email(email, **extra) if email else None
        if user is None:
            from fastauth.utils.helpers import generate_token
            import re
            safe_username = re.sub(r"[^a-zA-Z0-9_-]", "_", username)[:30]
            base = safe_username
            counter = 0
            while await user_manager.get_by_username(safe_username, **extra):
                counter += 1
                safe_username = f"{base}{counter}"

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
    settings: FastAuthSettings,
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


def _clear_cookies(response: Response, settings: FastAuthSettings) -> None:
    response.delete_cookie("refresh_token")
    response.delete_cookie("access_token")


def _token_response(settings: FastAuthSettings, access: str, refresh: str) -> TokenSchema:
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
