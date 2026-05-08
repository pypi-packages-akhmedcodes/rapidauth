from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class OAuthProvider(ABC):
    """Base class for all OAuth2 social-login providers."""

    name: str = "base"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    @property
    @abstractmethod
    def authorization_url(self) -> str:
        """OAuth2 authorization endpoint."""

    @property
    @abstractmethod
    def token_url(self) -> str:
        """OAuth2 token endpoint."""

    @abstractmethod
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Fetch profile info from provider using the access token."""

    def get_auth_redirect_url(self, state: str = "") -> str:
        """Build the provider's authorization URL with required params."""
        from urllib.parse import urlencode

        params: Dict[str, str] = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": self.scope,
        }
        if state:
            params["state"] = state
        return f"{self.authorization_url}?{urlencode(params)}"

    @property
    @abstractmethod
    def scope(self) -> str:
        """OAuth2 scope string."""

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange an authorization code for tokens."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
