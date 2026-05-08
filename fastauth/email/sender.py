from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("fastauth.email")


class EmailSender:
    """Async SMTP email sender with Jinja2-powered templates."""

    VERIFY_HTML = """
<html><body style="font-family:sans-serif;background:#f8fafc;padding:2rem">
<div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:2rem;box-shadow:0 2px 12px rgba(0,0,0,.08)">
  <h2 style="color:#6366f1">Verify your email address</h2>
  <p style="color:#64748b">Click the button below to verify your email. This link expires in <strong>24 hours</strong>.</p>
  <a href="{{ verify_url }}" style="display:inline-block;margin:1.2rem 0;padding:.75rem 1.5rem;background:#6366f1;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">
    Verify Email
  </a>
  <p style="font-size:.82rem;color:#94a3b8">Or copy this link:<br><a href="{{ verify_url }}" style="color:#6366f1;word-break:break-all">{{ verify_url }}</a></p>
  <p style="font-size:.78rem;color:#cbd5e1">If you did not create an account, ignore this email.</p>
</div>
</body></html>
"""

    RESET_HTML = """
<html><body style="font-family:sans-serif;background:#f8fafc;padding:2rem">
<div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:2rem;box-shadow:0 2px 12px rgba(0,0,0,.08)">
  <h2 style="color:#6366f1">Password reset request</h2>
  <p style="color:#64748b">Click the button below to reset your password. This link expires in <strong>1 hour</strong>.</p>
  <a href="{{ reset_url }}" style="display:inline-block;margin:1.2rem 0;padding:.75rem 1.5rem;background:#6366f1;color:#fff;border-radius:8px;text-decoration:none;font-weight:600">
    Reset Password
  </a>
  <p style="font-size:.82rem;color:#94a3b8">Or copy this link:<br><a href="{{ reset_url }}" style="color:#6366f1;word-break:break-all">{{ reset_url }}</a></p>
  <p style="font-size:.78rem;color:#cbd5e1">If you did not request this, ignore this email.</p>
</div>
</body></html>
"""

    WELCOME_HTML = """
<html><body style="font-family:sans-serif;background:#f8fafc;padding:2rem">
<div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;padding:2rem;box-shadow:0 2px 12px rgba(0,0,0,.08)">
  <h2 style="color:#6366f1">Welcome, {{ username }}! 🎉</h2>
  <p style="color:#64748b">Your account has been created successfully.</p>
</div>
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

    async def send_verification(self, to: str, verify_url: str) -> bool:
        """Send email verification link. `verify_url` is the full URL."""
        from jinja2 import Template
        html = Template(self.VERIFY_HTML).render(verify_url=verify_url)
        return await self.send(to, "Verify your email address", html)

    async def send_reset(self, to: str, reset_url: str) -> bool:
        """Send password reset link. `reset_url` is the full URL."""
        from jinja2 import Template
        html = Template(self.RESET_HTML).render(reset_url=reset_url)
        return await self.send(to, "Password reset request", html)

    async def send_welcome(self, to: str, username: str) -> bool:
        from jinja2 import Template
        html = Template(self.WELCOME_HTML).render(username=username)
        return await self.send(to, "Welcome!", html)
