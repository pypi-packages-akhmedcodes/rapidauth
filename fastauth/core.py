from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, FastAPI
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from fastauth.backends.base import BaseAdapter, detect_orm
from fastauth.backends.sqlalchemy_adapter import SQLAlchemyAdapter
from fastauth.backends.tortoise_adapter import TortoiseAdapter
from fastauth.config.settings import CookieConfig, EmailConfig, FastAuthSettings, RateLimitConfig
from fastauth.email.sender import EmailSender
from fastauth.exceptions import TokenInvalidError, UserNotFoundError
from fastauth.hashing.handler import HashingHandler
from fastauth.jwt.handler import JWTHandler
from fastauth.jwt.store import InMemoryTokenStore
from fastauth.managers.rate_limit import RateLimiter
from fastauth.managers.user import UserManager
from fastauth.middleware.auth import AuthMiddleware
from fastauth.router.auth import build_router


_bearer = HTTPBearer(auto_error=False)


class FastAuth:
    """
    Main entry point for FastAuth.

    Minimal usage::

        auth = FastAuth(user_model=User, jwt_secret="supersecret")
        app.include_router(auth.router)

    Advanced usage::

        auth = FastAuth(
            user_model=User,
            username_field="login",
            email_field="mail",
            password_field="passwd",
            jwt={"secret": "...", "algorithm": "HS256", "access_expire": 900},
            refresh_token_mode="cookie",
            password_hasher="argon2",
            email={"host": "smtp.gmail.com", "port": 587, ...},
            social_auth={"google": {"client_id": "...", "client_secret": "...", "redirect_uri": "..."}},
        )
    """

    def __init__(
        self,
        user_model: type,
        # ── Simple JWT shortcut ──────────────────────────────────────────────
        jwt_secret: Optional[str] = None,
        # ── Full JWT config dict ─────────────────────────────────────────────
        jwt: Optional[Dict[str, Any]] = None,
        # ── Field mappings ───────────────────────────────────────────────────
        username_field: str = "username",
        email_field: str = "email",
        password_field: str = "password",
        id_field: str = "id",
        is_active_field: str = "is_active",
        is_verified_field: str = "is_verified",
        roles_field: str = "roles",
        permissions_field: str = "permissions",
        # ── Token delivery ────────────────────────────────────────────────────
        refresh_token_mode: str = "body",
        # ── Cookie config ─────────────────────────────────────────────────────
        cookie: Optional[Dict[str, Any]] = None,
        # ── Password hashing ─────────────────────────────────────────────────
        password_hasher: str = "bcrypt",
        # ── Email config ──────────────────────────────────────────────────────
        email: Optional[Dict[str, Any]] = None,
        # ── Social OAuth ──────────────────────────────────────────────────────
        social_auth: Optional[Dict[str, Dict[str, str]]] = None,
        # ── Rate limiting ─────────────────────────────────────────────────────
        rate_limit: Optional[Dict[str, Any]] = None,
        # ── Feature flags ─────────────────────────────────────────────────────
        email_verification_required: bool = False,
        enable_refresh_rotation: bool = True,
        # ── Router ───────────────────────────────────────────────────────────
        router_prefix: str = "/auth",
        router_tags: Optional[List[str]] = None,
        # ── Database (for SQLAlchemy) ─────────────────────────────────────────
        get_db: Optional[Callable] = None,
        # ── Base URL for email links ──────────────────────────────────────────
        base_url: str = "http://localhost:8000",
        # ── Custom token store (e.g., Redis) ──────────────────────────────────
        token_store: Optional[Any] = None,
    ) -> None:
        # ── Build settings ────────────────────────────────────────────────────
        jwt_cfg = jwt or {}
        secret = jwt_cfg.get("secret") or jwt_secret
        if not secret:
            raise ValueError(
                "FastAuth requires a JWT secret. "
                "Pass jwt_secret='...' or jwt={'secret': '...'}"
            )

        self._settings = FastAuthSettings(
            username_field=username_field,
            email_field=email_field,
            password_field=password_field,
            id_field=id_field,
            is_active_field=is_active_field,
            is_verified_field=is_verified_field,
            roles_field=roles_field,
            permissions_field=permissions_field,
            jwt_secret=secret,
            jwt_algorithm=jwt_cfg.get("algorithm", "HS256"),
            access_token_expire=jwt_cfg.get("access_expire", 900),
            refresh_token_expire=jwt_cfg.get("refresh_expire", 604800),
            refresh_token_mode=refresh_token_mode,
            cookie=CookieConfig(**(cookie or {})),
            password_hasher=password_hasher,
            email=EmailConfig(**(email or {})) if email else None,
            social_auth=social_auth,
            rate_limit=RateLimitConfig(**(rate_limit or {})),
            email_verification_required=email_verification_required,
            enable_refresh_rotation=enable_refresh_rotation,
            router_prefix=router_prefix,
            router_tags=router_tags or ["Authentication"],
        )

        # ── JWT handler ───────────────────────────────────────────────────────
        self._jwt = JWTHandler(
            secret=secret,
            algorithm=self._settings.jwt_algorithm,
            access_expire=self._settings.access_token_expire,
            refresh_expire=self._settings.refresh_token_expire,
        )

        # ── Password hasher ───────────────────────────────────────────────────
        self._hasher = HashingHandler(scheme=password_hasher)

        # ── ORM adapter ───────────────────────────────────────────────────────
        orm = detect_orm(user_model)
        if get_db is not None:
            self._adapter: BaseAdapter = SQLAlchemyAdapter(
                user_model, get_db=get_db, id_field=id_field
            )
        elif orm == "tortoise":
            self._adapter = TortoiseAdapter(user_model, id_field=id_field)
        elif orm in ("sqlalchemy", "sqlmodel"):
            raise ValueError(
                f"Detected {orm} model but no `get_db` dependency provided. "
                "Pass get_db=your_async_session_dependency to FastAuth()."
            )
        else:
            # Generic fallback — developer must handle DB ops via callbacks
            self._adapter = TortoiseAdapter(user_model, id_field=id_field)

        # ── Token store ───────────────────────────────────────────────────────
        self._token_store = token_store or InMemoryTokenStore()

        # ── User manager ──────────────────────────────────────────────────────
        self._manager = UserManager(
            adapter=self._adapter,
            settings=self._settings,
            jwt=self._jwt,
            hasher=self._hasher,
            token_store=self._token_store,
        )

        # ── Rate limiter ──────────────────────────────────────────────────────
        rl_cfg = self._settings.rate_limit
        self._rate_limiter = RateLimiter(
            max_attempts=rl_cfg.max_login_attempts,
            window_seconds=rl_cfg.lockout_seconds,
        ) if rl_cfg.enabled else None

        # ── Email sender ──────────────────────────────────────────────────────
        self._email: Optional[EmailSender] = None
        if self._settings.email:
            ec = self._settings.email
            self._email = EmailSender(
                host=ec.host,
                port=ec.port,
                username=ec.username,
                password=ec.password,
                from_email=ec.from_email,
                use_tls=ec.use_tls,
                use_ssl=ec.use_ssl,
                timeout=ec.timeout,
            )

        # ── OAuth providers ───────────────────────────────────────────────────
        self._oauth: Dict[str, Any] = {}
        if social_auth:
            self._oauth = _build_oauth_providers(social_auth)

        # ── Build router ──────────────────────────────────────────────────────
        self._router = build_router(
            user_manager=self._manager,
            settings=self._settings,
            rate_limiter=self._rate_limiter,
            email_sender=self._email,
            oauth_providers=self._oauth,
            base_url=base_url,
            extra_kwargs_factory=get_db,
        )

        self._base_url = base_url
        self._get_db = get_db  # stored so get_current_user() can inject it

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def router(self) -> APIRouter:
        return self._router

    @property
    def manager(self) -> UserManager:
        return self._manager

    # ── Dependency: get current user ──────────────────────────────────────────

    def get_current_user(self) -> Callable:
        """
        Returns a FastAPI dependency that resolves to the authenticated user.

        Usage::

            @router.get("/profile")
            async def profile(user=Depends(auth.get_current_user())):
                return user
        """
        jwt_handler = self._jwt
        manager = self._manager
        get_db = self._get_db  # may be None (Tortoise) or a generator dep (SQLAlchemy)

        if get_db is not None:
            # SQLAlchemy / SQLModel: inject session via Depends so FastAPI
            # handles the generator lifecycle correctly (no direct await).
            async def _dep(
                creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
                db=Depends(get_db),
            ) -> Any:
                token = creds.credentials if creds else None
                if token is None:
                    raise TokenInvalidError()
                payload = jwt_handler.decode_access(token)
                user = await manager.get_by_id(payload["sub"], session=db)
                if user is None:
                    raise UserNotFoundError()
                return user
        else:
            # Tortoise ORM / generic: no session needed.
            async def _dep(  # type: ignore[misc]
                creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
            ) -> Any:
                token = creds.credentials if creds else None
                if token is None:
                    raise TokenInvalidError()
                payload = jwt_handler.decode_access(token)
                user = await manager.get_by_id(payload["sub"])
                if user is None:
                    raise UserNotFoundError()
                return user

        return _dep

    def current_user_dependency(self) -> Callable:
        """Alias for get_current_user() — pick the name you prefer."""
        return self.get_current_user()

    # ── Middleware convenience ────────────────────────────────────────────────

    def add_middleware(self, app: FastAPI) -> None:
        """Attach AuthMiddleware so request.state.user is always available."""
        app.add_middleware(AuthMiddleware, jwt_handler=self._jwt, user_manager=self._manager)

    # ── User manager helpers (convenience proxies) ────────────────────────────

    async def create_user(self, username: str, email: str, password: str, **kw: Any) -> Any:
        return await self._manager.create_user(username, email, password, **kw)

    async def authenticate(self, username_or_email: str, password: str, **kw: Any) -> Any:
        return await self._manager.authenticate(username_or_email, password, **kw)

    def hash_password(self, password: str) -> str:
        return self._manager.hash_password(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return self._manager.verify_password(plain, hashed)


# ── OAuth provider factory ────────────────────────────────────────────────────

def _build_oauth_providers(social_auth: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    from fastauth.oauth.discord import DiscordOAuth
    from fastauth.oauth.github import GitHubOAuth
    from fastauth.oauth.google import GoogleOAuth

    _map = {
        "google": GoogleOAuth,
        "github": GitHubOAuth,
        "discord": DiscordOAuth,
    }
    providers: Dict[str, Any] = {}
    for name, cfg in social_auth.items():
        cls = _map.get(name.lower())
        if cls is None:
            import warnings
            warnings.warn(f"FastAuth: unknown OAuth provider '{name}', skipping")
            continue
        providers[name] = cls(
            client_id=cfg["client_id"],
            client_secret=cfg["client_secret"],
            redirect_uri=cfg["redirect_uri"],
        )
    return providers
