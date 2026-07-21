"""
Async repository layer — all DB reads/writes go through here.

Pattern:
  - Every public function accepts a SQLAlchemy AsyncSession.
  - Callers use `async with get_db() as db:` from engine.py.
  - Functions never commit — the context manager does that.
  - All functions are no-ops / raise if DB is not enabled; callers
    guard with `if DB_ENABLED` before calling.

Tenant upsert:
  sync_tenants_to_db(tenants) — called at startup to mirror the JSON config.

Session CRUD:
  get_or_create_session   — load active session for (tenant_db_id, contact_id)
  save_session_state      — write phase + meta + history + status back
  close_session           — mark status=closed/confirmed/stalled

Contact upsert:
  get_or_create_contact   — upsert by (tenant_db_id, wa_id)

Mute CRUD:
  set_mute / get_mute_until / clear_mute

Lead upsert:
  upsert_lead_record      — create or update the leads row for a session

Order create:
  create_order_record

Event append:
  append_event
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("orderbot.repo")


# ── Import models lazily to avoid circular imports at module load ─────────────

def _m():
    from app.db import models
    return models


# ── Tenants ───────────────────────────────────────────────────────────────────

async def sync_tenants_to_db(session: AsyncSession, tenants: list) -> None:
    """
    First-boot seed: insert tenants from JSON/env if missing.
    Existing rows are NOT overwritten — DB config is source of truth after seed.
    New rows get messages catalog seeded to match current Bahi POS defaults.
    """
    m = _m()
    from app.messages import seed_messages_into_config

    now = datetime.now(timezone.utc)
    for t in tenants:
        result = await session.execute(
            select(m.DBTenant).where(m.DBTenant.phone_number_id == t.phone_number_id)
        )
        row = result.scalar_one_or_none()
        config = t.model_dump(exclude={"phone_number_id", "name", "flow_mode", "status"})
        config.pop("_raw_config", None)
        config = seed_messages_into_config(
            config,
            flow_mode=t.flow_mode,
            greeting_language=getattr(t, "greeting_language", "roman_urdu"),
        )
        if row is None:
            row = m.DBTenant(
                phone_number_id=t.phone_number_id,
                name=t.name,
                flow_mode=t.flow_mode,
                status=getattr(t, "status", None) or "live",
                config=config,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            log.info(f"repo: seeded tenant {t.phone_number_id!r}")
        else:
            # Ensure messages exist on old rows without overwriting custom config
            if not (row.config or {}).get("messages"):
                row.config = seed_messages_into_config(
                    dict(row.config or {}),
                    flow_mode=row.flow_mode,
                    greeting_language=(row.config or {}).get("greeting_language", "roman_urdu"),
                )
                row.updated_at = now
                log.info(f"repo: seeded messages for existing tenant {t.phone_number_id!r}")
            else:
                log.info(f"repo: tenant {t.phone_number_id!r} exists — config unchanged")


async def create_tenant(
    session: AsyncSession,
    *,
    name: str,
    flow_mode: str,
    phone_number_id: str,
    business_wa_id: str = "",
    owner_whatsapp: str = "",
    greeting_language: str = "roman_urdu",
    status: str = "draft",
    config: dict | None = None,
    template_id: str | None = None,
) -> Any:
    """Create a new tenant row (admin). Returns DBTenant."""
    m = _m()
    from app.messages import seed_messages_into_config

    existing = await get_tenant_row_by_phone(session, phone_number_id)
    if existing is not None:
        raise ValueError(f"phone_number_id already exists: {phone_number_id}")

    now = datetime.now(timezone.utc)
    cfg = dict(config or {})
    cfg.setdefault("business_wa_id", business_wa_id)
    cfg.setdefault("owner_whatsapp", owner_whatsapp)
    cfg.setdefault("greeting_language", greeting_language)

    if template_id:
        from app.onboarding import apply_template_to_config
        cfg = apply_template_to_config(
            cfg,
            template_id=template_id,
            flow_mode=flow_mode,
            greeting_language=greeting_language,
            business_name=name,
        )
    else:
        cfg = seed_messages_into_config(
            cfg, flow_mode=flow_mode, greeting_language=greeting_language
        )
        if flow_mode == "order":
            if not cfg.get("menu_v2"):
                from app.menu_v2 import empty_menu_v2 as _empty
                menu = _empty()
                cfg["menu_v2"] = menu
                cfg["menu_v2_draft"] = menu
            if not cfg.get("menu"):
                cfg["menu"] = {
                    "shop_name": name,
                    "delivery_fee": 100,
                    "delivery_area": "",
                    "categories": [
                        {"name": "Items", "items": [{"name": "Sample", "price": 100}]}
                    ],
                }

    row = m.DBTenant(
        phone_number_id=phone_number_id,
        name=name,
        flow_mode=flow_mode,
        status=status,
        config=cfg,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def set_tenant_status(
    session: AsyncSession,
    tenant_db_id: int,
    status: str,
    *,
    enforce_transitions: bool = True,
) -> Any:
    """
    Update tenant lifecycle status.

    Allowed transitions (when enforce_transitions=True):
      draft  → live | paused | archived
      live   → paused | archived
      paused → live | archived
      archived → paused   (restore — never jump straight to live)
    """
    allowed = {"draft", "live", "paused", "archived"}
    if status not in allowed:
        raise ValueError(f"status must be one of {sorted(allowed)}")
    row = await get_tenant_row(session, tenant_db_id)
    if row is None:
        return None
    current = (getattr(row, "status", None) or "live").lower()
    if enforce_transitions and current != status:
        transitions = {
            "draft": {"live", "paused", "archived"},
            "live": {"paused", "archived"},
            "paused": {"live", "archived"},
            "archived": {"paused"},
        }
        ok = transitions.get(current, set())
        if status not in ok:
            raise ValueError(
                f"Cannot change status from {current!r} to {status!r}. "
                f"Allowed: {sorted(ok) or 'none'}"
            )
    row.status = status
    row.updated_at = datetime.now(timezone.utc)
    return row


async def delete_tenant_permanently(
    session: AsyncSession,
    tenant_db_id: int,
    *,
    confirm_name: str,
) -> dict:
    """
    Permanently delete an *archived* tenant and all cascaded records.
    confirm_name must match the tenant name (case-sensitive strip).
    """
    from sqlalchemy import delete, update

    m = _m()
    row = await get_tenant_row(session, tenant_db_id)
    if row is None:
        raise LookupError("Tenant not found")
    status = (getattr(row, "status", None) or "live").lower()
    if status != "archived":
        raise ValueError("Only archived tenants can be permanently deleted")
    if (confirm_name or "").strip() != (row.name or "").strip():
        raise ValueError("confirm_name does not match business name")

    phone = row.phone_number_id
    name = row.name

    # Child tables that reference sessions/contacts first
    await session.execute(delete(m.DBLead).where(m.DBLead.tenant_id == tenant_db_id))
    await session.execute(delete(m.DBOrder).where(m.DBOrder.tenant_id == tenant_db_id))
    await session.execute(delete(m.DBEvent).where(m.DBEvent.tenant_id == tenant_db_id))
    await session.execute(delete(m.DBMute).where(m.DBMute.tenant_id == tenant_db_id))
    await session.execute(delete(m.DBSession).where(m.DBSession.tenant_id == tenant_db_id))
    await session.execute(delete(m.DBContact).where(m.DBContact.tenant_id == tenant_db_id))
    await session.execute(
        delete(m.DBConfigHistory).where(m.DBConfigHistory.tenant_id == tenant_db_id)
    )
    # Detach owner users rather than deleting admin accounts
    await session.execute(
        update(m.DBUser)
        .where(m.DBUser.tenant_id == tenant_db_id)
        .values(tenant_id=None)
    )
    await session.execute(delete(m.DBTenant).where(m.DBTenant.id == tenant_db_id))
    await session.flush()
    return {"id": tenant_db_id, "phone_number_id": phone, "name": name, "deleted": True}


async def get_tenant_row(session: AsyncSession, tenant_db_id: int):
    m = _m()
    result = await session.execute(
        select(m.DBTenant).where(m.DBTenant.id == tenant_db_id)
    )
    return result.scalar_one_or_none()


async def get_tenant_row_by_phone(session: AsyncSession, phone_number_id: str):
    m = _m()
    result = await session.execute(
        select(m.DBTenant).where(m.DBTenant.phone_number_id == phone_number_id)
    )
    return result.scalar_one_or_none()


async def save_tenant_config(
    session: AsyncSession,
    tenant_db_id: int,
    *,
    name: str | None,
    config: dict,
    changed_by: str,
) -> None:
    """Save config + snapshot previous version to config_history."""
    m = _m()
    result = await session.execute(
        select(m.DBTenant).where(m.DBTenant.id == tenant_db_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ValueError(f"tenant {tenant_db_id} not found")

    # Snapshot previous config
    hist = m.DBConfigHistory(
        tenant_id=tenant_db_id,
        config=dict(row.config or {}),
        changed_by=changed_by,
        created_at=datetime.now(timezone.utc),
    )
    session.add(hist)

    if name is not None:
        row.name = name
    row.config = config
    row.updated_at = datetime.now(timezone.utc)


async def get_user_by_username(session: AsyncSession, username: str):
    m = _m()
    result = await session.execute(
        select(m.DBUser).where(m.DBUser.username == username)
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password_hash: str,
    role: str,
    tenant_id: int | None = None,
):
    m = _m()
    user = m.DBUser(
        username=username,
        password_hash=password_hash,
        role=role,
        tenant_id=tenant_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.flush()
    return user


async def list_users(session: AsyncSession) -> list:
    m = _m()
    result = await session.execute(
        select(m.DBUser).order_by(m.DBUser.created_at.desc())
    )
    return list(result.scalars().all())


async def get_db_tenant_id(session: AsyncSession, phone_number_id: str) -> Optional[int]:
    """Return the DB integer PK for a tenant by its phone_number_id."""
    m = _m()
    result = await session.execute(
        select(m.DBTenant.id).where(m.DBTenant.phone_number_id == phone_number_id)
    )
    return result.scalar_one_or_none()


# ── Contacts ──────────────────────────────────────────────────────────────────

async def get_or_create_contact(
    session: AsyncSession,
    tenant_db_id: int,
    wa_id: str,
    profile_name: str = "",
    channel: str = "whatsapp",
) -> "Any":  # DBContact
    """Upsert contact; return the DBContact row."""
    m = _m()
    result = await session.execute(
        select(m.DBContact).where(
            m.DBContact.tenant_id == tenant_db_id,
            m.DBContact.channel == channel,
            m.DBContact.wa_id == wa_id,
        )
    )
    contact = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if contact is None:
        contact = m.DBContact(
            tenant_id=tenant_db_id,
            channel=channel,
            wa_id=wa_id,
            profile_name=profile_name or "",
            first_seen=now,
            last_seen=now,
        )
        session.add(contact)
        await session.flush()  # get contact.id
    else:
        contact.last_seen = now
        if profile_name:
            contact.profile_name = profile_name
    return contact


# ── Sessions ──────────────────────────────────────────────────────────────────

async def get_active_session(
    session: AsyncSession,
    tenant_db_id: int,
    contact_id: int,
) -> "Any | None":  # DBSession | None
    """Return the active DBSession for (tenant, contact), or None."""
    m = _m()
    result = await session.execute(
        select(m.DBSession).where(
            m.DBSession.tenant_id == tenant_db_id,
            m.DBSession.contact_id == contact_id,
            m.DBSession.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def create_session(
    session: AsyncSession,
    tenant_db_id: int,
    contact_id: int,
    flow_mode: str,
    phase: str = "GREETING",
    meta: dict | None = None,
    channel: str = "whatsapp",
) -> "Any":  # DBSession
    """Create a new active session row."""
    m = _m()
    now = datetime.now(timezone.utc)
    db_session = m.DBSession(
        tenant_id=tenant_db_id,
        contact_id=contact_id,
        channel=channel,
        flow_mode=flow_mode,
        phase=phase,
        meta=meta or {},
        history=[],
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(db_session)
    await session.flush()
    return db_session


async def save_session_state(
    session: AsyncSession,
    db_session_row: "Any",
    *,
    phase: str | None = None,
    meta: dict | None = None,
    history: list | None = None,
    status: str | None = None,
) -> None:
    """Patch updated fields onto the session row."""
    if phase is not None:
        db_session_row.phase = phase
    if meta is not None:
        db_session_row.meta = meta
    if history is not None:
        db_session_row.history = history
    if status is not None:
        db_session_row.status = status
    db_session_row.updated_at = datetime.now(timezone.utc)


async def close_session(
    session: AsyncSession,
    db_session_row: "Any",
    status: str = "closed",
) -> None:
    """Mark session as closed/confirmed/stalled."""
    await save_session_state(session, db_session_row, status=status)


# ── Mutes ─────────────────────────────────────────────────────────────────────

async def set_mute(
    session: AsyncSession,
    tenant_db_id: int,
    wa_id: str,
    muted_until: datetime,
    channel: str = "whatsapp",
) -> None:
    """Upsert a mute record."""
    m = _m()
    result = await session.execute(
        select(m.DBMute).where(
            m.DBMute.tenant_id == tenant_db_id,
            m.DBMute.channel == channel,
            m.DBMute.wa_id == wa_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = m.DBMute(
            tenant_id=tenant_db_id,
            channel=channel,
            wa_id=wa_id,
            muted_until=muted_until,
        )
        session.add(row)
    else:
        row.muted_until = muted_until


async def get_mute_until(
    session: AsyncSession,
    tenant_db_id: int,
    wa_id: str,
) -> datetime | None:
    """Return muted_until datetime or None if not muted."""
    m = _m()
    result = await session.execute(
        select(m.DBMute.muted_until).where(
            m.DBMute.tenant_id == tenant_db_id,
            m.DBMute.wa_id == wa_id,
        )
    )
    return result.scalar_one_or_none()


async def clear_mute(
    session: AsyncSession,
    tenant_db_id: int,
    wa_id: str,
) -> None:
    """Delete mute record."""
    m = _m()
    await session.execute(
        delete(m.DBMute).where(
            m.DBMute.tenant_id == tenant_db_id,
            m.DBMute.wa_id == wa_id,
        )
    )


# ── Leads ─────────────────────────────────────────────────────────────────────

async def upsert_lead_record(
    session: AsyncSession,
    tenant_db_id: int,
    contact_id: int,
    session_id: int,
    meta: dict,
) -> None:
    """Create or update the leads row for this session."""
    m = _m()
    contact = await session.get(m.DBContact, contact_id)
    channel = getattr(contact, "channel", "whatsapp") if contact else "whatsapp"
    result = await session.execute(
        select(m.DBLead).where(m.DBLead.session_id == session_id)
    )
    lead = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    fields = {
        "business_name":  meta.get("business_name", ""),
        "business_type":  meta.get("business_type", ""),
        "locations":      meta.get("locations", ""),
        "current_system": meta.get("current_system", ""),
        "demo_slot":      meta.get("demo_slot", ""),
        "entry_intent":   meta.get("entry_intent", ""),
        "ad_source":      meta.get("lead_source", ""),
    }

    if lead is None:
        lead = m.DBLead(
            tenant_id=tenant_db_id,
            contact_id=contact_id,
            session_id=session_id,
            channel=channel,
            **fields,
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add(lead)
    else:
        for k, v in fields.items():
            setattr(lead, k, v)
        lead.updated_at = now

    # Mirror status from phase
    phase = meta.get("phase", "")
    if phase == "CONFIRMED":
        lead.status = "confirmed"
    elif phase == "STALLED":
        lead.status = "stalled"


# ── Orders ────────────────────────────────────────────────────────────────────

async def create_order_record(
    session: AsyncSession,
    tenant_db_id: int,
    contact_id: int,
    session_id: int,
    order: dict,
) -> None:
    """Insert a confirmed order row."""
    m = _m()
    contact = await session.get(m.DBContact, contact_id)
    channel = getattr(contact, "channel", "whatsapp") if contact else "whatsapp"
    row = m.DBOrder(
        tenant_id=tenant_db_id,
        contact_id=contact_id,
        session_id=session_id,
        channel=channel,
        items=order.get("items", []),
        total=int(order.get("total", 0)),
        delivery_address=order.get("address", ""),
        status="confirmed",
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)


# ── Events ────────────────────────────────────────────────────────────────────

async def append_event(
    session: AsyncSession,
    tenant_db_id: int,
    event_type: str,
    payload: dict,
    contact_id: int | None = None,
    channel: str | None = None,
) -> None:
    """Append one audit event row."""
    m = _m()
    row = m.DBEvent(
        tenant_id=tenant_db_id,
        contact_id=contact_id,
        channel=channel,
        type=event_type,
        payload=payload,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)


# ── Access log (admin support audit) ──────────────────────────────────────────

async def append_access_log(
    session: AsyncSession,
    *,
    admin_username: str,
    action: str,
    tenant_id: int | None = None,
    tenant_name: str = "",
    detail: dict | None = None,
) -> Any:
    m = _m()
    row = m.DBAccessLog(
        admin_username=admin_username,
        tenant_id=tenant_id,
        tenant_name=tenant_name or "",
        action=action,
        detail=dict(detail or {}),
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()
    return row


async def list_access_logs(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    m = _m()
    result = await session.execute(
        select(m.DBAccessLog)
        .order_by(m.DBAccessLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    out = []
    for row in result.scalars().all():
        out.append({
            "id": row.id,
            "admin_username": row.admin_username,
            "tenant_id": row.tenant_id,
            "tenant_name": row.tenant_name or "",
            "action": row.action,
            "detail": row.detail or {},
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })
    return out
