"""Dashboard config API helpers."""

from __future__ import annotations

from app.dashboard.config_validate import validate_config_patch
from app.db.repo import get_tenant_row, save_tenant_config
from app.menu_v2 import (
    MenuV2Error,
    empty_menu_v2,
    migrate_legacy_menu,
    preview_flow_steps,
    validate_menu_v2,
)
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
        "status": getattr(row, "status", None) or t.status or "live",
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
            "menu_v2": cfg.get("menu_v2"),
            "menu_v2_draft": cfg.get("menu_v2_draft"),
            "messages": cfg.get("messages") or t.messages,
            "messages_draft": cfg.get("messages_draft") or cfg.get("messages") or t.messages,
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


def _draft_or_seed(row) -> dict:
    cfg = dict(row.config or {})
    if cfg.get("menu_v2_draft"):
        return validate_menu_v2(cfg["menu_v2_draft"])
    if cfg.get("menu_v2"):
        return validate_menu_v2(cfg["menu_v2"])
    if cfg.get("menu"):
        return migrate_legacy_menu(cfg["menu"])
    return empty_menu_v2()


async def publish_menu_v2(db, tenant_db_id: int, changed_by: str) -> dict:
    """Copy menu_v2_draft → menu_v2 (published). Snapshots via save_tenant_config."""
    row = await get_tenant_row(db, tenant_db_id)
    if row is None:
        return None
    if row.flow_mode != "order":
        raise MenuV2Error("menu publish only valid for order flow_mode")
    draft = _draft_or_seed(row)
    current = dict(row.config or {})
    current["menu_v2"] = draft
    current["menu_v2_draft"] = draft
    await save_tenant_config(db, tenant_db_id, name=None, config=current, changed_by=changed_by)
    invalidate_tenant(row.phone_number_id)
    row = await get_tenant_row(db, tenant_db_id)
    return tenant_config_response(row)


async def publish_messages(db, tenant_db_id: int, changed_by: str) -> dict:
    """Copy messages_draft → messages (published)."""
    from app.messages import MessagesError, validate_messages_patch, default_messages

    row = await get_tenant_row(db, tenant_db_id)
    if row is None:
        return None
    cfg = dict(row.config or {})
    draft = cfg.get("messages_draft") or cfg.get("messages")
    if not draft:
        draft = default_messages(cfg.get("greeting_language") or "roman_urdu")
    try:
        cleaned = validate_messages_patch(draft)
    except MessagesError as exc:
        raise MessagesError(str(exc)) from exc
    cfg["messages"] = cleaned
    cfg["messages_draft"] = cleaned
    await save_tenant_config(db, tenant_db_id, name=None, config=cfg, changed_by=changed_by)
    invalidate_tenant(row.phone_number_id)
    row = await get_tenant_row(db, tenant_db_id)
    return tenant_config_response(row)


def build_menu_preview(row, *, use_draft: bool = True) -> dict:
    """Preview steps from draft (default) or published menu_v2."""
    cfg = dict(row.config or {})
    if use_draft:
        menu = _draft_or_seed(row)
    else:
        raw = cfg.get("menu_v2") or cfg.get("menu_v2_draft")
        menu = validate_menu_v2(raw) if raw else _draft_or_seed(row)
    steps = preview_flow_steps(menu, to="preview")
    return {"menu": menu, "steps": steps}


async def send_menu_test(row, send_fn) -> dict:
    """Send draft menu entry payloads to owner_whatsapp."""
    t = Tenant.from_db_row(row)
    to = t.owner_whatsapp
    if not to:
        raise MenuV2Error("owner_whatsapp not set — cannot test-send")
    menu = _draft_or_seed(row)
    from app.menu_v2 import build_greeting_and_entry

    payloads = build_greeting_and_entry(to, menu)
    sent = 0
    for p in payloads:
        if p.get("type") == "text":
            body = f"[DRAFT TEST]\n{p['text']['body']}"
            ok = await send_fn(to, text=body, tenant=t)
        else:
            ok = await send_fn(to, interactive_payload=p, tenant=t)
        if ok:
            sent += 1
    return {"ok": True, "sent": sent, "to": to, "draft": True}
