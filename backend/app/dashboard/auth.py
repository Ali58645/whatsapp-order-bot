"""
Dashboard auth — JWT with role + tenant_id scoping.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.dashboard.users import verify_password

ALGORITHM = "HS256"
TOKEN_TTL_H = 24

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthUser:
    username: str
    role: str  # admin | owner
    tenant_id: Optional[int] = None  # DB tenant PK for owners


def is_dashboard_enabled() -> bool:
    if not os.environ.get("DASHBOARD_JWT_SECRET"):
        return False
    # Enabled if env creds OR DB users (checked at login)
    return bool(os.environ.get("DASHBOARD_USER") and os.environ.get("DASHBOARD_PASSWORD"))


def _require_enabled() -> None:
    if not os.environ.get("DASHBOARD_JWT_SECRET"):
        raise HTTPException(status_code=404, detail="Not found")


def create_access_token(user: AuthUser) -> str:
    _require_enabled()
    secret = os.environ["DASHBOARD_JWT_SECRET"]
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.username,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_TTL_H),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str) -> AuthUser:
    _require_enabled()
    secret = os.environ["DASHBOARD_JWT_SECRET"]
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    return AuthUser(
        username=str(sub),
        role=str(payload.get("role", "owner")),
        tenant_id=payload.get("tenant_id"),
    )


async def authenticate(username: str, password: str) -> Optional[AuthUser]:
    """DB user first, then env-var fallback for bootstrap."""
    from app.db.engine import DB_ENABLED, get_db
    from app.db.repo import get_user_by_username

    if DB_ENABLED:
        try:
            async with get_db() as db:
                row = await get_user_by_username(db, username)
                if row and verify_password(password, row.password_hash):
                    return AuthUser(username=row.username, role=row.role, tenant_id=row.tenant_id)
                if row:
                    return None  # wrong password for known DB user
        except Exception:
            # Schema not ready / ephemeral test DB — fall through to env creds
            pass

    # Env fallback (same as v1)
    if not is_dashboard_enabled():
        return None
    import secrets
    if not secrets.compare_digest(username, os.environ["DASHBOARD_USER"]):
        return None
    stored = os.environ["DASHBOARD_PASSWORD"]
    if stored.startswith(("$2a$", "$2b$", "$2y$")):
        if not verify_password(password, stored):
            return None
    elif not secrets.compare_digest(password, stored):
        return None
    return AuthUser(username=username, role="admin", tenant_id=None)


async def require_auth(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> AuthUser:
    _require_enabled()
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_token(creds.credentials)


def require_admin(user: AuthUser = Depends(require_auth)) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


async def assert_tenant_access(user: AuthUser, tenant_db_id: int) -> None:
    """Owners may only access their tenant."""
    if user.role == "admin":
        return
    if user.tenant_id != tenant_db_id:
        raise HTTPException(status_code=403, detail="Not allowed for this tenant")
