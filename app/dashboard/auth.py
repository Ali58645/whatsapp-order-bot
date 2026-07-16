"""
Dashboard auth — env-gated JWT login.

Required env vars (all three, or dashboard routes return 404):
  DASHBOARD_USER
  DASHBOARD_PASSWORD   — plain text, or bcrypt hash ($2b$… / $2a$…)
  DASHBOARD_JWT_SECRET
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ALGORITHM = "HS256"
TOKEN_TTL_H = 24

_bearer = HTTPBearer(auto_error=False)


def is_dashboard_enabled() -> bool:
    return bool(
        os.environ.get("DASHBOARD_USER")
        and os.environ.get("DASHBOARD_PASSWORD")
        and os.environ.get("DASHBOARD_JWT_SECRET")
    )


def _require_enabled() -> None:
    if not is_dashboard_enabled():
        raise HTTPException(status_code=404, detail="Not found")


def _password_ok(provided: str, stored: str) -> bool:
    if stored.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            import bcrypt
            return bcrypt.checkpw(provided.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    return secrets.compare_digest(provided, stored)


def verify_login(username: str, password: str) -> bool:
    _require_enabled()
    expected_user = os.environ["DASHBOARD_USER"]
    expected_pass = os.environ["DASHBOARD_PASSWORD"]
    if not secrets.compare_digest(username, expected_user):
        return False
    return _password_ok(password, expected_pass)


def create_access_token(username: str) -> str:
    _require_enabled()
    secret = os.environ["DASHBOARD_JWT_SECRET"]
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_TTL_H),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    _require_enabled()
    secret = os.environ["DASHBOARD_JWT_SECRET"]
    try:
        return jwt.decode(token, secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def require_auth(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> str:
    """Dependency: valid Bearer JWT → username. Missing/bad → 401. Disabled → 404."""
    _require_enabled()
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_token(creds.credentials)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return str(sub)
