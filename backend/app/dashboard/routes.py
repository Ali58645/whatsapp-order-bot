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
    readonly: bool = False
    impersonated_by: Optional[str] = None


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
        readonly=user.readonly,
        impersonated_by=user.impersonated_by,
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
async def get_tenants(
    status: Optional[str] = Query(None, description="Filter: live|paused|archived|draft|all"),
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    async with _get_db() as db:
        rows = await queries.list_tenants(db)
        counts = await queries.tenant_status_counts(db)
    if user.role == "owner" and user.tenant_id is not None:
        rows = [t for t in rows if t["id"] == user.tenant_id]
        counts = {"all": len(rows), "live": 0, "paused": 0, "archived": 0, "draft": 0}
        for t in rows:
            st = (t.get("status") or "live").lower()
            if st in counts:
                counts[st] += 1
    filt = (status or "all").lower()
    if filt and filt != "all":
        if filt not in ("live", "paused", "archived", "draft"):
            raise HTTPException(status_code=400, detail="Invalid status filter")
        rows = [t for t in rows if (t.get("status") or "live").lower() == filt]
    return {"items": rows, "counts": counts}


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
    dash_auth.assert_writable(user)
    await dash_auth.audit_support_action(user, "config_save", tenant_id=tenant_db_id)
    dash_auth.assert_owner_config_patch(user, body if isinstance(body, dict) else {})
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
    dash_auth.assert_writable(user)
    await dash_auth.audit_support_action(user, "menu_publish", tenant_id=tenant_db_id)
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


@router.post("/api/dashboard/tenants/{tenant_db_id}/flow/preview")
async def preview_lead_flow(
    tenant_db_id: int,
    body: dict | None = None,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """
    End-to-end WhatsApp preview of the lead conversation flow.
    Optional body.flow overrides stored config (unsaved editor state).
    """
    _require_db()
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    from app.db.repo import get_tenant_row
    from app.flow import FlowError, default_bahi_pos_flow, preview_flow_messages, validate_flow
    from app.tenants import Tenant

    async with _get_db() as db:
        row = await get_tenant_row(db, tenant_db_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if row.flow_mode != "lead":
        raise HTTPException(status_code=400, detail="flow preview only for lead tenants")

    tenant = Tenant.from_db_row(row)
    cfg = dict(row.config or {})
    flow = (body or {}).get("flow")
    if flow is None:
        flow = cfg.get("flow") or default_bahi_pos_flow()
    try:
        cleaned = validate_flow(flow)
        steps = preview_flow_messages(
            cleaned,
            lang=tenant.lang_code(),
            tenant=tenant,
            demo_slots=tenant.demo_slots,
        )
    except FlowError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"flow": cleaned, "steps": steps}


@router.post("/api/dashboard/tenants/{tenant_db_id}/knowledge/preview")
async def preview_knowledge(
    tenant_db_id: int,
    body: dict | None = None,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """
    Test a customer question against the knowledge base (draft or published).
    Optional body.knowledge_base overrides stored config (unsaved editor state).
    """
    _require_db()
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    from app.db.repo import get_tenant_row
    from app.knowledge import (
        check_preview_rate_limit,
        migrate_faq_into_knowledge,
        preview_knowledge_answer,
        validate_knowledge_base,
    )

    question = str((body or {}).get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    if len(question) > 500:
        raise HTTPException(status_code=400, detail="question too long")
    if not check_preview_rate_limit(tenant_db_id):
        raise HTTPException(status_code=429, detail="Too many preview requests — try again shortly")

    async with _get_db() as db:
        row = await get_tenant_row(db, tenant_db_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    cfg = migrate_faq_into_knowledge(dict(row.config or {}))
    kb_raw = (body or {}).get("knowledge_base")
    if kb_raw is None:
        kb_raw = cfg.get("knowledge_base")
    try:
        validate_knowledge_base(kb_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Import AI client from main (same provider as WhatsApp path)
    from app.main import ANTHROPIC_MODEL, anthropic_client
    import os

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="AI is not configured — set ANTHROPIC_API_KEY for knowledge answers",
        )

    lang = str((body or {}).get("lang") or "en")
    try:
        result = await preview_knowledge_answer(
            question,
            kb_raw,
            client=anthropic_client,
            model=ANTHROPIC_MODEL,
            lang_hint=lang,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Preview failed: {exc}") from exc
    return result


@router.post("/api/dashboard/tenants/{tenant_db_id}/menu/test-send")
async def test_send_menu(
    tenant_db_id: int,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """Send current draft menu entry messages to owner_whatsapp (does not publish)."""
    _require_db()
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    dash_auth.assert_writable(user)
    await dash_auth.audit_support_action(user, "menu_test_send", tenant_id=tenant_db_id)
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
    dash_auth.assert_writable(user)
    await dash_auth.audit_support_action(user, "messages_publish", tenant_id=tenant_db_id)
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
    template_id: Optional[str] = None
    waba_id: str = ""
    sheet_url: str = ""
    connection_verified: bool = False
    subscribed_apps: Optional[bool] = None
    sheet_tested: bool = False
    verified_name: str = ""


class TenantStatusBody(BaseModel):
    status: str = Field(..., pattern="^(draft|live|paused|archived)$")


class VerifyWhatsAppBody(BaseModel):
    phone_number_id: str = Field(..., min_length=1, max_length=64)
    waba_id: str = ""


class SheetTestBody(BaseModel):
    sheet_url: str = Field(..., min_length=1, max_length=512)


class OnboardingDraftBody(BaseModel):
    """Create or update a draft tenant from the onboarding wizard."""
    tenant_id: Optional[int] = None  # update existing draft when set
    name: str = Field(..., min_length=1, max_length=256)
    flow_mode: str = Field(..., pattern="^(lead|order)$")
    phone_number_id: str = Field(..., min_length=1, max_length=64)
    business_wa_id: str = ""
    owner_whatsapp: str = ""
    greeting_language: str = "roman_urdu"
    template_id: str = Field(..., min_length=1, max_length=64)
    waba_id: str = ""
    sheet_url: str = ""
    connection_verified: bool = False
    subscribed_apps: Optional[bool] = None
    sheet_tested: bool = False
    verified_name: str = ""


class OnboardingActivateBody(BaseModel):
    send_test: bool = True


@router.post("/api/dashboard/tenants")
async def create_tenant_route(
    body: CreateTenantBody,
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    """Admin: create a new business tenant (draft by default)."""
    _require_db()
    from app.db.repo import create_tenant
    from app.onboarding import parse_sheet_id, patch_onboarding
    from app.prompt_data import sanitize_text
    from app.tenant_resolver import invalidate_tenant

    status = "live" if body.publish else "draft"
    lang = body.greeting_language.strip().lower()
    if lang not in ("roman_urdu", "en", "ur", "english"):
        raise HTTPException(status_code=400, detail="Invalid greeting_language")
    lang_norm = "en" if lang in ("en", "english") else "roman_urdu"

    extra: dict = {}
    if body.waba_id or body.connection_verified or body.template_id:
        extra = patch_onboarding(
            extra,
            waba_id=sanitize_text(body.waba_id, max_len=64) if body.waba_id else None,
            connection_verified=body.connection_verified or None,
            subscribed_apps=body.subscribed_apps,
            sheet_tested=body.sheet_tested or None,
            verified_name=sanitize_text(body.verified_name, max_len=256) if body.verified_name else None,
            template_id=body.template_id,
        )
    sheet_id = parse_sheet_id(body.sheet_url) if body.sheet_url else ""
    if sheet_id:
        extra["sheet"] = {"gsheet_id": sheet_id, "tab": ""}

    try:
        async with _get_db() as db:
            row = await create_tenant(
                db,
                name=sanitize_text(body.name, max_len=256),
                flow_mode=body.flow_mode,
                phone_number_id=sanitize_text(body.phone_number_id, max_len=64),
                business_wa_id=sanitize_text(body.business_wa_id or "", max_len=32),
                owner_whatsapp=sanitize_text(body.owner_whatsapp or "", max_len=32),
                greeting_language=lang_norm,
                status=status,
                config=extra or None,
                template_id=body.template_id,
            )
            phone = row.phone_number_id
            tid = row.id
            st = row.status
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    invalidate_tenant(phone)
    return {
        "id": tid,
        "phone_number_id": phone,
        "name": body.name,
        "flow_mode": body.flow_mode,
        "status": st,
        "template_id": body.template_id,
    }


@router.post("/api/dashboard/tenants/{tenant_db_id}/status")
async def set_tenant_status_route(
    tenant_db_id: int,
    body: TenantStatusBody,
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    """Admin: pause / resume / archive / restore (→paused) / publish (live)."""
    _require_db()
    from app.db.repo import set_tenant_status
    from app.tenant_resolver import invalidate_tenant

    async with _get_db() as db:
        try:
            row = await set_tenant_status(db, tenant_db_id, body.status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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


class DeleteTenantBody(BaseModel):
    confirm_name: str = Field(..., min_length=1, max_length=256)


@router.delete("/api/dashboard/tenants/{tenant_db_id}")
async def delete_tenant_route(
    tenant_db_id: int,
    body: DeleteTenantBody,
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    """
    Permanently delete an archived tenant (cascade).
    Requires confirm_name matching the business name exactly.
    """
    _require_db()
    from app.db.repo import delete_tenant_permanently
    from app.tenant_resolver import invalidate_tenant

    async with _get_db() as db:
        try:
            result = await delete_tenant_permanently(
                db, tenant_db_id, confirm_name=body.confirm_name
            )
        except LookupError:
            raise HTTPException(status_code=404, detail="Tenant not found") from None
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    invalidate_tenant(result["phone_number_id"])
    return result


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
        try:
            row = await set_tenant_status(db, tenant_db_id, "live")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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
    Confirm phone_number_id via Graph API, show display name, and
    auto-check / subscribe WABA subscribed_apps when waba_id is provided.
    """
    from app.onboarding import verify_and_subscribe

    try:
        return await verify_and_subscribe(
            phone_number_id=body.phone_number_id.strip(),
            waba_id=(body.waba_id or "").strip(),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Graph API error: {exc}") from exc


@router.get("/api/dashboard/onboarding/templates")
async def list_onboarding_templates(
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    from app.onboarding import list_templates
    return {"items": list_templates()}


@router.get("/api/dashboard/templates")
async def list_starter_templates(
    flow_mode: Optional[str] = Query(None),
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """List vertical starter templates (admin + owners for Settings picker)."""
    from app.templates import list_templates
    if flow_mode and flow_mode not in ("lead", "order"):
        raise HTTPException(status_code=400, detail="flow_mode must be lead or order")
    return {"items": list_templates(flow_mode=flow_mode)}


class ApplyTemplateBody(BaseModel):
    template_id: str = Field(..., min_length=1, max_length=64)
    confirm: bool = False
    greeting_language: Optional[str] = None
    """When true, also copy drafts → published (owner My Bot expects this)."""
    go_live: bool = False


@router.post("/api/dashboard/tenants/{tenant_db_id}/apply-template")
async def apply_starter_template(
    tenant_db_id: int,
    body: ApplyTemplateBody,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """
    Apply a starter template — replaces greeting, questions/buttons, FAQ, and
    related draft copy. With go_live=true (owners), also publishes messages/menu.
    """
    _require_db()
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm=true required — applying a template overwrites bot content",
        )
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    dash_auth.assert_writable(user)
    await dash_auth.audit_support_action(
        user, "apply_template", tenant_id=tenant_db_id, detail={"template_id": body.template_id}
    )
    from app.dashboard.config_api import tenant_config_response
    from app.dashboard.config_validate import validate_config_patch
    from app.db.repo import get_tenant_row, save_tenant_config
    from app.templates import build_draft_patch, get_template
    from app.tenant_resolver import invalidate_tenant
    import copy

    tmpl = get_template(body.template_id)
    if tmpl is None:
        raise HTTPException(status_code=404, detail="Template not found")

    # Owners (incl. support view-as) go live by default; admins need go_live=true
    go_live = bool(body.go_live) or user.role == "owner"
    async with _get_db() as db:
        row = await get_tenant_row(db, tenant_db_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        cfg = dict(row.config or {})
        lang = (body.greeting_language or cfg.get("greeting_language") or "roman_urdu").strip()
        tmpl_flow = tmpl.get("flow_mode") or row.flow_mode
        try:
            patch = build_draft_patch(
                body.template_id,
                flow_mode=tmpl_flow,
                greeting_language=lang,
                business_name=row.name or "",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        cleaned = validate_config_patch(tmpl_flow, patch)
        new_cfg = dict(cfg)
        for key, val in cleaned.items():
            if key in ("messages", "menu_v2") and not go_live:
                continue
            new_cfg[key] = val
        if "messages_draft" in patch:
            new_cfg["messages_draft"] = patch["messages_draft"]
            if go_live:
                new_cfg["messages"] = copy.deepcopy(patch["messages_draft"])
        if "menu_v2_draft" in patch:
            new_cfg["menu_v2_draft"] = patch["menu_v2_draft"]
            if go_live:
                new_cfg["menu_v2"] = copy.deepcopy(patch["menu_v2_draft"])
        if "onboarding" in patch:
            ob = dict(new_cfg.get("onboarding") or {})
            ob.update(patch["onboarding"])
            new_cfg["onboarding"] = ob
        if "flow" in patch:
            new_cfg["flow"] = patch["flow"]
        if "faq" in cleaned:
            new_cfg["faq"] = cleaned["faq"]
            from app.knowledge import empty_knowledge_base, migrate_faq_into_knowledge

            new_cfg = migrate_faq_into_knowledge(new_cfg)
            kb = dict(new_cfg.get("knowledge_base") or empty_knowledge_base())
            kb["faq"] = list(cleaned["faq"])
            # Template FAQ goes live as published knowledge so bot answers work immediately
            if go_live:
                kb["status"] = "published"
                kb["enabled"] = True
            new_cfg["knowledge_base"] = kb

        if tmpl_flow in ("lead", "order") and row.flow_mode != tmpl_flow:
            row.flow_mode = tmpl_flow

        await save_tenant_config(
            db,
            tenant_db_id,
            name=None,
            config=new_cfg,
            changed_by=user.username,
        )
        phone = row.phone_number_id
        # Refresh row for response
        row = await get_tenant_row(db, tenant_db_id)
        out = tenant_config_response(row) if row else None

    invalidate_tenant(phone)
    from app.knowledge import invalidate_knowledge_cache

    invalidate_knowledge_cache(phone)
    return {
        "ok": True,
        "tenant_id": tenant_db_id,
        "template_id": tmpl.get("id"),
        "flow_mode": out["flow_mode"] if out else tmpl_flow,
        "go_live": go_live,
        "message": (
            "Template applied and live — edit greeting, questions, and knowledge base anytime"
            if go_live
            else "Draft updated — publish from Settings to go live"
        ),
        "config": out,
    }


@router.post("/api/dashboard/sheet/test")
async def test_sheet_connection(
    body: SheetTestBody,
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    from app.onboarding import test_sheet_access

    try:
        result = await test_sheet_access(body.sheet_url)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Sheet test failed: {exc}") from exc
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("detail") or "Sheet write failed")
    return result


@router.post("/api/dashboard/onboarding/draft")
async def save_onboarding_draft(
    body: OnboardingDraftBody,
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    """Save wizard progress as a draft tenant (create or update)."""
    _require_db()
    from app.db.repo import (
        create_tenant,
        get_tenant_row,
        get_tenant_row_by_phone,
        save_tenant_config,
    )
    from app.onboarding import (
        apply_template_to_config,
        build_checklist,
        parse_sheet_id,
        patch_onboarding,
    )
    from app.prompt_data import sanitize_text
    from app.tenant_resolver import invalidate_tenant

    lang = body.greeting_language.strip().lower()
    if lang not in ("roman_urdu", "en", "ur", "english"):
        raise HTTPException(status_code=400, detail="Invalid greeting_language")
    lang_norm = "en" if lang in ("en", "english") else "roman_urdu"
    phone = sanitize_text(body.phone_number_id, max_len=64)
    name = sanitize_text(body.name, max_len=256)

    sheet_id = parse_sheet_id(body.sheet_url) if body.sheet_url else ""
    base_cfg: dict = {
        "business_wa_id": sanitize_text(body.business_wa_id or "", max_len=32),
        "owner_whatsapp": sanitize_text(body.owner_whatsapp or "", max_len=32),
        "greeting_language": lang_norm,
    }
    if sheet_id:
        base_cfg["sheet"] = {"gsheet_id": sheet_id, "tab": ""}

    try:
        base_cfg = apply_template_to_config(
            base_cfg,
            template_id=body.template_id,
            flow_mode=body.flow_mode,
            greeting_language=lang_norm,
            business_name=name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    base_cfg = patch_onboarding(
        base_cfg,
        waba_id=sanitize_text(body.waba_id, max_len=64) if body.waba_id else "",
        connection_verified=body.connection_verified,
        subscribed_apps=body.subscribed_apps,
        sheet_tested=body.sheet_tested,
        verified_name=sanitize_text(body.verified_name, max_len=256) if body.verified_name else "",
        template_id=body.template_id,
        content_set=True,
    )

    async with _get_db() as db:
        row = None
        if body.tenant_id:
            row = await get_tenant_row(db, body.tenant_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Tenant not found")
            if (row.status or "") not in ("draft", "paused"):
                raise HTTPException(
                    status_code=400,
                    detail="Only draft/paused tenants can be updated via onboarding draft",
                )
        else:
            existing = await get_tenant_row_by_phone(db, phone)
            if existing is not None and (not body.tenant_id or existing.id != body.tenant_id):
                # Allow continuing the same draft phone
                if (existing.status or "") == "draft":
                    row = existing
                else:
                    raise HTTPException(
                        status_code=409,
                        detail=f"phone_number_id already exists: {phone}",
                    )

        if row is None:
            try:
                row = await create_tenant(
                    db,
                    name=name,
                    flow_mode=body.flow_mode,
                    phone_number_id=phone,
                    business_wa_id=base_cfg.get("business_wa_id", ""),
                    owner_whatsapp=base_cfg.get("owner_whatsapp", ""),
                    greeting_language=lang_norm,
                    status="draft",
                    config=base_cfg,
                    template_id=None,  # already applied into base_cfg
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        else:
            row.name = name
            row.flow_mode = body.flow_mode
            # phone change only if free
            if row.phone_number_id != phone:
                clash = await get_tenant_row_by_phone(db, phone)
                if clash is not None and clash.id != row.id:
                    raise HTTPException(status_code=409, detail="phone_number_id already exists")
                row.phone_number_id = phone
            await save_tenant_config(
                db,
                row.id,
                name=name,
                config=base_cfg,
                changed_by=_admin.username,
            )
            # Re-fetch for checklist
            row = await get_tenant_row(db, row.id)

        checklist = build_checklist(row)
        tid = row.id
        st = row.status
        out_phone = row.phone_number_id

    invalidate_tenant(out_phone)
    return {
        "id": tid,
        "phone_number_id": out_phone,
        "name": name,
        "flow_mode": body.flow_mode,
        "status": st,
        "template_id": body.template_id,
        "checklist": checklist,
    }


@router.post("/api/dashboard/onboarding/{tenant_db_id}/activate")
async def activate_onboarding(
    tenant_db_id: int,
    body: OnboardingActivateBody = OnboardingActivateBody(),
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    """Promote draft → live, invalidate resolver cache, optionally SMS owner."""
    _require_db()
    from app.db.repo import get_tenant_row, set_tenant_status
    from app.onboarding import build_checklist, patch_onboarding
    from app.tenant_resolver import invalidate_tenant
    from app.tenants import Tenant

    async with _get_db() as db:
        row = await get_tenant_row(db, tenant_db_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        cfg = dict(row.config or {})
        owner = (cfg.get("owner_whatsapp") or "").strip()
        if not owner:
            raise HTTPException(
                status_code=400,
                detail="owner_whatsapp required before activate",
            )
        if not (cfg.get("onboarding") or {}).get("connection_verified"):
            raise HTTPException(
                status_code=400,
                detail="Verify WhatsApp connection before activate",
            )

        row = await set_tenant_status(db, tenant_db_id, "live")
        phone = row.phone_number_id
        tenant = Tenant.from_db_row(row)

    invalidate_tenant(phone)

    test_sent = False
    test_error = None
    if body.send_test:
        from app.main import send_whatsapp_message

        text = (
            f"BahiDesk: {tenant.name} is now LIVE on WhatsApp. "
            f"Reply to this number to confirm the bot is working."
        )
        try:
            ok = await send_whatsapp_message(owner, text, tenant=tenant)
            test_sent = bool(ok)
            if not ok:
                test_error = "WhatsApp send failed"
        except Exception as exc:
            test_error = str(exc)

        async with _get_db() as db:
            row = await get_tenant_row(db, tenant_db_id)
            cfg = patch_onboarding(
                dict(row.config or {}),
                test_message_sent=test_sent,
                test_message_error=test_error or "",
            )
            row.config = cfg
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(row, "config")
            checklist = build_checklist(row)
    else:
        async with _get_db() as db:
            row = await get_tenant_row(db, tenant_db_id)
            checklist = build_checklist(row)

    invalidate_tenant(phone)
    return {
        "id": tenant_db_id,
        "phone_number_id": phone,
        "status": "live",
        "test_message_sent": test_sent,
        "test_error": test_error,
        "checklist": checklist,
    }


@router.get("/api/dashboard/tenants/{tenant_db_id}/checklist")
async def get_tenant_checklist(
    tenant_db_id: int,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    from app.db.repo import get_tenant_row
    from app.onboarding import build_checklist

    await dash_auth.assert_tenant_access(user, tenant_db_id)
    async with _get_db() as db:
        row = await get_tenant_row(db, tenant_db_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return build_checklist(row)


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
    return {"ok": True, "username": body.username, "tenant_id": body.tenant_id, "role": "owner"}


@router.get("/api/dashboard/users")
async def list_dashboard_users(
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    _require_db()
    from app.db.repo import list_users, get_tenant_row

    async with _get_db() as db:
        rows = await list_users(db)
        items = []
        for u in rows:
            tenant_name = None
            if u.tenant_id:
                t = await get_tenant_row(db, u.tenant_id)
                tenant_name = t.name if t else None
            items.append({
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "tenant_id": u.tenant_id,
                "tenant_name": tenant_name,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            })
    return {"items": items}


@router.get("/api/dashboard/me")
async def get_me(user: dash_auth.AuthUser = Depends(dash_auth.require_auth)):
    """Current user + tenant summary (owner shell bootstrap)."""
    _require_db()
    from app.db.repo import get_tenant_row
    from app.onboarding import build_checklist

    tenant = None
    if user.tenant_id is not None:
        async with _get_db() as db:
            row = await get_tenant_row(db, user.tenant_id)
            if row is not None:
                cfg = row.config or {}
                tenant = {
                    "id": row.id,
                    "name": row.name,
                    "phone_number_id": row.phone_number_id,
                    "flow_mode": row.flow_mode,
                    "status": getattr(row, "status", None) or "live",
                    "logo_url": (cfg.get("logo_url") or "").strip(),
                    "waba_id": (cfg.get("onboarding") or {}).get("waba_id") or "",
                    "checklist": build_checklist(row),
                }
    return {
        "username": user.username,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "readonly": user.readonly,
        "impersonated_by": user.impersonated_by,
        "tenant": tenant,
    }


@router.get("/api/dashboard/billing")
async def get_billing(user: dash_auth.AuthUser = Depends(dash_auth.require_auth)):
    """
    Read-only billing placeholder for owners.
    Structured for a future metering backend.
    """
    _require_db()
    from datetime import datetime, timezone
    from app.db.repo import get_tenant_row

    if user.role == "owner" and user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Owner missing tenant")

    tenant_id = user.tenant_id
    tenant_name = None
    if tenant_id is not None:
        async with _get_db() as db:
            row = await get_tenant_row(db, tenant_id)
            if row is None and user.role == "owner":
                raise HTTPException(status_code=404, detail="Tenant not found")
            if row:
                tenant_name = row.name

    now = datetime.now(timezone.utc)
    return {
        "plan_name": "Starter",
        "status": "active",
        "period": now.strftime("%Y-%m"),
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "usage": {
            "messages_sent": 0,
            "templates_sent": 0,
            "note": "Usage metering coming soon — placeholder counts",
        },
        "placeholder": True,
    }


@router.post("/api/dashboard/admin/view-as/{tenant_db_id}")
async def view_as_owner(
    tenant_db_id: int,
    admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    """
    Issue a support-mode owner token (writable, audited) for the given tenant.
    Client stores previous admin token separately to exit view-as.
    """
    _require_db()
    from app.db.repo import append_access_log, get_tenant_row

    async with _get_db() as db:
        row = await get_tenant_row(db, tenant_db_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        name = row.name
        await append_access_log(
            db,
            admin_username=admin.username,
            action="view_as_enter",
            tenant_id=tenant_db_id,
            tenant_name=name,
            detail={"support_mode": True},
        )

    view_user = dash_auth.AuthUser(
        username=f"viewas:{admin.username}",
        role="owner",
        tenant_id=tenant_db_id,
        impersonated_by=admin.username,
        readonly=False,
    )
    token = dash_auth.create_access_token(view_user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "owner",
        "tenant_id": tenant_db_id,
        "tenant_name": name,
        "readonly": False,
        "support_mode": True,
        "impersonated_by": admin.username,
        "expires_in_hours": dash_auth.TOKEN_TTL_H,
    }


@router.get("/api/dashboard/access-log")
async def get_access_log(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: dash_auth.AuthUser = Depends(dash_auth.require_admin),
):
    """Admin: list support / impersonation audit entries (newest first)."""
    _require_db()
    from app.db.repo import list_access_logs

    async with _get_db() as db:
        items = await list_access_logs(db, limit=limit, offset=offset)
    return {"items": items, "limit": limit, "offset": offset}


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
    channel: Optional[str] = None,
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
            channel=channel,
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
    channel: Optional[str] = None,
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
            channel=channel,
            date_from=_parse_dt(date_from),
            date_to=_parse_dt(date_to),
            limit=limit,
            offset=offset,
        )


@router.get("/api/dashboard/conversations/{contact_id}")
async def get_conversation(
    contact_id: int,
    session_id: Optional[int] = None,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    async with _get_db() as db:
        data = await queries.conversation_for_contact(
            db, contact_id, session_id_hint=session_id
        )
    if data is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    await _assert_resource_tenant(user, data["contact"]["tenant_id"])
    return data


class SendMessageBody(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)


@router.post("/api/dashboard/conversations/{contact_id}/send")
async def send_conversation_message(
    contact_id: int,
    body: SendMessageBody,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    _require_db()
    from app.prompt_data import sanitize_text

    dash_auth.assert_writable(user)
    text = sanitize_text(body.text.strip(), max_len=4096)
    if not text:
        raise HTTPException(status_code=400, detail="Message text is required")

    async with _get_db() as db:
        preview = await queries.conversation_for_contact(db, contact_id)
        if preview is None:
            raise HTTPException(status_code=404, detail="Contact not found")
        await _assert_resource_tenant(user, preview["contact"]["tenant_id"])
        await dash_auth.audit_support_action(
            user,
            "reply",
            tenant_id=preview["contact"]["tenant_id"],
            detail={"contact_id": contact_id},
        )

        try:
            data = await queries.send_agent_reply(
                db,
                contact_id=contact_id,
                text=text,
                agent_username=user.username,
            )
        except ValueError as exc:
            if str(exc) == "window_closed":
                raise HTTPException(
                    status_code=400,
                    detail="Window closed — customer must message first",
                ) from exc
            raise
        except LookupError as exc:
            if str(exc) == "contact_not_found":
                raise HTTPException(status_code=404, detail="Contact not found") from exc
            if str(exc) == "tenant_not_found":
                raise HTTPException(status_code=404, detail="Tenant not found") from exc
            raise
        except RuntimeError as exc:
            if str(exc) == "send_failed":
                raise HTTPException(
                    status_code=502, detail="WhatsApp send failed"
                ) from exc
            raise

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

    dash_auth.assert_writable(user)
    if user.role == "owner":
        scoped = await _scoped_tenant_phone(user, body.tenant_id)
        if scoped != body.tenant_id:
            raise HTTPException(status_code=403, detail="Not allowed for this tenant")

    await dash_auth.audit_support_action(
        user,
        "mute" if body.mute else "unmute",
        tenant_id=user.tenant_id,
        detail={"wa_id": body.wa_id, "phone_number_id": body.tenant_id},
    )

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


# ── Multi-channel connect (OAuth scaffold — pending Meta App Review) ─────────

_CHANNEL_META = {
    "whatsapp": {
        "label": "WhatsApp",
        "connect_type": "manual",
        "note": "Configured via Phone number ID in Wiring / onboarding.",
    },
    "instagram": {
        "label": "Instagram",
        "connect_type": "facebook_login",
        "note": "Pending Meta approval — Facebook Login will connect your IG professional account.",
    },
    "messenger": {
        "label": "Messenger",
        "connect_type": "facebook_login",
        "note": "Pending Meta approval — Facebook Login will connect your Facebook Page.",
    },
}


@router.get("/api/dashboard/tenants/{tenant_db_id}/channels")
async def list_tenant_channels(
    tenant_db_id: int,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """Per-tenant channel connection status."""
    _require_db()
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    from app.db.repo import get_tenant_row
    from app.tenants import Tenant

    async with _get_db() as db:
        row = await get_tenant_row(db, tenant_db_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    tenant = Tenant.from_db_row(row)
    items = []
    for ch, meta in _CHANNEL_META.items():
        cfg = tenant.channel_config(ch)
        items.append({
            "channel": ch,
            "label": meta["label"],
            "status": cfg.get("status") or "disconnected",
            "connected": tenant.is_channel_live(ch) if ch == "whatsapp" else cfg.get("status") == "live",
            "account_id": cfg.get("account_id") or "",
            "oauth_pending": cfg.get("oauth_pending", ch != "whatsapp"),
            "connect_type": meta["connect_type"],
            "note": meta["note"],
        })
    return {"tenant_id": tenant_db_id, "channels": items}


@router.post("/api/dashboard/tenants/{tenant_db_id}/channels/{channel}/connect")
async def connect_tenant_channel(
    tenant_db_id: int,
    channel: str,
    user: dash_auth.AuthUser = Depends(dash_auth.require_auth),
):
    """
    OAuth connect scaffold for IG/FB. Returns auth URL placeholder until App Review.
    WhatsApp remains manual (onboarding / wiring).
    """
    _require_db()
    await dash_auth.assert_tenant_access(user, tenant_db_id)
    dash_auth.assert_writable(user)
    if channel not in _CHANNEL_META:
        raise HTTPException(status_code=400, detail="Unknown channel")
    if channel == "whatsapp":
        raise HTTPException(
            status_code=400,
            detail="WhatsApp is connected via Phone number ID in Settings → Wiring",
        )
    return {
        "channel": channel,
        "status": "pending_meta_approval",
        "oauth_url": None,
        "message": (
            "Facebook Login connect flow is scaffolded. "
            "Complete Meta App Review to enable Instagram/Messenger OAuth."
        ),
    }
