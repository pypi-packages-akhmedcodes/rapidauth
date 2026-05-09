from __future__ import annotations

from typing import Any, Dict

import httpx

from .base import OAuthProvider


class GitHubOAuth(OAuthProvider):
    name = "github"

    @property
    def authorization_url(self) -> str:
        return "https://github.com/login/oauth/authorize"

    @property
    def token_url(self) -> str:
        return "https://github.com/login/oauth/access_token"

    @property
    def scope(self) -> str:
        return "read:user user:email"

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        headers = {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        async with httpx.AsyncClient() as client:
            user_resp = await client.get("https://api.github.com/user", headers=headers)
            user_resp.raise_for_status()
            user_data = user_resp.json()

            email = user_data.get("email")
            if not email:
                emails_resp = await client.get(
                    "https://api.github.com/user/emails", headers=headers
                )
                if emails_resp.status_code == 200:
                    emails = emails_resp.json()
                    primary = next((e for e in emails if e.get("primary")), None)
                    email = primary["email"] if primary else None

        return {
            "provider_id": str(user_data.get("id")),
            "email": email,
            "username": user_data.get("login"),
            "name": user_data.get("name"),
            "picture": user_data.get("avatar_url"),
            "email_verified": True,
        }
