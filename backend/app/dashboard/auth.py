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
    impersonated_by: Optional[str] = None  # admin username when view-as
    readonly: bool = False  # legacy read-only flag (support mode is writable)


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
    if user.impersonated_by:
        payload["impersonated_by"] = user.impersonated_by
    if user.readonly:
        payload["readonly"] = True
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
        impersonated_by=payload.get("impersonated_by"),
        readonly=bool(payload.get("readonly")),
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
    if user.readonly:
        raise HTTPException(status_code=403, detail="Read-only session")
    return user


def assert_writable(user: AuthUser) -> None:
    """Block mutations only for explicitly read-only sessions."""
    if user.readonly:
        raise HTTPException(
            status_code=403,
            detail="Read-only view — exit View as owner to make changes",
        )


async def audit_support_action(
    user: AuthUser,
    action: str,
    *,
    tenant_id: int | None = None,
    tenant_name: str = "",
    detail: dict | None = None,
) -> None:
    """Persist an access-log row when an admin is in support (view-as) mode."""
    if not user.impersonated_by:
        return
    from app.db.engine import DB_ENABLED, get_db
    from app.db.repo import append_access_log, get_tenant_row

    if not DB_ENABLED:
        return
    tid = tenant_id if tenant_id is not None else user.tenant_id
    name = tenant_name
    try:
        async with get_db() as db:
            if tid is not None and not name:
                row = await get_tenant_row(db, tid)
                if row is not None:
                    name = row.name or ""
            await append_access_log(
                db,
                admin_username=user.impersonated_by,
                action=action,
                tenant_id=tid,
                tenant_name=name,
                detail=detail,
            )
    except Exception:
        # Never fail the primary action because of audit write issues
        pass


# Config keys owners must never change (wiring / credentials)
OWNER_FORBIDDEN_CONFIG_KEYS = frozenset({
    "business_wa_id",
    "owner_whatsapp",
    "sheet",
    "phone_number_id",
    "flow_mode",
})


def assert_owner_config_patch(user: AuthUser, patch: dict) -> None:
    """Owners cannot edit wiring fields; admins can."""
    if user.role == "admin" and not user.readonly:
        return
    assert_writable(user)
    bad = sorted(k for k in patch.keys() if k in OWNER_FORBIDDEN_CONFIG_KEYS)
    # Nested onboarding.waba_id / connection fields
    if "onboarding" in patch and isinstance(patch["onboarding"], dict):
        wiring_ob = {"waba_id", "connection_verified", "subscribed_apps", "verified_name"}
        if wiring_ob & set(patch["onboarding"].keys()):
            bad.append("onboarding.wiring")
    if bad:
        raise HTTPException(
            status_code=403,
            detail=f"Owners cannot edit wiring fields: {', '.join(bad)} (managed by AccellionX)",
        )


async def assert_tenant_access(user: AuthUser, tenant_db_id: int) -> None:
    """Owners (and view-as sessions) may only access their tenant."""
    if user.role == "admin":
        return
    if user.tenant_id != tenant_db_id:
        raise HTTPException(status_code=403, detail="Not allowed for this tenant")
