from __future__ import annotations

from typing import Literal


class HashingHandler:
    """
    Password hashing — wraps bcrypt or argon2-cffi directly.

    Security properties:
    - bcrypt: adaptive cost, salted, timing-safe verify (via bcrypt.checkpw)
    - argon2: memory-hard, resistant to GPU/ASIC, recommended for new projects
    """

    def __init__(self, scheme: Literal["bcrypt", "argon2"] = "bcrypt") -> None:
        self._scheme = scheme
        if scheme == "bcrypt":
            try:
                import bcrypt as _bcrypt  # noqa: F401
            except ImportError:
                raise ImportError("Install bcrypt: pip install bcrypt")
        else:
            try:
                from argon2 import PasswordHasher  # noqa: F401
            except ImportError:
                raise ImportError("Install argon2-cffi: pip install argon2-cffi")

    def hash(self, password: str) -> str:
        """Return a salted hash of `password`."""
        if self._scheme == "bcrypt":
            import bcrypt
            return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        else:
            from argon2 import PasswordHasher
            ph = PasswordHasher()
            return ph.hash(password)

    def verify(self, plain: str, hashed: str) -> bool:
        """Timing-safe comparison of `plain` against `hashed`."""
        if self._scheme == "bcrypt":
            import bcrypt
            try:
                return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
            except Exception:
                return False
        else:
            from argon2 import PasswordHasher
            from argon2.exceptions import VerifyMismatchError
            ph = PasswordHasher()
            try:
                return ph.verify(hashed, plain)
            except VerifyMismatchError:
                return False
            except Exception:
                return False

    def needs_rehash(self, hashed: str) -> bool:
        """True if the hash should be upgraded (e.g., cost factor changed)."""
        if self._scheme == "argon2":
            from argon2 import PasswordHasher
            ph = PasswordHasher()
            return ph.check_needs_rehash(hashed)
        return False
