from .base import OAuthProvider
from .google import GoogleOAuth
from .github import GitHubOAuth
from .discord import DiscordOAuth

__all__ = ["OAuthProvider", "GoogleOAuth", "GitHubOAuth", "DiscordOAuth"]
