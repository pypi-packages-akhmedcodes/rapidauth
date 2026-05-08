from __future__ import annotations

from typing import Any, Dict

import httpx

from .base import OAuthProvider


class DiscordOAuth(OAuthProvider):
    name = "discord"

    @property
    def authorization_url(self) -> str:
        return "https://discord.com/api/oauth2/authorize"

    @property
    def token_url(self) -> str:
        return "https://discord.com/api/oauth2/token"

    @property
    def scope(self) -> str:
        return "identify email"

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()

        return {
            "provider_id": str(data.get("id")),
            "email": data.get("email"),
            "username": data.get("username"),
            "name": data.get("global_name") or data.get("username"),
            "picture": (
                f"https://cdn.discordapp.com/avatars/{data['id']}/{data['avatar']}.png"
                if data.get("avatar")
                else None
            ),
            "email_verified": data.get("verified", False),
        }
