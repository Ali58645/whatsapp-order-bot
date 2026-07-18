"""Dashboard HTTP routes."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.dashboard import auth as dash_auth
from app.dashboard import queries
from app.dashboard.config_api import apply_config_save, tenant_config_response
from app.dashboard.users import hash_password


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
    role: str = "admin"
    tenant_id: Optional[int] = None


@router.post("/api/auth/login", response_model=TokenOut)
async def login(body: LoginBody):
    dash_auth._require_enabled()
    user = await dash_auth.authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = dash_auth.create_access_token(user)
    return TokenOut(
        access_token=token,
        role=user.role,
        tenant_id=user.tenant_id,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}")


async def _scoped_tenant_phone(user: dash_auth.AuthUser, tenant_id: str) -> str:
    """Admin: pass through. Owner: force own tenant or 403."""
    if user.role == "admin":
        return tenant_id
    if user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Owner missing tenant")
    from app.db.repo import get_tenant_row
    async with _get_db() as db:
        row = await get_tenant_row(db, user.tenant_id)
    if row is None:
        raise HTTPException(status_code=403, detail="Tenant not found")
    phone = row.phone_number_id
    if tenant_id not in ("all", phone):
        raise HTTPException(status_code=403, detail="Not allowed for this tenant")
    return phone


async def _assert_resource_tenant(user: dash_auth.AuthUser, resource_tenant_id: int) -> None:
    if user.role == "admin":
        return
    if user.tenant_id != resource_tenant_id:
        raise HTTPException(status_code=403, detail="Not allowed for this tenant")

# ── Read endpoints ────────────────────────────────────────────────────────────

@router.get("/api/dashboard/tenants")
async def get_tenants(user: dash_auth.AuthUser = Depends(dash_auth.require_auth)):
    _require_db()
    async with _get_db() as db:
        rows = await queries.list_tenants(db)
    if user.role == "owner" and user.tenant_id is not None:
        rows = [t for t in rows if t["id"] == user.tenant_id]
    return rows


@router.get("/api/dashboard/tenants/{tenant_db_id}/config")
async def get_tenant_config(
    tenant_db_id: int,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    from app.db.repo import get_tenant_row
    async with _get_db() as db:
        row = await get_tenant_row(db, tenant_db_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant_config_response(row)


@router.post("/api/dashboard/tenants/{tenant_db_id}/config")
async def save_tenant_config(
    tenant_db_id: int,
    body: dict,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    async with _get_db() as db:
        result = await apply_config_save(db, tenant_db_id, body, changed_by=user.username)
    if result is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return result


@router.post("/api/dashboard/tenants/{tenant_db_id}/menu/publish")
async def publish_menu(
    tenant_db_id: int,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """Promote menu_v2_draft → published menu_v2 (history snapshot on save)."""
    _require_db()
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    from app.dashboard.config_api import publish_menu_v2
    from app.menu_v2 import MenuV2Error

    try:
        async with _get_db() as db:
            result = await publish_menu_v2(db, tenant_db_id, changed_by=user.username)
    except MenuV2Error as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return result


@router.post("/api/dashboard/tenants/{tenant_db_id}/menu/preview")
async def preview_menu(
    tenant_db_id: int,
    body: dict | None = None,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """
    Build WhatsApp payloads for the live preview.
    Optional body.menu_v2_draft overrides stored draft (unsaved editor state).
    """
    _require_db()
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    from app.db.repo import get_tenant_row
    from app.dashboard.config_api import build_menu_preview
    from app.menu_v2 import MenuV2Error, preview_flow_steps, validate_menu_v2

    async with _get_db() as db:
        row = await get_tenant_row(db, tenant_db_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    try:
        if body and body.get("menu_v2_draft") is not None:
            menu = validate_menu_v2(body["menu_v2_draft"])
            return {"menu": menu, "steps": preview_flow_steps(menu, to="preview")}
        return build_menu_preview(row, use_draft=True)
    except MenuV2Error as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/dashboard/tenants/{tenant_db_id}/menu/test-send")
async def test_send_menu(
    tenant_db_id: int,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """Send current draft menu entry messages to owner_whatsapp (does not publish)."""
    _require_db()
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    from app.db.repo import get_tenant_row
    from app.dashboard.config_api import send_menu_test
    from app.menu_v2 import MenuV2Error
    from app.main import send_whatsapp_message

    async with _get_db() as db:
        row = await get_tenant_row(db, tenant_db_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    try:
        return await send_menu_test(row, send_whatsapp_message)
    except MenuV2Error as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/dashboard/tenants/{tenant_db_id}/messages/publish")
async def publish_messages(
    tenant_db_id: int,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """Promote messages_draft → published messages."""
    _require_db()
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    from app.dashboard.config_api import publish_messages as _publish
    from app.messages import MessagesError

    try:
        async with _get_db() as db:
            result = await _publish(db, tenant_db_id, changed_by=user.username)
    except MessagesError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return result


class CreateTenantBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    flow_mode: str = Field(..., pattern="^(lead|order)$")
    phone_number_id: str = Field(..., min_length=1, max_length=64)
    business_wa_id: str = ""
    owner_whatsapp: str = ""
    greeting_language: str = "roman_urdu"
    publish: bool = False  # if True, create as live; else draft


class TenantStatusBody(BaseModel):
    status: str = Field(..., pattern="^(draft|live|paused|archived)$")


class VerifyWhatsAppBody(BaseModel):
    phone_number_id: str = Field(..., min_length=1, max_length=64)


@router.post("/api/dashboard/tenants")
async def create_tenant_route(
    body: CreateTenantBody,
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    """Admin: create a new business tenant (draft by default)."""
    _require_db()
    from app.db.repo import create_tenant
    from app.prompt_data import sanitize_text
    from app.tenant_resolver import invalidate_tenant

    status = "live" if body.publish else "draft"
    lang = body.greeting_language.strip().lower()
    if lang not in ("roman_urdu", "en", "ur", "english"):
        raise HTTPException(status_code=400, detail="Invalid greeting_language")
    try:
        async with _get_db() as db:
            row = await create_tenant(
                db,
                name=sanitize_text(body.name, max_len=256),
                flow_mode=body.flow_mode,
                phone_number_id=sanitize_text(body.phone_number_id, max_len=64),
                business_wa_id=sanitize_text(body.business_wa_id or "", max_len=32),
                owner_whatsapp=sanitize_text(body.owner_whatsapp or "", max_len=32),
                greeting_language="en" if lang in ("en", "english") else "roman_urdu",
                status=status,
            )
            phone = row.phone_number_id
            tid = row.id
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    invalidate_tenant(phone)
    return {
        "id": tid,
        "phone_number_id": phone,
        "name": body.name,
        "flow_mode": body.flow_mode,
        "status": status,
    }


@router.post("/api/dashboard/tenants/{tenant_db_id}/status")
async def set_tenant_status_route(
    tenant_db_id: int,
    body: TenantStatusBody,
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    """Admin: pause / resume / archive / publish (live) a tenant."""
    _require_db()
    from app.db.repo import set_tenant_status
    from app.tenant_resolver import invalidate_tenant

    async with _get_db() as db:
        row = await set_tenant_status(db, tenant_db_id, body.status)
        if row is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        phone = row.phone_number_id
        status = row.status
        name = row.name
        flow = row.flow_mode
    invalidate_tenant(phone)
    return {
        "id": tenant_db_id,
        "phone_number_id": phone,
        "name": name,
        "flow_mode": flow,
        "status": status,
    }


@router.post("/api/dashboard/tenants/{tenant_db_id}/publish")
async def publish_tenant(
    tenant_db_id: int,
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    """Admin shortcut: draft → live."""
    _require_db()
    from app.db.repo import set_tenant_status
    from app.tenant_resolver import invalidate_tenant

    async with _get_db() as db:
        row = await set_tenant_status(db, tenant_db_id, "live")
        if row is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        phone = row.phone_number_id
    invalidate_tenant(phone)
    return {"id": tenant_db_id, "status": "live", "phone_number_id": phone}


@router.post("/api/dashboard/whatsapp/verify")
async def verify_whatsapp_connection(
    body: VerifyWhatsAppBody,
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    """
    Call Meta Graph API to confirm phone_number_id resolves.
    Returns display name / verified_name when available.
    """
    _require_db()
    import httpx
    import os

    token = os.environ.get("WHATSAPP_TOKEN") or os.environ.get("META_WHATSAPP_TOKEN") or ""
    if not token:
        raise HTTPException(status_code=503, detail="WHATSAPP_TOKEN not configured")
    url = f"https://graph.facebook.com/v21.0/{body.phone_number_id}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                params={"fields": "display_phone_number,verified_name,quality_rating"},
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Graph API error: {exc}") from exc
    data = resp.json() if resp.content else {}
    if resp.status_code >= 400:
        err = (data.get("error") or {}).get("message") or resp.text
        raise HTTPException(status_code=400, detail=f"Verification failed: {err}")
    return {
        "ok": True,
        "phone_number_id": body.phone_number_id,
        "display_phone_number": data.get("display_phone_number"),
        "verified_name": data.get("verified_name") or data.get("name"),
        "quality_rating": data.get("quality_rating"),
        "raw": data,
    }


class CreateOwnerBody(BaseModel):
    username: str
    password: str
    tenant_id: int = Field(..., description="DB tenant id")


@router.post("/api/dashboard/users")
async def create_owner(
    body: CreateOwnerBody,
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    _require_db()
    from app.db.repo import create_user, get_user_by_username, get_tenant_row
    async with _get_db() as db:
        if await get_user_by_username(db, body.username):
            raise HTTPException(status_code=409, detail="Username taken")
        if await get_tenant_row(db, body.tenant_id) is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        await create_user(
            db,
            username=body.username,
            password_hash=hash_password(body.password),
            role="owner",
            tenant_id=body.tenant_id,
        )
    return {"ok": True, "username": body.username}


@router.get("/api/dashboard/overview")
async def get_overview(
    tenant_id: str = Query("all"),
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    tenant_id = await _scoped_tenant_phone(user, tenant_id)
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
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    tenant_id = await _scoped_tenant_phone(user, tenant_id)
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
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    async with _get_db() as db:
        data = await queries.get_lead(db, lead_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    await _assert_resource_tenant(user, data["tenant_id"])
    return data


@router.get("/api/dashboard/orders")
async def get_orders(
    tenant_id: str = Query("all"),
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    tenant_id = await _scoped_tenant_phone(user, tenant_id)
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
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    async with _get_db() as db:
        data = await queries.conversation_for_contact(db, contact_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    await _assert_resource_tenant(user, data["contact"]["tenant_id"])
    return data


@router.get("/api/dashboard/events")
async def get_events(
    tenant_id: str = Query("all"),
    type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    tenant_id = await _scoped_tenant_phone(user, tenant_id)
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
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    from app.tenants import get_tenant
    from app.db.store import MuteStore, EventStore

    if user.role == "owner":
        scoped = await _scoped_tenant_phone(user, body.tenant_id)
        if scoped != body.tenant_id:
            raise HTTPException(status_code=403, detail="Not allowed for this tenant")

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
