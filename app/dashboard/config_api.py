"""Dashboard config API helpers."""

from __future__ import annotations

from app.dashboard.config_validate import validate_config_patch
from app.db.repo import get_tenant_row, save_tenant_config
from app.tenant_resolver import invalidate_tenant
from app.tenants import Tenant


def tenant_config_response(row) -> dict:
    t = Tenant.from_db_row(row)
    cfg = dict(row.config or {})
    return {
        "id": row.id,
        "phone_number_id": row.phone_number_id,
        "name": row.name,
        "flow_mode": row.flow_mode,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "config": {
            **cfg,
            "greeting_text": t.greeting_text,
            "greeting_language": t.greeting_language,
            "campaign_phrase": t.campaign_phrase,
            "demo_slots": t.demo_slots,
            "facts_features": t.facts_features or t.facts,
            "facts_pricing_note": t.facts_pricing_note,
            "facts_claims_note": t.facts_claims_note,
            "faq": t.faq_list,
            "menu": t.menu.model_dump() if t.menu else None,
            "business_wa_id": t.business_wa_id,
            "owner_whatsapp": t.owner_whatsapp,
        },
    }


async def apply_config_save(db, tenant_db_id: int, patch: dict, changed_by: str) -> dict:
    row = await get_tenant_row(db, tenant_db_id)
    if row is None:
        return None
    cleaned = validate_config_patch(row.flow_mode, patch)
    current = dict(row.config or {})
    name = cleaned.pop("name", None)
    current.update(cleaned)
    await save_tenant_config(db, tenant_db_id, name=name, config=current, changed_by=changed_by)
    invalidate_tenant(row.phone_number_id)
    row = await get_tenant_row(db, tenant_db_id)
    return tenant_config_response(row)
