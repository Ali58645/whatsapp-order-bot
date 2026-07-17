"""
Live tenant config from DB with 60s in-process cache.

When DATABASE_URL is set, resolve_tenant() reads from DB (cached).
When not set, falls back to the in-memory registry from tenants.json/env.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from app.tenants import Tenant, get_tenant as _registry_get

log = logging.getLogger("orderbot.tenant_resolver")

CACHE_TTL_S = 60
_cache: dict[str, tuple[Tenant, float]] = {}


def invalidate_tenant(phone_number_id: str) -> None:
    _cache.pop(phone_number_id, None)


def invalidate_all() -> None:
    _cache.clear()


async def resolve_tenant(phone_number_id: str) -> Optional[Tenant]:
    """Return tenant config for routing — DB-backed when enabled."""
    from app.db.engine import DB_ENABLED

    if not DB_ENABLED:
        return _registry_get(phone_number_id)

    now = time.monotonic()
    cached = _cache.get(phone_number_id)
    if cached and (now - cached[1]) < CACHE_TTL_S:
        return cached[0]

    try:
        from app.db.engine import get_db
        from app.db.models import DBTenant
        from sqlalchemy import select

        async with get_db() as db:
            result = await db.execute(
                select(DBTenant).where(DBTenant.phone_number_id == phone_number_id)
            )
            row = result.scalar_one_or_none()
        if row is None:
            return _registry_get(phone_number_id)
        tenant = Tenant.from_db_row(row)
        _cache[phone_number_id] = (tenant, now)
        return tenant
    except Exception as exc:
        log.error(f"tenant_resolver: DB load failed for {phone_number_id} — {exc}")
        return _registry_get(phone_number_id)
