from __future__ import annotations

from typing import Any, Dict

import httpx

from .base import OAuthProvider


class GoogleOAuth(OAuthProvider):
    name = "google"

    @property
    def authorization_url(self) -> str:
        return "https://accounts.google.com/o/oauth2/v2/auth"

    @property
    def token_url(self) -> str:
        return "https://oauth2.googleapis.com/token"

    @property
    def scope(self) -> str:
        return "openid email profile"

    def get_auth_redirect_url(self, state: str = "") -> str:
        from urllib.parse import urlencode

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": self.scope,
            "access_type": "offline",
        }
        if state:
            params["state"] = state
        return f"{self.authorization_url}?{urlencode(params)}"

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
        return {
            "provider_id": data.get("sub"),
            "email": data.get("email"),
            "username": data.get("email", "").split("@")[0],
            "name": data.get("name"),
            "picture": data.get("picture"),
            "email_verified": data.get("email_verified", False),
        }
