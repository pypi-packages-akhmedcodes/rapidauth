from __future__ import annotations

import asyncio
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger("fastauth.email")


class EmailSender:
    """Async SMTP email sender with Jinja2-powered templates."""

    VERIFY_HTML = """
<html><body>
<h2>Verify your email address</h2>
<p>Click the link below to verify your email:</p>
<p><a href="{{ verify_url }}">{{ verify_url }}</a></p>
<p>This link expires in 24 hours.</p>
</body></html>
"""

    RESET_HTML = """
<html><body>
<h2>Password reset request</h2>
<p>Click the link below to reset your password:</p>
<p><a href="{{ reset_url }}">{{ reset_url }}</a></p>
<p>This link expires in 1 hour. If you did not request this, ignore this email.</p>
</body></html>
"""

    WELCOME_HTML = """
<html><body>
<h2>Welcome, {{ username }}!</h2>
<p>Your account has been created successfully.</p>
</body></html>
"""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: int = 30,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.timeout = timeout

    async def send(self, to: str, subject: str, html_body: str) -> bool:
        """Send an email. Returns True on success."""
        try:
            import aiosmtplib

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to
            msg.attach(MIMEText(html_body, "html"))

            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                use_tls=self.use_ssl,
                start_tls=self.use_tls,
                timeout=self.timeout,
            )
            logger.info("Email sent to %s: %s", to, subject)
            return True
        except Exception as exc:
            logger.error("Failed to send email to %s: %s", to, exc)
            return False

    async def send_verification(self, to: str, token: str, base_url: str) -> bool:
        from jinja2 import Template

        url = f"{base_url.rstrip('/')}/auth/verify-email?token={token}"
        html = Template(self.VERIFY_HTML).render(verify_url=url)
        return await self.send(to, "Verify your email address", html)

    async def send_reset(self, to: str, token: str, base_url: str) -> bool:
        from jinja2 import Template

        url = f"{base_url.rstrip('/')}/auth/reset-password/confirm?token={token}"
        html = Template(self.RESET_HTML).render(reset_url=url)
        return await self.send(to, "Password reset request", html)

    async def send_welcome(self, to: str, username: str) -> bool:
        from jinja2 import Template

        html = Template(self.WELCOME_HTML).render(username=username)
        return await self.send(to, "Welcome!", html)
