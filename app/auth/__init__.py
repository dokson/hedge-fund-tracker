"""
Authentication and user management.

Built on fastapi-users v14, with:
- SQLAlchemy backend (DB-backed users + sessions)
- Cookie transport (HttpOnly, SameSite=Lax)
- DatabaseStrategy for tokens (revocable; supports "sign out all devices")
- Argon2id password hashing (via pwdlib, fastapi-users default)
- Email verification REQUIRED for non-public actions

Wiring is in `app/server.py` via `include_routers_for_auth(app)`.
"""

from app.auth.dependencies import (
    current_active_user,
    current_active_verified_user,
    current_optional_user,
    current_superuser,
)
from app.auth.routes import include_routers_for_auth

__all__ = [
    "current_active_user",
    "current_active_verified_user",
    "current_optional_user",
    "current_superuser",
    "include_routers_for_auth",
]
