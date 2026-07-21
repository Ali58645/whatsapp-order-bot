"""Owner self-serve endpoints: pause bot, password, team, export, broadcast, notes."""

from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.dashboard import auth as dash_auth
from app.dashboard import queries
from app.dashboard.users import hash_password, verify_password

router = APIRouter(tags=["dashboard-owner"])


def _require_db() -> None:
    from app.db.engine import DB_ENABLED

    if not DB_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Dashboard requires DATABASE_URL (Postgres). Running in in-memory mode.",
        )


def _get_db():
    from app.db.engine import get_db

    return get_db()


def _owner_tenant_id(user: dash_auth.AuthUser) -> int:
    if user.role == "admin" and user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Select a business first")
    tid = user.tenant_id
    if tid is None:
        raise HTTPException(status_code=403, detail="Owner missing tenant")
    return int(tid)


class PauseBody(BaseModel):
    status: str = Field(..., pattern="^(live|paused)$")


@router.post("/api/dashboard/my-business/status")
async def owner_set_status(
    body: PauseBody,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """Owner: pause or resume their bot (live ↔ paused only)."""
    _require_db()
    dash_auth.assert_writable(user)
    tid = _owner_tenant_id(user)
    from app.db.repo import set_tenant_status
    from app.tenant_resolver import invalidate_tenant

    async with _get_db() as db:
        try:
            row = await set_tenant_status(db, tid, body.status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if row is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        phone = row.phone_number_id
        st = row.status
    invalidate_tenant(phone)
    await dash_auth.audit_support_action(
        user, "owner_status", tenant_id=tid, detail={"status": st}
    )
    return {"id": tid, "status": st, "phone_number_id": phone}


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/api/dashboard/me/password")
async def change_password(
    body: ChangePasswordBody,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    dash_auth.assert_writable(user)
    from app.db.repo import get_user_by_username, update_user_password

    async with _get_db() as db:
        row = await get_user_by_username(db, user.username)
        if row is None:
            raise HTTPException(
                status_code=400,
                detail="Password change is only available for database users",
            )
        if not verify_password(body.current_password, row.password_hash):
            raise HTTPException(status_code=400, detail="Current password is wrong")
        await update_user_password(db, row.id, hash_password(body.new_password))
    return {"ok": True}


class ProfileBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    logo_url: str = Field("", max_length=2048)


@router.patch("/api/dashboard/my-business/profile")
async def owner_update_profile(
    body: ProfileBody,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """Owner: update business display name + profile picture URL."""
    _require_db()
    dash_auth.assert_writable(user)
    tid = _owner_tenant_id(user)
    from app.db.repo import get_tenant_row
    from app.tenant_resolver import invalidate_tenant

    name = (body.name or "").strip()[:256]
    if not name:
        raise HTTPException(status_code=400, detail="Business name is required")
    logo = (body.logo_url or "").strip()
    if logo and not logo.lower().startswith("https://"):
        raise HTTPException(status_code=400, detail="Picture must be an https:// link")
    logo = logo[:2048]

    async with _get_db() as db:
        row = await get_tenant_row(db, tid)
        if row is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        row.name = name
        cfg = dict(row.config or {})
        cfg["logo_url"] = logo
        row.config = cfg
        from datetime import datetime, timezone
        from sqlalchemy.orm.attributes import flag_modified

        row.updated_at = datetime.now(timezone.utc)
        flag_modified(row, "config")
        phone = row.phone_number_id

    invalidate_tenant(phone)
    await dash_auth.audit_support_action(
        user, "owner_profile", tenant_id=tid, detail={"name": name, "has_logo": bool(logo)}
    )
    return {"id": tid, "name": name, "logo_url": logo, "phone_number_id": phone}


class InviteStaffBody(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)


@router.get("/api/dashboard/my-team")
async def list_my_team(user: dash_auth.AuthUser = Depends(dash_auth.require_auth)):
    _require_db()
    tid = _owner_tenant_id(user)
    from app.db.repo import list_users_for_tenant

    async with _get_db() as db:
        rows = await list_users_for_tenant(db, tid)
    return {
        "items": [
            {"id": u.id, "username": u.username, "role": u.role, "tenant_id": u.tenant_id}
            for u in rows
        ]
    }


@router.post("/api/dashboard/my-team")
async def invite_staff(
    body: InviteStaffBody,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """Owner invites another login for the same business (shared owner access)."""
    _require_db()
    dash_auth.assert_writable(user)
    tid = _owner_tenant_id(user)
    from app.db.repo import create_user, get_user_by_username

    async with _get_db() as db:
        if await get_user_by_username(db, body.username.strip()):
            raise HTTPException(status_code=409, detail="Username taken")
        await create_user(
            db,
            username=body.username.strip(),
            password_hash=hash_password(body.password),
            role="owner",
            tenant_id=tid,
        )
    await dash_auth.audit_support_action(
        user, "owner_invite_staff", tenant_id=tid, detail={"username": body.username}
    )
    return {"ok": True, "username": body.username.strip(), "tenant_id": tid, "role": "owner"}


@router.get("/api/dashboard/export/leads.csv")
async def export_leads_csv(user: dash_auth.AuthUser = Depends(dash_auth.require_auth)):
    _require_db()
    phone = await _scoped_phone(user)
    async with _get_db() as db:
        data = await queries.list_leads(db, tenant_phone_id=phone, limit=5000, offset=0)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "id",
            "name",
            "phone",
            "status",
            "business_type",
            "locations",
            "demo_slot",
            "notes",
            "tags",
            "last_activity",
        ]
    )
    for lead in data["items"]:
        tags = lead.get("tags") or []
        w.writerow(
            [
                lead.get("id"),
                lead.get("business_name") or lead.get("contact", {}).get("profile_name"),
                lead.get("contact", {}).get("wa_id"),
                lead.get("status"),
                lead.get("business_type"),
                lead.get("locations"),
                lead.get("demo_slot"),
                lead.get("notes") or "",
                ";".join(tags) if isinstance(tags, list) else tags,
                lead.get("last_activity"),
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=customers.csv"},
    )


@router.get("/api/dashboard/export/orders.csv")
async def export_orders_csv(user: dash_auth.AuthUser = Depends(dash_auth.require_auth)):
    _require_db()
    phone = await _scoped_phone(user)
    async with _get_db() as db:
        data = await queries.list_orders(db, tenant_phone_id=phone, limit=5000, offset=0)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "phone", "total", "status", "address", "created_at"])
    for o in data["items"]:
        w.writerow(
            [
                o.get("id"),
                o.get("contact", {}).get("wa_id"),
                o.get("total"),
                o.get("status"),
                o.get("delivery_address"),
                o.get("created_at"),
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orders.csv"},
    )


class LeadNotesBody(BaseModel):
    notes: str = ""
    tags: list[str] = Field(default_factory=list)


@router.patch("/api/dashboard/leads/{lead_id}/notes")
async def update_lead_notes(
    lead_id: int,
    body: LeadNotesBody,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    dash_auth.assert_writable(user)
    from app.db.models import DBLead
    from sqlalchemy import select

    async with _get_db() as db:
        lead = (
            await db.execute(select(DBLead).where(DBLead.id == lead_id))
        ).scalar_one_or_none()
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")
        await dash_auth.assert_tenant_access(user, lead.tenant_id)
        lead.notes = (body.notes or "")[:4000]
        tags = [str(t).strip()[:32] for t in (body.tags or []) if str(t).strip()][:20]
        lead.tags = tags
        await db.flush()
    return {"ok": True, "id": lead_id, "notes": body.notes, "tags": tags}


class BroadcastBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=1024)
    lead_ids: Optional[list[int]] = None  # None = all with open window preference


@router.post("/api/dashboard/broadcast")
async def broadcast_message(
    body: BroadcastBody,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """
    Send a plain text message to selected (or recent) customers.
    Only contacts with an open 24h WhatsApp window are attempted.
    """
    _require_db()
    dash_auth.assert_writable(user)
    tid = _owner_tenant_id(user)
    phone = await _scoped_phone(user)

    from app.db.repo import get_tenant_row
    from app.main import send_whatsapp_message
    from app.tenants import Tenant

    async with _get_db() as db:
        row = await get_tenant_row(db, tid)
        if row is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        tenant = Tenant.from_db_row(row)
        data = await queries.list_leads(db, tenant_phone_id=phone, limit=200, offset=0)
        items = data["items"]
        if body.lead_ids:
            want = set(body.lead_ids)
            items = [row for row in items if row["id"] in want]

    sent = 0
    failed = 0
    skipped = 0
    for lead in items[:50]:
        wa = (lead.get("contact") or {}).get("wa_id") or ""
        if not wa:
            skipped += 1
            continue
        ok = await send_whatsapp_message(wa, body.text.strip(), tenant=tenant)
        if ok:
            sent += 1
        else:
            failed += 1
    await dash_auth.audit_support_action(
        user,
        "owner_broadcast",
        tenant_id=tid,
        detail={"sent": sent, "failed": failed, "skipped": skipped},
    )
    return {"ok": True, "sent": sent, "failed": failed, "skipped": skipped}


async def _scoped_phone(user: dash_auth.AuthUser) -> str:
    from app.dashboard.routes import _scoped_tenant_phone

    return await _scoped_tenant_phone(user, "all")
