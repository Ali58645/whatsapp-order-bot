"""
System health snapshot — DB, tenants, dashboard static, migrations.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, text

log = logging.getLogger("orderbot.health")


def _registry_tenant_statuses() -> list[dict[str, str]]:
    from app.tenants import get_all_tenants

    out: list[dict[str, str]] = []
    for t in get_all_tenants():
        out.append(
            {
                "phone_number_id": t.phone_number_id,
                "name": t.name or "",
                "status": (getattr(t, "status", None) or "live").lower(),
            }
        )
    return out


async def build_health_report(
    *,
    dashboard_built: bool,
    dashboard_dir: str,
) -> dict[str, Any]:
    from app.dashboard.auth import is_dashboard_enabled
    from app.db.engine import DB_ENABLED, DATABASE_URL, get_db
    from app.db.models import DBTenant

    report: dict[str, Any] = {
        "status": "running",
        "database": {
            "enabled": DB_ENABLED,
            "connected": False,
        },
        "tenant_count": 0,
        "tenants": [],
        "tenant_statuses": [],
        "dashboard": {
            "url": "/dashboard",
            "mounted": dashboard_built,
            "built": dashboard_built,
            "path": dashboard_dir,
            "auth_configured": is_dashboard_enabled(),
        },
        "migrations_at_head": None,
    }

    tenant_statuses: list[dict[str, str]] = []
    db_connected = False

    if DB_ENABLED:
        try:
            async with get_db() as db:
                await db.execute(text("SELECT 1"))
                db_connected = True
                result = await db.execute(
                    select(
                        DBTenant.phone_number_id,
                        DBTenant.name,
                        DBTenant.status,
                    ).order_by(DBTenant.name)
                )
                for phone_number_id, name, status in result.all():
                    st = (status or "live").lower()
                    tenant_statuses.append(
                        {
                            "phone_number_id": phone_number_id,
                            "name": name or "",
                            "status": st,
                        }
                    )
        except Exception as exc:
            log.warning("health: database probe failed — %s", exc)
            report["status"] = "degraded"

        report["database"]["connected"] = db_connected

        if not db_connected:
            tenant_statuses = _registry_tenant_statuses()

        try:
            from app.db.migrate import check_migrations_at_head

            report["migrations_at_head"] = check_migrations_at_head(DATABASE_URL)
        except Exception as exc:
            log.warning("health: migration check failed — %s", exc)
            report["migrations_at_head"] = None
    else:
        tenant_statuses = _registry_tenant_statuses()

    report["tenant_statuses"] = tenant_statuses
    report["tenant_count"] = len(tenant_statuses)
    report["tenants"] = [t["phone_number_id"] for t in tenant_statuses]
    return report
