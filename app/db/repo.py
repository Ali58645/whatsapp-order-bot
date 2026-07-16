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
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger("orderbot.repo")


# ── Import models lazily to avoid circular imports at module load ─────────────

def _m():
    from app.db import models
    return models


# ── Tenants ───────────────────────────────────────────────────────────────────

async def sync_tenants_to_db(session: AsyncSession, tenants: list) -> None:
    """
    Upsert each Tenant pydantic object into the tenants table.
    Called once at startup after load_tenants().
    """
    m = _m()
    for t in tenants:
        result = await session.execute(
            select(m.DBTenant).where(m.DBTenant.phone_number_id == t.phone_number_id)
        )
        row = result.scalar_one_or_none()
        config = t.model_dump(exclude={"phone_number_id", "name", "flow_mode"})
        if row is None:
            row = m.DBTenant(
                phone_number_id=t.phone_number_id,
                name=t.name,
                flow_mode=t.flow_mode,
                config=config,
            )
            session.add(row)
            log.info(f"repo: inserted tenant {t.phone_number_id!r}")
        else:
            row.name = t.name
            row.flow_mode = t.flow_mode
            row.config = config
            log.info(f"repo: updated tenant {t.phone_number_id!r}")


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
) -> "Any":  # DBContact
    """Upsert contact; return the DBContact row."""
    m = _m()
    result = await session.execute(
        select(m.DBContact).where(
            m.DBContact.tenant_id == tenant_db_id,
            m.DBContact.wa_id == wa_id,
        )
    )
    contact = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if contact is None:
        contact = m.DBContact(
            tenant_id=tenant_db_id,
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
) -> "Any":  # DBSession
    """Create a new active session row."""
    m = _m()
    now = datetime.now(timezone.utc)
    db_session = m.DBSession(
        tenant_id=tenant_db_id,
        contact_id=contact_id,
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
) -> None:
    """Upsert a mute record."""
    m = _m()
    result = await session.execute(
        select(m.DBMute).where(
            m.DBMute.tenant_id == tenant_db_id,
            m.DBMute.wa_id == wa_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = m.DBMute(tenant_id=tenant_db_id, wa_id=wa_id, muted_until=muted_until)
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
    row = m.DBOrder(
        tenant_id=tenant_db_id,
        contact_id=contact_id,
        session_id=session_id,
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
) -> None:
    """Append one audit event row."""
    m = _m()
    row = m.DBEvent(
        tenant_id=tenant_db_id,
        contact_id=contact_id,
        type=event_type,
        payload=payload,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
