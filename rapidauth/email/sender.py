from __future__ import annotations

import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("rapidauth.email")


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

    RESET_DEV_HTML = """
<html><body style="font-family:sans-serif;background:#f8fafc;padding:2rem">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:2rem;box-shadow:0 2px 12px rgba(0,0,0,.08)">
  <h2 style="color:#6366f1">Password reset request <span style="font-size:.7em;color:#94a3b8">(dev mode)</span></h2>
  <p style="color:#64748b;font-size:.9rem"><strong>reset_password_url</strong> is not configured.<br>Use the token below to test via Swagger or curl:</p>
  <div style="background:#f1f5f9;border-radius:8px;padding:1rem 1.2rem;margin:1rem 0;font-family:monospace;font-size:.95rem;word-break:break-all;color:#1e293b">{{ token }}</div>
  <p style="color:#64748b;font-size:.88rem;margin:.5rem 0 .3rem">Test with curl:</p>
  <pre style="background:#0f172a;color:#7dd3fc;border-radius:8px;padding:1rem 1.2rem;font-size:.8rem;overflow-x:auto;margin:.4rem 0">curl -X POST {{ base_url }}/auth/reset-password/confirm \
  -H "Content-Type: application/json" \
  -d '{"token": "{{ token }}", "new_password": "YourNewPassword1!"}'</pre>
  <p style="font-size:.78rem;color:#cbd5e1;margin-top:1rem">This token expires in 1 hour. Set <code>reset_password_url</code> in RapidAuth() for production.</p>
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

    async def send_reset_dev(self, to: str, token: str, base_url: str = "http://localhost:8000") -> bool:
        """Dev-mode reset email: shows raw token + curl example.

        Sent when reset_password_url is not configured.  Switch to send_reset()
        by setting reset_password_url in RapidAuth() before going to production.
        """
        from jinja2 import Template
        html = Template(self.RESET_DEV_HTML).render(token=token, base_url=base_url.rstrip("/"))
        return await self.send(to, "[DEV] Password reset token", html)

    async def send_welcome(self, to: str, username: str) -> bool:
        from jinja2 import Template
        html = Template(self.WELCOME_HTML).render(username=username)
        return await self.send(to, "Welcome!", html)
