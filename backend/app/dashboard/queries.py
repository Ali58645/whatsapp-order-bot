"""
Dashboard read queries — plain SELECTs over existing models.
All tenant-scoped via phone_number_id or "all".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    DBContact,
    DBEvent,
    DBLead,
    DBMute,
    DBOrder,
    DBSession,
    DBTenant,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _day_start(dt: datetime | None = None) -> datetime:
    now = dt or _utc_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


async def _tenant_ids(
    db: AsyncSession, tenant_phone_id: str | None
) -> list[int] | None:
    """
    Resolve filter to DB tenant PKs.
    None / "all" → no filter (return None).
    Specific phone_number_id → [id] or [] if unknown.
    """
    if not tenant_phone_id or tenant_phone_id == "all":
        return None
    result = await db.execute(
        select(DBTenant.id).where(DBTenant.phone_number_id == tenant_phone_id)
    )
    row = result.scalar_one_or_none()
    return [row] if row is not None else []


def _apply_tenant(stmt: Select, col, tenant_ids: list[int] | None) -> Select:
    if tenant_ids is None:
        return stmt
    if not tenant_ids:
        return stmt.where(col == -1)  # empty result
    return stmt.where(col.in_(tenant_ids))


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ── Tenants ───────────────────────────────────────────────────────────────────

async def list_tenants(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(DBTenant).order_by(DBTenant.name)
    )
    rows = result.scalars().all()
    today = _day_start(_utc_now())
    out = []
    for t in rows:
        leads_today = int(
            (
                await db.execute(
                    select(func.count(DBLead.id)).where(
                        DBLead.tenant_id == t.id,
                        DBLead.created_at >= today,
                    )
                )
            ).scalar_one()
        )
        orders_today = int(
            (
                await db.execute(
                    select(func.count(DBOrder.id)).where(
                        DBOrder.tenant_id == t.id,
                        DBOrder.created_at >= today,
                    )
                )
            ).scalar_one()
        )
        cfg = t.config or {}
        out.append({
            "id": t.id,
            "phone_number_id": t.phone_number_id,
            "name": t.name,
            "flow_mode": t.flow_mode,
            "status": getattr(t, "status", None) or "live",
            "business_wa_id": cfg.get("business_wa_id") or "",
            "owner_whatsapp": cfg.get("owner_whatsapp") or "",
            "leads_today": leads_today,
            "orders_today": orders_today,
            "stat_today": leads_today if t.flow_mode == "lead" else orders_today,
        })
    return out


# ── Overview ──────────────────────────────────────────────────────────────────

async def overview(db: AsyncSession, tenant_phone_id: str | None = None) -> dict:
    tids = await _tenant_ids(db, tenant_phone_id)
    now = _utc_now()
    today = _day_start(now)
    week = today - timedelta(days=7)

    # Leads today / week
    async def _lead_count(since: datetime) -> int:
        stmt = select(func.count(DBLead.id)).where(DBLead.created_at >= since)
        stmt = _apply_tenant(stmt, DBLead.tenant_id, tids)
        return int((await db.execute(stmt)).scalar_one())

    leads_today = await _lead_count(today)
    leads_week = await _lead_count(week)

    # Leads by status
    stmt = select(DBLead.status, func.count(DBLead.id)).group_by(DBLead.status)
    stmt = _apply_tenant(stmt, DBLead.tenant_id, tids)
    by_status_rows = (await db.execute(stmt)).all()
    leads_by_status = {row[0] or "unknown": int(row[1]) for row in by_status_rows}

    # Demos scheduled = leads with demo_slot set and status confirmed (or any with slot)
    stmt = select(func.count(DBLead.id)).where(
        DBLead.demo_slot != "",
        DBLead.status == "confirmed",
    )
    stmt = _apply_tenant(stmt, DBLead.tenant_id, tids)
    demos_scheduled = int((await db.execute(stmt)).scalar_one())

    # Orders today + revenue
    stmt = select(func.count(DBOrder.id), func.coalesce(func.sum(DBOrder.total), 0)).where(
        DBOrder.created_at >= today
    )
    stmt = _apply_tenant(stmt, DBOrder.tenant_id, tids)
    order_row = (await db.execute(stmt)).one()
    orders_today = int(order_row[0])
    revenue_today = int(order_row[1])

    # Active conversations
    stmt = select(func.count(DBSession.id)).where(DBSession.status == "active")
    stmt = _apply_tenant(stmt, DBSession.tenant_id, tids)
    active_conversations = int((await db.execute(stmt)).scalar_one())

    # Recent events
    events = await list_events(db, tenant_phone_id=tenant_phone_id, limit=20, offset=0)

    return {
        "leads_today": leads_today,
        "leads_this_week": leads_week,
        "leads_by_status": leads_by_status,
        "demos_scheduled": demos_scheduled,
        "orders_today": orders_today,
        "revenue_today": revenue_today,
        "active_conversations": active_conversations,
        "recent_events": events["items"],
    }


# ── Leads ─────────────────────────────────────────────────────────────────────

def _lead_dict(lead: DBLead, contact: DBContact | None = None) -> dict:
    c = contact or lead.contact
    return {
        "id": lead.id,
        "tenant_id": lead.tenant_id,
        "contact_id": lead.contact_id,
        "session_id": lead.session_id,
        "business_name": lead.business_name,
        "business_type": lead.business_type,
        "locations": lead.locations,
        "current_system": lead.current_system,
        "demo_slot": lead.demo_slot,
        "entry_intent": lead.entry_intent,
        "ad_source": lead.ad_source,
        "status": lead.status,
        "created_at": _iso(lead.created_at),
        "updated_at": _iso(lead.updated_at),
        "last_activity": _iso(lead.updated_at or lead.created_at),
        "contact": {
            "id": c.id if c else None,
            "wa_id": c.wa_id if c else "",
            "profile_name": c.profile_name if c else "",
        },
    }


async def list_leads(
    db: AsyncSession,
    *,
    tenant_phone_id: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    tids = await _tenant_ids(db, tenant_phone_id)
    stmt = (
        select(DBLead)
        .options(selectinload(DBLead.contact))
        .order_by(DBLead.updated_at.desc())
    )
    stmt = _apply_tenant(stmt, DBLead.tenant_id, tids)

    if status:
        stmt = stmt.where(DBLead.status == status)
    if date_from:
        stmt = stmt.where(DBLead.created_at >= date_from)
    if date_to:
        stmt = stmt.where(DBLead.created_at <= date_to)
    if search:
        q = f"%{search.strip()}%"
        stmt = stmt.join(DBContact, DBLead.contact_id == DBContact.id).where(
            or_(
                DBLead.business_name.ilike(q),
                DBContact.profile_name.ilike(q),
                DBContact.wa_id.ilike(q),
            )
        )

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await db.execute(count_stmt)).scalar_one())

    stmt = stmt.limit(min(limit, 200)).offset(max(offset, 0))
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_lead_dict(r) for r in rows],
    }


async def get_lead(db: AsyncSession, lead_id: int) -> dict | None:
    result = await db.execute(
        select(DBLead)
        .options(
            selectinload(DBLead.contact),
            selectinload(DBLead.session),
        )
        .where(DBLead.id == lead_id)
    )
    lead = result.scalar_one_or_none()
    if lead is None:
        return None
    data = _lead_dict(lead)
    sess = lead.session
    data["history"] = list(sess.history or []) if sess else []
    data["phase"] = sess.phase if sess else None
    data["session_status"] = sess.status if sess else None
    return data


# ── Orders ────────────────────────────────────────────────────────────────────

def _order_dict(order: DBOrder) -> dict:
    c = order.contact
    return {
        "id": order.id,
        "tenant_id": order.tenant_id,
        "contact_id": order.contact_id,
        "session_id": order.session_id,
        "items": order.items or [],
        "total": order.total,
        "delivery_address": order.delivery_address,
        "location_lat": order.location_lat,
        "location_lng": order.location_lng,
        "status": order.status,
        "created_at": _iso(order.created_at),
        "contact": {
            "id": c.id if c else None,
            "wa_id": c.wa_id if c else "",
            "profile_name": c.profile_name if c else "",
        },
    }


async def list_orders(
    db: AsyncSession,
    *,
    tenant_phone_id: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    tids = await _tenant_ids(db, tenant_phone_id)
    stmt = (
        select(DBOrder)
        .options(selectinload(DBOrder.contact))
        .order_by(DBOrder.created_at.desc())
    )
    stmt = _apply_tenant(stmt, DBOrder.tenant_id, tids)
    if status:
        stmt = stmt.where(DBOrder.status == status)
    if date_from:
        stmt = stmt.where(DBOrder.created_at >= date_from)
    if date_to:
        stmt = stmt.where(DBOrder.created_at <= date_to)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await db.execute(count_stmt)).scalar_one())

    stmt = stmt.limit(min(limit, 200)).offset(max(offset, 0))
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_order_dict(r) for r in rows],
    }


# ── Conversations ─────────────────────────────────────────────────────────────

MESSAGING_WINDOW_S = 24 * 3600


def _aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def messaging_window_open(last_inbound_at: datetime | None) -> bool:
    """True when a free-form session message may be sent (Meta 24h window)."""
    if last_inbound_at is None:
        return False
    return (_utc_now() - _aware_utc(last_inbound_at)).total_seconds() < MESSAGING_WINDOW_S


async def send_agent_reply(
    db: AsyncSession,
    *,
    contact_id: int,
    text: str,
    agent_username: str = "",
) -> dict:
    """Send dashboard agent reply; persist history, mute, and human_takeover event."""
    from app.gate import MUTE_DURATION_S, mute_contact
    from app.main import send_whatsapp_message
    from app.db.repo import (
        append_event,
        create_session,
        get_active_session,
        save_session_state,
        set_mute,
    )
    from app.sessions import save_session as mem_save_session
    from app.tenants import Tenant, get_tenant

    contact = (
        await db.execute(select(DBContact).where(DBContact.id == contact_id))
    ).scalar_one_or_none()
    if contact is None:
        raise LookupError("contact_not_found")

    if not messaging_window_open(contact.last_seen):
        raise ValueError("window_closed")

    tenant_row = (
        await db.execute(select(DBTenant).where(DBTenant.id == contact.tenant_id))
    ).scalar_one_or_none()
    if tenant_row is None:
        raise LookupError("tenant_not_found")

    tenant = get_tenant(tenant_row.phone_number_id)
    if tenant is None:
        tenant = Tenant.from_db_row(tenant_row)

    ok = await send_whatsapp_message(contact.wa_id, text, tenant=tenant)
    if not ok:
        raise RuntimeError("send_failed")

    agent_msg = {"role": "human_agent", "content": text, "sender": "human_agent"}
    db_sess = await get_active_session(db, contact.tenant_id, contact.id)
    if db_sess is None:
        db_sess = await create_session(
            db,
            contact.tenant_id,
            contact.id,
            flow_mode=tenant.flow_mode,
            phase="GREETING",
            meta={},
        )
        history = [agent_msg]
    else:
        history = list(db_sess.history or [])
        history.append(agent_msg)

    await save_session_state(db, db_sess, history=history)
    mem_save_session(contact.wa_id, history, tenant_id=tenant.phone_number_id)

    mute_contact(contact.wa_id, tenant.phone_number_id, MUTE_DURATION_S)
    muted_until = _utc_now() + timedelta(seconds=MUTE_DURATION_S)
    await set_mute(db, contact.tenant_id, contact.wa_id, muted_until)
    await append_event(
        db,
        contact.tenant_id,
        "human_takeover",
        {
            "wa_id": contact.wa_id,
            "source": "dashboard_send",
            "agent": agent_username,
        },
        contact_id=contact.id,
    )
    await db.flush()

    return await conversation_for_contact(db, contact_id)


async def conversation_for_contact(
    db: AsyncSession, contact_id: int
) -> dict | None:
    contact = (
        await db.execute(select(DBContact).where(DBContact.id == contact_id))
    ).scalar_one_or_none()
    if contact is None:
        return None

    result = await db.execute(
        select(DBSession)
        .where(DBSession.contact_id == contact_id)
        .order_by(DBSession.updated_at.desc())
    )
    sessions = result.scalars().all()

    # Prefer active, else most recent
    active = next((s for s in sessions if s.status == "active"), None)
    primary = active or (sessions[0] if sessions else None)

    timeline: list[dict] = []
    for s in sessions:
        for msg in s.history or []:
            timeline.append({
                "session_id": s.id,
                "session_status": s.status,
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

    muted_until = None
    mute_row = (
        await db.execute(
            select(DBMute).where(
                DBMute.tenant_id == contact.tenant_id,
                DBMute.wa_id == contact.wa_id,
            )
        )
    ).scalar_one_or_none()
    if mute_row:
        muted_until = _iso(mute_row.muted_until)

    return {
        "contact": {
            "id": contact.id,
            "wa_id": contact.wa_id,
            "profile_name": contact.profile_name,
            "tenant_id": contact.tenant_id,
            "first_seen": _iso(contact.first_seen),
            "last_seen": _iso(contact.last_seen),
        },
        "muted_until": muted_until,
        "window_open": messaging_window_open(contact.last_seen),
        "last_inbound_at": _iso(contact.last_seen),
        "active_session_id": primary.id if primary else None,
        "phase": primary.phase if primary else None,
        "history": list(primary.history or []) if primary else [],
        "timeline": timeline,
    }


# ── Events ────────────────────────────────────────────────────────────────────

async def list_events(
    db: AsyncSession,
    *,
    tenant_phone_id: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    tids = await _tenant_ids(db, tenant_phone_id)
    stmt = (
        select(DBEvent)
        .options(selectinload(DBEvent.contact))
        .order_by(DBEvent.created_at.desc())
    )
    stmt = _apply_tenant(stmt, DBEvent.tenant_id, tids)
    if event_type:
        stmt = stmt.where(DBEvent.type == event_type)

    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int((await db.execute(count_stmt)).scalar_one())

    stmt = stmt.limit(min(limit, 200)).offset(max(offset, 0))
    rows = (await db.execute(stmt)).scalars().all()
    items = []
    for e in rows:
        c = e.contact
        items.append({
            "id": e.id,
            "tenant_id": e.tenant_id,
            "contact_id": e.contact_id,
            "type": e.type,
            "payload": e.payload or {},
            "created_at": _iso(e.created_at),
            "contact": {
                "id": c.id if c else None,
                "wa_id": c.wa_id if c else "",
                "profile_name": c.profile_name if c else "",
            } if c else None,
        })
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }
