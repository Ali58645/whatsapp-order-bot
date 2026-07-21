"""
Live tenant config from DB with 60s in-process cache.

When DATABASE_URL is set, resolve_tenant() reads from DB only (cached).
JSON/env registry is first-boot seed via sync_tenants_to_db — not consulted
for request routing after DB is enabled.

When DATABASE_URL is absent, falls back to the in-memory registry (local/tests).
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
            # After seeding, unknown numbers are ignored — do not fall back to env registry
            log.warning(
                f"tenant_resolver: no DB row for phone_number_id={phone_number_id!r}"
            )
            return None
        # Archived tenants never route
        status = getattr(row, "status", "live") or "live"
        if status == "archived":
            log.info(f"tenant_resolver: tenant {phone_number_id!r} archived — ignore")
            return None
        tenant = Tenant.from_db_row(row)
        _cache[phone_number_id] = (tenant, now)
        return tenant
    except Exception as exc:
        log.error(f"tenant_resolver: DB load failed for {phone_number_id} — {exc}")
        # Soft fallback only on hard DB failure (keeps bot up during outages)
        return _registry_get(phone_number_id)


async def resolve_tenant_for_channel(
    channel: str,
    account_id: str,
) -> Optional[Tenant]:
    """Resolve tenant by channel account id (WA phone_number_id, IG id, Page id)."""
    if channel == "whatsapp":
        return await resolve_tenant(account_id)

    from app.db.engine import DB_ENABLED

    if not DB_ENABLED:
        return None

    try:
        from app.db.engine import get_db
        from app.db.models import DBTenant
        from sqlalchemy import select

        async with get_db() as db:
            result = await db.execute(select(DBTenant))
            rows = result.scalars().all()
        for row in rows:
            t = Tenant.from_db_row(row)
            cfg = t.channel_config(channel)
            if str(cfg.get("account_id") or "") == str(account_id):
                if getattr(row, "status", "live") == "archived":
                    return None
                return t
    except Exception as exc:
        log.error(
            "tenant_resolver: channel lookup failed %s/%s — %s",
            channel,
            account_id,
            exc,
        )
    return None
