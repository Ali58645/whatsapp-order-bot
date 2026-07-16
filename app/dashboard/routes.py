"""Dashboard HTTP routes."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dashboard import auth as dash_auth
from app.dashboard import queries


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


router = APIRouter(tags=["dashboard"])


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginBody(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int = dash_auth.TOKEN_TTL_H


@router.post("/api/auth/login", response_model=TokenOut)
async def login(body: LoginBody):
    dash_auth._require_enabled()
    if not dash_auth.verify_login(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = dash_auth.create_access_token(body.username)
    return TokenOut(access_token=token)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}")


# ── Read endpoints ────────────────────────────────────────────────────────────

@router.get("/api/dashboard/tenants")
async def get_tenants(_user: str = Depends(dash_auth.require_auth)):
    _require_db()
    async with _get_db() as db:
        return await queries.list_tenants(db)


@router.get("/api/dashboard/overview")
async def get_overview(
    tenant_id: str = Query("all"),
    _user: str = Depends(dash_auth.require_auth),
):
    _require_db()
    async with _get_db() as db:
        return await queries.overview(db, tenant_phone_id=tenant_id)


@router.get("/api/dashboard/leads")
async def get_leads(
    tenant_id: str = Query("all"),
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: str = Depends(dash_auth.require_auth),
):
    _require_db()
    async with _get_db() as db:
        return await queries.list_leads(
            db,
            tenant_phone_id=tenant_id,
            status=status,
            date_from=_parse_dt(date_from),
            date_to=_parse_dt(date_to),
            search=search,
            limit=limit,
            offset=offset,
        )


@router.get("/api/dashboard/leads/{lead_id}")
async def get_lead_detail(
    lead_id: int,
    _user: str = Depends(dash_auth.require_auth),
):
    _require_db()
    async with _get_db() as db:
        data = await queries.get_lead(db, lead_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return data


@router.get("/api/dashboard/orders")
async def get_orders(
    tenant_id: str = Query("all"),
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: str = Depends(dash_auth.require_auth),
):
    _require_db()
    async with _get_db() as db:
        return await queries.list_orders(
            db,
            tenant_phone_id=tenant_id,
            status=status,
            date_from=_parse_dt(date_from),
            date_to=_parse_dt(date_to),
            limit=limit,
            offset=offset,
        )


@router.get("/api/dashboard/conversations/{contact_id}")
async def get_conversation(
    contact_id: int,
    _user: str = Depends(dash_auth.require_auth),
):
    _require_db()
    async with _get_db() as db:
        data = await queries.conversation_for_contact(db, contact_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return data


@router.get("/api/dashboard/events")
async def get_events(
    tenant_id: str = Query("all"),
    type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: str = Depends(dash_auth.require_auth),
):
    _require_db()
    async with _get_db() as db:
        return await queries.list_events(
            db,
            tenant_phone_id=tenant_id,
            event_type=type,
            limit=limit,
            offset=offset,
        )


# ── Mutes (human takeover) ────────────────────────────────────────────────────

class MuteBody(BaseModel):
    tenant_id: str = Field(..., description="Tenant phone_number_id")
    wa_id: str
    mute: bool = True
    duration_s: int = Field(24 * 3600, ge=60, le=30 * 24 * 3600)


@router.post("/api/dashboard/mutes")
async def post_mute(
    body: MuteBody,
    _user: str = Depends(dash_auth.require_auth),
):
    _require_db()
    from app.tenants import get_tenant
    from app.db.store import MuteStore, EventStore

    tenant = get_tenant(body.tenant_id)
    if tenant is None:
        # Fall back: look up DB tenant and build a minimal Tenant for MuteStore
        from app.tenants import Tenant
        async with _get_db() as db:
            from app.db.models import DBTenant
            from sqlalchemy import select
            row = (
                await db.execute(
                    select(DBTenant).where(DBTenant.phone_number_id == body.tenant_id)
                )
            ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        tenant = Tenant(
            phone_number_id=row.phone_number_id,
            name=row.name,
            flow_mode="lead",  # mute-only; avoid order-mode menu requirement
        )

    if body.mute:
        await MuteStore.mute(body.wa_id, tenant, body.duration_s)
        await EventStore.append(
            tenant, "mute",
            {"wa_id": body.wa_id, "duration_s": body.duration_s, "source": "dashboard"},
            wa_id=body.wa_id,
        )
        return {"ok": True, "muted": True, "wa_id": body.wa_id}
    else:
        await MuteStore.clear(body.wa_id, tenant)
        await EventStore.append(
            tenant, "mute",
            {"wa_id": body.wa_id, "muted": False, "source": "dashboard"},
            wa_id=body.wa_id,
        )
        return {"ok": True, "muted": False, "wa_id": body.wa_id}
