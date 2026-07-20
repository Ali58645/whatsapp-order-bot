"""
WhatsApp Bot — FastAPI + Meta Cloud API + Claude Haiku
Multi-tenant: routed by phone_number_id from the webhook payload.

TENANTS_JSON_B64 / TENANTS_FILE → multi-tenant registry
Neither set → single-tenant fallback from legacy env vars

DATABASE_URL → Postgres-backed sessions/leads/mutes/events
Not set      → in-memory fallback (local dev / tests)
"""

import os
import asyncio
import logging
from pathlib import Path

import httpx
from contextlib import asynccontextmanager
from datetime import timedelta
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response, HTTPException
from anthropic import AsyncAnthropic

# Load backend/.env before any os.environ reads (uvicorn does not auto-load it)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.menu import load_menu, menu_as_text
from app.sessions import get_session, save_session, clear_session, get_sender_lock
from app.orders import detect_confirmed_order, forward_order_to_owner  # noqa: F401
from app.tenants import Tenant
from app.tenant_resolver import resolve_tenant

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("orderbot")

# ---------------------------------------------------------------------------
# Globals that don't change per-tenant
# ---------------------------------------------------------------------------
VERIFY_TOKEN    = os.environ["WHATSAPP_VERIFY_TOKEN"]
WHATSAPP_TOKEN  = os.environ["WHATSAPP_ACCESS_TOKEN"]
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

anthropic_client = AsyncAnthropic()


# ---------------------------------------------------------------------------
# Lifespan — migrations + tenant DB sync
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before accepting requests."""
    from app.db.migrate import run_migrations
    from app.db.engine import DB_ENABLED

    await run_migrations()

    if DB_ENABLED:
        try:
            from app.dashboard.users import seed_admin_user
            await seed_admin_user()
        except Exception as exc:
            log.error(f"main: admin seed failed — {exc}")
        try:
            from app.db.engine import get_db
            from app.db.repo import sync_tenants_to_db
            from app.tenants import get_all_tenants
            async with get_db() as db:
                await sync_tenants_to_db(db, get_all_tenants())
            log.info("main: tenant DB sync complete")
        except Exception as exc:
            log.error(f"main: tenant DB sync failed — {exc}")

    from app.dashboard.auth import is_dashboard_enabled
    if _DASHBOARD_BUILT:
        log.info("main: dashboard UI ready at /dashboard")
        if not is_dashboard_enabled():
            log.warning(
                "main: dashboard UI is built but DASHBOARD_USER / DASHBOARD_PASSWORD / "
                "DASHBOARD_JWT_SECRET are not all set — login API will return 404"
            )
    else:
        log.warning(
            "main: dashboard UI not found at %s — run: npm run build",
            _DASHBOARD_DIR,
        )

    yield  # app runs here


app = FastAPI(title="WhatsApp Bot", lifespan=lifespan)

# Dashboard API (404 when DASHBOARD_* env vars absent; 503 without DATABASE_URL)
from app.dashboard.routes import router as dashboard_router  # noqa: E402
app.include_router(dashboard_router)

# Serve built React dashboard (Vite → app/static/dashboard)
from fastapi.responses import RedirectResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402


def _resolve_dashboard_dir() -> Path:
    """Find built dashboard files — always relative to this package, not CWD."""
    return Path(__file__).resolve().parent / "static" / "dashboard"


_DASHBOARD_DIR = _resolve_dashboard_dir()
_DASHBOARD_BUILT = (_DASHBOARD_DIR / "index.html").is_file()


# Lead-flow symbols (always imported — tenants choose which flow to run)
from app.lead import (                                      # noqa: E402
    get_lead_meta, clear_lead_meta, has_active_lead,
    extract_lead_marker, extract_meta_from_turn,
    forward_lead_card, get_phase_interactive,
    apply_interactive_answer,
    classify_entry_intent, build_entry_response,
    INTENT_DEMO_FIRST,
)
from app.interactive import parse_interactive_reply         # noqa: E402
from app.sheet import upsert_lead, parse_slot_datetime      # noqa: E402
from app.sheet import (                                     # noqa: E402
    STATUS_NEW, STATUS_IN_PROGRESS,
    STATUS_DEMO_BOOKED, STATUS_NOT_RESPONDING,
)

# Order-flow: load the default menu for single-tenant compat
_default_menu = load_menu()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_graph_url(phone_number_id: str) -> str:
    return f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"


def _is_own_number(phone: str, tenant: Tenant) -> bool:
    from app.sheet import _normalize_phone
    normalized = _normalize_phone(phone)
    own = {_normalize_phone(n) for n in (tenant.owner_whatsapp, tenant.business_wa_id) if n}
    return normalized in own


def _karachi_now():
    from app.sheet import _karachi_now as _kn
    return _kn()


def _sheet_upsert(sender: str, fields: dict, tenant: Tenant) -> None:
    """Fire-and-forget sheet write, skipping own/owner numbers."""
    if _is_own_number(sender, tenant):
        return
    gsheet_id = tenant.sheet.gsheet_id if tenant.sheet else ""
    tab = tenant.sheet.tab if tenant.sheet else ""
    if not gsheet_id:
        return
    asyncio.create_task(upsert_lead(sender, fields, gsheet_id=gsheet_id, tab=tab))


def _sheet_field_update(sender: str, meta: dict, tenant: Tenant) -> None:
    from app.flow import sheet_fields_from_meta
    fields = sheet_fields_from_meta(meta)
    # Keep classic fields if helper returns empty for partial meta
    if not fields:
        fields = {
            k: meta[k]
            for k in ("business_name", "business_type", "current_system")
            if meta.get(k)
        }
    if fields:
        _sheet_upsert(sender, fields, tenant)


# ---------------------------------------------------------------------------
# DB helpers — fire-and-forget; never delay or break a reply
# ---------------------------------------------------------------------------

async def _db_save_lead_state(sender: str, meta: dict, tenant: Tenant) -> None:
    """Persist active lead session state. Errors logged only."""
    try:
        from app.db.store import SessionStore
        store = await SessionStore.load(sender, tenant)
        store.meta = dict(meta)
        store.phase = meta.get("phase", store.phase or "GREETING")
        store.history = list(get_session(sender, tenant_id=tenant.phone_number_id))
        await store.save()
    except Exception as exc:
        log.error(f"db: save lead state failed for {sender} — {exc}")


async def _db_close_lead(
    sender: str, meta: dict, tenant: Tenant, status: str
) -> None:
    """Close lead session + append audit event. Errors logged only."""
    try:
        from app.db.store import SessionStore, EventStore
        store = await SessionStore.load(sender, tenant)
        store.meta = dict(meta)
        store.phase = meta.get("phase", store.phase or "GREETING")
        store.history = list(get_session(sender, tenant_id=tenant.phone_number_id))
        await store.close(status)
        await EventStore.append(
            tenant, status, {"phase": meta.get("phase", "")}, wa_id=sender
        )
    except Exception as exc:
        log.error(f"db: close lead failed for {sender} — {exc}")


async def _db_persist_lead(sender: str, meta: dict, tenant: Tenant) -> None:
    """Save or close based on phase (CONFIRMED / STALLED → close)."""
    phase = meta.get("phase", "")
    if phase == "CONFIRMED":
        await _db_close_lead(sender, meta, tenant, "confirmed")
    elif phase == "STALLED":
        await _db_close_lead(sender, meta, tenant, "stalled")
    else:
        await _db_save_lead_state(sender, meta, tenant)


async def _db_append_event(
    tenant: Tenant,
    event_type: str,
    payload: dict,
    wa_id: str | None = None,
) -> None:
    """Append audit event. Errors logged only."""
    try:
        from app.db.store import EventStore
        await EventStore.append(tenant, event_type, payload, wa_id=wa_id)
    except Exception as exc:
        log.error(f"db: append event ({event_type}) failed — {exc}")


async def _db_save_order_state(sender: str, tenant: Tenant) -> None:
    """Persist order-flow session history. Errors logged only."""
    try:
        from app.db.store import SessionStore
        store = await SessionStore.load(sender, tenant)
        store.history = list(get_session(sender, tenant_id=tenant.phone_number_id))
        store.phase = "ORDERING"
        store.meta = {"phase": "ORDERING"}
        await store.save()
    except Exception as exc:
        log.error(f"db: save order state failed for {sender} — {exc}")


async def _db_confirm_order(
    sender: str, tenant: Tenant, order: dict, history: list | None = None
) -> None:
    """Persist confirmed order + close session + event. Errors logged only."""
    try:
        from app.db.store import SessionStore, OrderStore, EventStore
        store = await SessionStore.load(sender, tenant)
        store.history = list(
            history if history is not None
            else get_session(sender, tenant_id=tenant.phone_number_id)
        )
        store.phase = "CONFIRMED"
        store.meta = {"phase": "CONFIRMED", "order": order}
        await store.save()
        await OrderStore.save_order(tenant, sender, order, store)
        await store.close("confirmed")
        await EventStore.append(
            tenant, "confirmed",
            {"total": order.get("total"), "items": order.get("items", [])},
            wa_id=sender,
        )
    except Exception as exc:
        log.error(f"db: confirm order failed for {sender} — {exc}")


async def _db_close_order_session(sender: str, tenant: Tenant, status: str = "closed") -> None:
    """Close order session (e.g. reset). Errors logged only."""
    try:
        from app.db.store import SessionStore
        store = await SessionStore.load(sender, tenant)
        store.history = list(get_session(sender, tenant_id=tenant.phone_number_id))
        await store.close(status)
    except Exception as exc:
        log.error(f"db: close order session failed for {sender} — {exc}")


def _build_order_system_prompt(tenant: Tenant) -> str:
    if tenant.menu:
        menu_dict = tenant.menu.model_dump()
        from app.menu import menu_as_text as _mat
        menu_text = _mat(menu_dict)
        shop_name = tenant.menu.shop_name
    else:
        menu_text = menu_as_text(_default_menu)
        shop_name = _default_menu["shop_name"]
    return (
        f"You are a friendly, efficient order-taking assistant for {shop_name}, a food shop in Pakistan.\n\n"
        "Rules:\n"
        "- Speak simple English mixed with Roman Urdu, matching the customer's language.\n"
        "- Only offer items from the menu below. Never invent items or prices.\n"
        "- Keep every reply under 3 short lines. No long paragraphs.\n"
        "- Flow: greet -> take items -> confirm quantities -> ask delivery address -> "
        "read back full order with total -> ask \"Confirm karein? (yes/no)\".\n"
        "- When the customer confirms the final order, reply with the confirmation message "
        "AND on a new final line output exactly:\n"
        "  ORDER_JSON: {\"items\": [{\"name\": ..., \"qty\": ..., \"price\": ...}], "
        "\"total\": ..., \"address\": ...}\n"
        "- Never output ORDER_JSON before the customer explicitly confirms.\n"
        "- If asked something unrelated to food orders, politely steer back to the menu.\n\n"
        f"MENU:\n{menu_text}"
    )


# ---------------------------------------------------------------------------
# Webhook endpoints
# ---------------------------------------------------------------------------

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()

    try:
        entry = body["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError):
        return {"status": "ignored"}

    # ── Tenant routing ────────────────────────────────────────────────────
    phone_number_id = (
        body.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("metadata", {})
        .get("phone_number_id", "")
    )
    # Fallback: some test fixtures omit metadata — use the configured default
    if not phone_number_id:
        phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "default")

    tenant = await resolve_tenant(phone_number_id)
    if tenant is None:
        return {"status": "ignored"}

    # Draft / paused: webhook still accepted & logged, but bot does not reply
    if not tenant.is_live:
        log.info(
            f"tenant {tenant.phone_number_id!r} status={tenant.status!r} — "
            "inbound logged, no reply"
        )
        try:
            from app.db.store import EventStore
            wa_id = ""
            try:
                wa_id = entry["messages"][0]["from"]
            except (KeyError, IndexError, TypeError):
                pass
            asyncio.create_task(
                EventStore.append(
                    tenant,
                    "inbound_paused",
                    {"status": tenant.status, "phone_number_id": phone_number_id},
                    wa_id=wa_id or None,
                )
            )
        except Exception:
            pass
        return {"status": "ok", "bot": "paused"}

    if tenant.flow_mode == "lead":
        return await _handle_lead_flow(entry, tenant)
    else:
        return await _handle_order_flow(entry, tenant)


@app.get("/")
async def health():
    from app.tenants import get_all_tenants
    from app.db.engine import DB_ENABLED
    from app.dashboard.auth import is_dashboard_enabled
    return {
        "status": "running",
        "tenants": [t.phone_number_id for t in get_all_tenants()],
        "dashboard": {
            "url": "/dashboard",
            "built": _DASHBOARD_BUILT,
            "auth_configured": is_dashboard_enabled(),
            "database": DB_ENABLED,
        },
    }


# ---------------------------------------------------------------------------
# Lead flow
# ---------------------------------------------------------------------------

async def _handle_lead_flow(entry: dict, tenant: Tenant) -> dict:
    from app.gate import check_gate

    tid = tenant.phone_number_id
    pre_sender = ""
    try:
        pre_sender = entry["messages"][0]["from"]
    except (KeyError, IndexError):
        pass
    active = has_active_lead(pre_sender, tenant_id=tid) if pre_sender else False

    gate = check_gate(entry, active_session=active, tenant=tenant)

    if not gate.allowed:
        if not gate.is_status_event:
            try:
                contacts = entry.get("contacts", [])
                if contacts and "messages" in entry:
                    contact_ids = {c.get("wa_id") for c in contacts}
                    if pre_sender not in contact_ids:
                        customer_id = next(iter(contact_ids), None)
                        if customer_id and not _is_own_number(customer_id, tenant):
                            ts = _karachi_now().strftime("%Y-%m-%d %H:%M")
                            _sheet_upsert(customer_id, {"notes": f"Human took over {ts}"}, tenant)
            except Exception:
                pass
        return {"status": "ignored"}

    sender = gate.sender

    async with get_sender_lock(sender, tenant_id=tid):
        meta = get_lead_meta(sender, tenant_id=tid)

        is_new_activation = gate.lead_source and "lead_source" not in meta
        if is_new_activation:
            meta["lead_source"] = gate.lead_source
            # Stamp per-tenant demo slots into meta for downstream use
            meta.setdefault("_slot_1", tenant.demo_slot_1)
            meta.setdefault("_slot_2", tenant.demo_slot_2)
            if not _is_own_number(sender, tenant):
                profile_name = ""
                try:
                    contacts = entry.get("contacts", [])
                    if contacts:
                        profile_name = contacts[0].get("profile", {}).get("name", "")
                except Exception:
                    pass
                _sheet_upsert(sender, {"name": profile_name, "status": STATUS_NEW,
                                       "interest": gate.lead_source}, tenant)
                # DB: fire-and-forget activation event
                asyncio.create_task(_db_save_lead_state(sender, meta, tenant))
                asyncio.create_task(_db_append_event(
                    tenant, "activation",
                    {"lead_source": gate.lead_source, "profile_name": profile_name},
                    wa_id=sender,
                ))
        if gate.referral:
            meta["referral_source_id"] = gate.referral.get("source_id", "")
            meta["referral_headline"]  = gate.referral.get("headline", "")

        if gate.message_type == "interactive":
            result = await _handle_interactive_reply(sender, meta, entry, tenant)
            asyncio.create_task(_db_persist_lead(sender, meta, tenant))
            return result

        user_text = gate.text or ""
        log.info(f"[{tid}] lead: {sender} [{meta.get('phase')}]: {user_text!r}")
        meta.setdefault("lang", tenant.lang_code())

        # FAQ before any LLM / phase logic (non-terminal phases)
        phase_now = meta.get("phase", "")
        if phase_now not in ("CONFIRMED", "STALLED") and user_text:
            if await _maybe_faq_reply(sender, meta, user_text, meta.get("lang", "ur"), tenant):
                asyncio.create_task(_db_persist_lead(sender, meta, tenant))
                return {"status": "ok"}

        # Non-text
        if gate.message_type not in ("text",):
            lang = meta.get("lang", "ur")
            phase = meta.get("phase", "GREETING")
            if phase == "GREETING":
                meta["phase"] = "BUSINESS_NAME"
                meta["entry_intent"] = "GENERIC_INFO"
                from app.lead import _media_first_text
                reply_text = _media_first_text(lang, tenant)
            else:
                from app.lead import lead_text, build_reprompt
                reply_text = (
                    f"{lead_text('unsupported_media', lang, tenant)}\n\n"
                    f"{build_reprompt(phase, lang, tenant)}"
                )
            await send_whatsapp_message(sender, reply_text, tenant=tenant)
            asyncio.create_task(_db_persist_lead(sender, meta, tenant))
            return {"status": "ok"}

        # Custom slot
        if meta.get("awaiting_custom_slot") and user_text:
            meta["demo_slot"] = user_text.strip()
            meta.pop("awaiting_custom_slot")
            meta["phase"] = "CONFIRMED"
            lang = meta.get("lang", "ur")
            from app.lead import lead_text
            confirm_msg = lead_text(
                "confirm_slot", lang, tenant, slot=meta["demo_slot"]
            )
            await send_whatsapp_message(sender, confirm_msg, tenant=tenant)
            await forward_lead_card(sender, meta, tenant.owner_whatsapp,
                                    lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant),
                                    tenant=tenant)
            demo_date, demo_time = parse_slot_datetime(meta["demo_slot"])
            _sheet_upsert(sender, {"status": STATUS_DEMO_BOOKED,
                "notes": f"Demo confirmed via bot: {meta['demo_slot']}",
                "next_followup": demo_date or "", "demo_date": demo_date or "",
                "demo_time": demo_time or "", "business_name": meta.get("business_name", ""),
                "business_type": meta.get("business_type", ""),
                "current_system": meta.get("current_system", "")}, tenant)
            asyncio.create_task(_db_close_lead(sender, meta, tenant, "confirmed"))
            clear_session(sender, tenant_id=tid)
            clear_lead_meta(sender, tenant_id=tid)
            return {"status": "ok"}

        # Entry intent
        if meta.get("phase") == "GREETING":
            result = await _handle_entry_message(sender, meta, user_text, tenant)
            asyncio.create_task(_db_persist_lead(sender, meta, tenant))
            return result

        phase = meta.get("phase", "")
        lang = meta.get("lang", "ur")

        from app.flow import find_step, get_tenant_flow

        step = find_step(get_tenant_flow(tenant), phase)
        if step and step.get("type") == "text_question" and step.get("capture_field") == "business_name":
            result = await _handle_business_name_phase(sender, meta, user_text, lang, tenant)
            asyncio.create_task(_db_persist_lead(sender, meta, tenant))
            return result
        if phase == "BUSINESS_NAME":
            result = await _handle_business_name_phase(sender, meta, user_text, lang, tenant)
            asyncio.create_task(_db_persist_lead(sender, meta, tenant))
            return result

        if step and step.get("type") in ("button_options", "list_options") and phase != "SCHEDULING":
            result = await _handle_text_at_flow_step(sender, meta, user_text, lang, step, tenant)
            asyncio.create_task(_db_persist_lead(sender, meta, tenant))
            return result

        # Legacy hard-coded matchers (same as default flow keys)
        if phase == "BUSINESS_TYPE":
            result = await _handle_text_at_interactive_phase(
                sender, meta, user_text, lang, _match_business_type, "LOCATIONS", "business_type", tenant)
            asyncio.create_task(_db_persist_lead(sender, meta, tenant))
            return result
        if phase == "LOCATIONS":
            result = await _handle_text_at_interactive_phase(
                sender, meta, user_text, lang, _match_locations, "CURRENT_SYSTEM", "locations", tenant)
            asyncio.create_task(_db_persist_lead(sender, meta, tenant))
            return result
        if phase == "CURRENT_SYSTEM":
            result = await _handle_text_at_interactive_phase(
                sender, meta, user_text, lang, _match_current_system, "SCHEDULING", "current_system", tenant)
            asyncio.create_task(_db_persist_lead(sender, meta, tenant))
            return result

        if step and step.get("type") == "free_text_capture":
            result = await _handle_free_text_capture_step(sender, meta, user_text, lang, step, tenant)
            asyncio.create_task(_db_persist_lead(sender, meta, tenant))
            return result

        result = await _handle_llm_turn(sender, meta, user_text, lang, tenant)
        asyncio.create_task(_db_persist_lead(sender, meta, tenant))
        return result


async def _handle_entry_message(sender: str, meta: dict, user_text: str, tenant: Tenant) -> dict:
    lang = tenant.lang_code()
    meta["lang"] = lang
    if await _maybe_faq_reply(sender, meta, user_text, lang, tenant):
        return {"status": "ok"}
    intent = classify_entry_intent(user_text)
    meta["entry_intent"] = intent
    reply_text, next_phase = build_entry_response(intent, lang=lang, tenant=tenant)
    meta["phase"] = next_phase
    await send_whatsapp_message(sender, reply_text, tenant=tenant)
    if not _is_own_number(sender, tenant):
        _sheet_upsert(sender, {"status": STATUS_IN_PROGRESS, "interest": intent}, tenant)
    if intent == INTENT_DEMO_FIRST:
        await _maybe_send_interactive(sender, meta, tenant)
    return {"status": "ok"}


async def _handle_interactive_reply(sender: str, meta: dict, entry: dict, tenant: Tenant) -> dict:
    tid = tenant.phone_number_id
    message = entry["messages"][0]
    reply_id, reply_title = parse_interactive_reply(message)
    if reply_id is None:
        log.warning(f"[{tid}] lead: malformed interactive from {sender}")
        return {"status": "ignored"}

    handled, follow_up = apply_interactive_answer(meta, reply_id, reply_title, tenant=tenant)

    if not handled:
        user_text = reply_title or reply_id
        reply = await _generate_lead_reply(sender, user_text, tenant)
        extract_meta_from_turn(meta, user_text, reply)
        marker, clean_reply = extract_lead_marker(reply)
        if marker == "CONFIRMED":
            meta["phase"] = "CONFIRMED"
            await send_whatsapp_message(sender, clean_reply, tenant=tenant)
            await forward_lead_card(sender, meta, tenant.owner_whatsapp,
                                    lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant),
                                    tenant=tenant)
            clear_session(sender, tenant_id=tid)
            clear_lead_meta(sender, tenant_id=tid)
        else:
            await send_whatsapp_message(sender, clean_reply, tenant=tenant)
            await _maybe_send_interactive(sender, meta, tenant)
        return {"status": "ok"}

    if follow_up:
        await send_whatsapp_message(sender, follow_up, tenant=tenant)
        return {"status": "ok"}

    if meta.get("phase") == "CONFIRMED":
        lang = meta.get("lang", "ur")
        from app.lead import lead_text
        confirm_msg = lead_text(
            "confirm_slot", lang, tenant, slot=meta.get("demo_slot", "")
        )
        await send_whatsapp_message(sender, confirm_msg, tenant=tenant)
        await forward_lead_card(sender, meta, tenant.owner_whatsapp,
                                lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant),
                                tenant=tenant)
        demo_date, demo_time = parse_slot_datetime(meta.get("demo_slot", ""))
        _sheet_upsert(sender, {"status": STATUS_DEMO_BOOKED,
            "notes": f"Demo confirmed via bot: {meta.get('demo_slot', '?')}",
            "next_followup": demo_date or "", "demo_date": demo_date or "",
            "demo_time": demo_time or "", "business_name": meta.get("business_name", ""),
            "business_type": meta.get("business_type", ""),
            "current_system": meta.get("current_system", "")}, tenant)
        clear_session(sender, tenant_id=tid)
        clear_lead_meta(sender, tenant_id=tid)
        return {"status": "ok"}

    await _maybe_send_interactive(sender, meta, tenant)
    return {"status": "ok"}


async def _maybe_send_interactive(sender: str, meta: dict, tenant: Tenant) -> None:
    phase = meta.get("phase", "GREETING")
    lang = meta.get("lang", "ur")
    payload = get_phase_interactive(phase, sender, lang, meta=meta, tenant=tenant)
    if payload:
        await send_whatsapp_message(sender, interactive_payload=payload, tenant=tenant)


async def _handle_business_name_phase(
    sender: str, meta: dict, user_text: str, lang: str, tenant: Tenant
) -> dict:
    from app.lead import (
        handle_business_name, _is_detour_question,
        extract_detour_done, lead_text,
    )
    if _is_detour_question(user_text):
        detour_reply = await _generate_lead_reply(sender, user_text, tenant)
        _, clean_detour = extract_detour_done(detour_reply)
        re_ask = lead_text("q_business_name", lang, tenant)
        combined = f"{clean_detour}\n\n{re_ask}" if clean_detour else re_ask
        await send_whatsapp_message(sender, combined, tenant=tenant)
        return {"status": "ok"}
    ack_text, accepted = handle_business_name(meta, user_text, lang, tenant=tenant)
    if accepted:
        _sheet_field_update(sender, meta, tenant)
        next_phase = meta.get("phase", "BUSINESS_TYPE")
        payload = get_phase_interactive(next_phase, sender, lang, meta=meta, tenant=tenant)
        if payload:
            await send_whatsapp_message(sender, interactive_payload=payload, tenant=tenant)
        else:
            await send_whatsapp_message(sender, ack_text, tenant=tenant)
    else:
        await send_whatsapp_message(sender, ack_text, tenant=tenant)
    return {"status": "ok"}


async def _handle_text_at_flow_step(
    sender: str, meta: dict, user_text: str, lang: str, step: dict, tenant: Tenant
) -> dict:
    """Free-text answer while on a button/list step — match option or re-prompt."""
    from app.flow import match_text_to_step_option, next_phase_key, step_question_text
    from app.lead import (
        build_handoff,
        increment_reprompt,
        reset_reprompts,
        MAX_REPROMPTS,
        extract_detour_done,
        _is_detour_question,
        build_reprompt,
    )

    tid = tenant.phone_number_id
    phase = step.get("key") or meta.get("phase", "")
    field = step.get("capture_field") or ""

    # Prefer legacy fuzzy matchers for classic steps (byte-identical)
    display_val = None
    sheet_val = None
    if phase == "BUSINESS_TYPE":
        display_val, sheet_val = _match_business_type(user_text)
    elif phase == "LOCATIONS":
        display_val, sheet_val = _match_locations(user_text)
    elif phase == "CURRENT_SYSTEM":
        display_val, sheet_val = _match_current_system(user_text)
    else:
        matched = match_text_to_step_option(step, user_text, tenant, lang)
        if matched is not None:
            display_val = sheet_val = matched

    if display_val is not None:
        if field:
            meta[field] = sheet_val
        meta["phase"] = next_phase_key(tenant, phase)
        reset_reprompts(meta)
        _sheet_field_update(sender, meta, tenant)
        advance_to = meta["phase"]
        payload = get_phase_interactive(advance_to, sender, lang, meta=meta, tenant=tenant)
        if payload:
            await send_whatsapp_message(sender, interactive_payload=payload, tenant=tenant)
        else:
            from app.lead import lead_text
            await send_whatsapp_message(
                sender, lead_text("q_business_name", lang, tenant), tenant=tenant
            )
        return {"status": "ok"}

    if _is_detour_question(user_text):
        detour_reply = await _generate_lead_reply(sender, user_text, tenant)
        _, clean_detour = extract_detour_done(detour_reply)
        re_ask = step_question_text(step, lang, tenant)
        combined = f"{clean_detour}\n\n{re_ask}" if clean_detour else re_ask
        await send_whatsapp_message(sender, combined, tenant=tenant)
        return {"status": "ok"}

    count = increment_reprompt(meta)
    if count > MAX_REPROMPTS:
        meta["phase"] = "STALLED"
        await send_whatsapp_message(sender, build_handoff(lang, tenant), tenant=tenant)
        await forward_lead_card(
            sender, meta, tenant.owner_whatsapp,
            lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant),
            tenant=tenant,
        )
        clear_session(sender, tenant_id=tid)
        clear_lead_meta(sender, tenant_id=tid)
    else:
        await send_whatsapp_message(
            sender, build_reprompt(phase, lang, tenant), tenant=tenant
        )
    return {"status": "ok"}


async def _handle_free_text_capture_step(
    sender: str, meta: dict, user_text: str, lang: str, step: dict, tenant: Tenant
) -> dict:
    from app.flow import next_phase_key, step_question_text
    from app.lead import reset_reprompts, lead_text

    stripped = user_text.strip()
    if not stripped:
        await send_whatsapp_message(
            sender, step_question_text(step, lang, tenant), tenant=tenant
        )
        return {"status": "ok"}
    field = step.get("capture_field")
    if field:
        meta[field] = stripped
    meta["phase"] = next_phase_key(tenant, step.get("key", ""))
    reset_reprompts(meta)
    _sheet_field_update(sender, meta, tenant)
    payload = get_phase_interactive(meta["phase"], sender, lang, meta=meta, tenant=tenant)
    if payload:
        await send_whatsapp_message(sender, interactive_payload=payload, tenant=tenant)
    else:
        await send_whatsapp_message(
            sender, lead_text("ack_business_name", lang, tenant, name=stripped), tenant=tenant
        )
    return {"status": "ok"}


def _match_business_type(text: str) -> tuple:
    from app.lead import match_free_text_business_type, _BUSINESS_TYPE_LABELS
    btype_id = match_free_text_business_type(text)
    if btype_id:
        label = _BUSINESS_TYPE_LABELS[btype_id]
        return label, label
    return None, None


def _match_locations(text: str) -> tuple:
    import re as _re
    _NUMS = {"ek": "1", "one": "1", "do": "2", "two": "2", "teen": "3", "three": "3",
             "char": "4", "four": "4", "paanch": "5", "five": "5", "chay": "6", "six": "6",
             "saat": "7", "seven": "7", "aath": "8", "eight": "8", "nau": "9", "nine": "9",
             "das": "10", "ten": "10"}
    lower = text.lower().strip()
    m = _re.search(r"\b(\d+)\b", lower)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 20:
            return str(n), str(n)
    for word, digit in _NUMS.items():
        if word in lower.split():
            return digit, digit
    if _re.fullmatch(r"\d+[\-\+]\d*", lower.strip()):
        return lower.strip(), lower.strip()
    return None, None


def _match_current_system(text: str) -> tuple:
    from app.lead import _CURRENT_SYSTEM_SHEET_VALUES
    lower = text.lower()
    if any(kw in lower for kw in ("manual", "dasti", "register", "hand")):
        return "Manual Register", _CURRENT_SYSTEM_SHEET_VALUES["sys_manual"]
    if any(kw in lower for kw in ("pos", "software", "system", "computer", "digital")):
        return "Existing POS", _CURRENT_SYSTEM_SHEET_VALUES["sys_pos"]
    if any(kw in lower for kw in ("kuch nahi", "nothing", "no system", "nahi", "none", "koi nahi")):
        return "No System", _CURRENT_SYSTEM_SHEET_VALUES["sys_none"]
    return None, None


async def _handle_text_at_interactive_phase(
    sender: str, meta: dict, user_text: str, lang: str,
    match_fn, advance_to: str, field_key: str, tenant: Tenant,
) -> dict:
    from app.lead import (
        build_reprompt, build_handoff,
        increment_reprompt, reset_reprompts, MAX_REPROMPTS,
        extract_detour_done, _is_detour_question, lead_text,
    )
    tid = tenant.phone_number_id
    display_val, sheet_val = match_fn(user_text)
    if display_val is not None:
        meta[field_key] = sheet_val
        meta["phase"] = advance_to
        reset_reprompts(meta)
        _sheet_field_update(sender, meta, tenant)
        payload = get_phase_interactive(advance_to, sender, lang, meta=meta, tenant=tenant)
        if payload:
            await send_whatsapp_message(sender, interactive_payload=payload, tenant=tenant)
        else:
            await send_whatsapp_message(sender, lead_text("q_business_name", lang, tenant), tenant=tenant)
        return {"status": "ok"}

    if _is_detour_question(user_text):
        detour_reply = await _generate_lead_reply(sender, user_text, tenant)
        _, clean_detour = extract_detour_done(detour_reply)
        _phase_q = {
            "BUSINESS_TYPE": "q_business_type",
            "LOCATIONS": "q_locations",
            "CURRENT_SYSTEM": "q_current_system",
        }
        phase = meta.get("phase", "")
        re_ask = lead_text(_phase_q.get(phase, "q_business_name"), lang, tenant)
        combined = f"{clean_detour}\n\n{re_ask}" if clean_detour else re_ask
        await send_whatsapp_message(sender, combined, tenant=tenant)
        return {"status": "ok"}

    count = increment_reprompt(meta)
    if count > MAX_REPROMPTS:
        meta["phase"] = "STALLED"
        await send_whatsapp_message(sender, build_handoff(lang, tenant), tenant=tenant)
        await forward_lead_card(sender, meta, tenant.owner_whatsapp,
                                lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant),
                                tenant=tenant)
        clear_session(sender, tenant_id=tid)
        clear_lead_meta(sender, tenant_id=tid)
    else:
        await send_whatsapp_message(
            sender, build_reprompt(meta.get("phase", ""), lang, tenant), tenant=tenant
        )
    return {"status": "ok"}


async def _handle_llm_turn(sender: str, meta: dict, user_text: str, lang: str, tenant: Tenant) -> dict:
    from app.lead import extract_detour_done, build_reprompt
    tid = tenant.phone_number_id
    reply = await _generate_lead_reply(sender, user_text, tenant)
    is_detour, clean_reply = extract_detour_done(reply)
    if is_detour:
        phase = meta.get("phase", "")
        re_ask = build_reprompt(phase, lang, tenant).split(". ", 1)[-1]
        combined = f"{clean_reply}\n\n{re_ask}" if clean_reply else re_ask
        await send_whatsapp_message(sender, combined, tenant=tenant)
        return {"status": "ok"}

    extract_meta_from_turn(meta, user_text, reply)
    marker, clean_reply = extract_lead_marker(reply)

    if marker == "CONFIRMED":
        meta["phase"] = "CONFIRMED"
        await send_whatsapp_message(sender, clean_reply, tenant=tenant)
        await forward_lead_card(sender, meta, tenant.owner_whatsapp,
                                lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant),
                                tenant=tenant)
        demo_date, demo_time = parse_slot_datetime(meta.get("demo_slot", ""))
        _sheet_upsert(sender, {"status": STATUS_DEMO_BOOKED,
            "notes": f"Demo confirmed via bot: {meta.get('demo_slot', '?')}",
            "next_followup": demo_date or "", "demo_date": demo_date or "",
            "demo_time": demo_time or "", "business_name": meta.get("business_name", ""),
            "business_type": meta.get("business_type", ""),
            "current_system": meta.get("current_system", "")}, tenant)
        clear_session(sender, tenant_id=tid)
        clear_lead_meta(sender, tenant_id=tid)
        return {"status": "ok"}

    if marker == "STALLED":
        meta["phase"] = "STALLED"
        if meta.get("business_name"):
            await forward_lead_card(sender, meta, tenant.owner_whatsapp,
                                    lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant),
                                    tenant=tenant)
        tomorrow = (_karachi_now().date() + timedelta(days=1)).strftime("%Y-%m-%d")
        _sheet_upsert(sender, {"status": STATUS_NOT_RESPONDING,
            "notes": f"Bot: stalled at {meta.get('phase', '?')}",
            "next_followup": tomorrow, "business_name": meta.get("business_name", ""),
            "business_type": meta.get("business_type", ""),
            "current_system": meta.get("current_system", "")}, tenant)
        clear_session(sender, tenant_id=tid)
        clear_lead_meta(sender, tenant_id=tid)
        return {"status": "ok"}

    _sheet_field_update(sender, meta, tenant)
    new_phase = meta.get("phase", "")
    interactive_payload = get_phase_interactive(new_phase, sender, lang, meta=meta, tenant=tenant)
    if interactive_payload:
        await send_whatsapp_message(sender, interactive_payload=interactive_payload, tenant=tenant)
    else:
        await send_whatsapp_message(sender, clean_reply, tenant=tenant)
    return {"status": "ok"}


async def _maybe_faq_reply(
    sender: str, meta: dict, user_text: str, lang: str, tenant: Tenant
) -> bool:
    """If FAQ matches, send answer + phase reprompt. Returns True if handled."""
    from app.faq import classify_faq_match, match_faq
    from app.lead import build_reprompt

    answer = match_faq(user_text, tenant.faq_list)
    if not answer:
        answer = await classify_faq_match(
            user_text, tenant.faq_list, client=anthropic_client, model=ANTHROPIC_MODEL
        )
    if not answer:
        return False
    phase = meta.get("phase", "")
    if phase and phase not in ("GREETING", "CONFIRMED", "STALLED"):
        reprompt = build_reprompt(phase, lang, tenant)
        msg = f"{answer}\n\n{reprompt}"
    else:
        msg = answer
    await send_whatsapp_message(sender, msg, tenant=tenant)
    return True


async def _generate_lead_reply(sender: str, user_text: str, tenant: Tenant) -> str:
    from app.lead import build_lead_system_prompt
    tid = tenant.phone_number_id
    history = get_session(sender, tenant_id=tid)
    history.append({"role": "user", "content": user_text})
    system = build_lead_system_prompt(tenant)
    try:
        response = await anthropic_client.messages.create(
            model=ANTHROPIC_MODEL, max_tokens=400,
            system=system, messages=history[-20:],
        )
        reply = response.content[0].text
    except Exception as e:
        log.error(f"Claude API error (lead): {e}")
        return tenant.msg().text("lead.error_fallback")
    history.append({"role": "assistant", "content": reply})
    save_session(sender, history, tenant_id=tid)
    return reply


# ---------------------------------------------------------------------------
# Order flow
# ---------------------------------------------------------------------------

async def _handle_order_flow(entry: dict, tenant: Tenant) -> dict:
    # Interactive menu_v2 path
    if getattr(tenant, "menu_v2", None):
        from app.order_flow import handle_order_interactive
        from app.orders import forward_order_to_owner

        async def _on_confirm(order: dict, sender: str, t: Tenant) -> None:
            await forward_order_to_owner(
                order, sender, t.owner_whatsapp,
                lambda to, txt: send_whatsapp_message(to, txt, tenant=t),
                tenant=t,
            )
            hist = list(get_session(sender, tenant_id=t.phone_number_id))
            asyncio.create_task(_db_confirm_order(sender, t, order, history=hist))

        return await handle_order_interactive(
            entry, tenant, send_whatsapp_message, on_confirm=_on_confirm
        )

    if "messages" not in entry:
        return {"status": "ignored"}
    message = entry["messages"][0]
    sender = message["from"]
    tid = tenant.phone_number_id
    if message.get("type") != "text":
        await send_whatsapp_message(
            sender, tenant.msg().text("order.text_only"), tenant=tenant
        )
        return {"status": "ok"}
    user_text = message["text"]["body"].strip()
    if user_text.lower() in ("reset", "restart", "naya order"):
        asyncio.create_task(_db_close_order_session(sender, tenant, "closed"))
        clear_session(sender, tenant_id=tid)
        await send_whatsapp_message(
            sender, tenant.msg().text("order.reset_done"), tenant=tenant
        )
        return {"status": "ok"}
    async with get_sender_lock(sender, tenant_id=tid):
        if await _maybe_faq_reply(sender, {"phase": "ORDERING"}, user_text, "ur", tenant):
            return {"status": "ok"}
        reply = await _generate_order_reply(sender, user_text, tenant)
        order, clean_reply = detect_confirmed_order(reply)
        if order:
            await forward_order_to_owner(
                order, sender, tenant.owner_whatsapp,
                lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant),
                tenant=tenant,
            )
            hist = list(get_session(sender, tenant_id=tid))
            asyncio.create_task(_db_confirm_order(sender, tenant, order, history=hist))
            clear_session(sender, tenant_id=tid)
        else:
            asyncio.create_task(_db_save_order_state(sender, tenant))
    await send_whatsapp_message(sender, clean_reply, tenant=tenant)
    return {"status": "ok"}


async def _generate_order_reply(sender: str, user_text: str, tenant: Tenant) -> str:
    tid = tenant.phone_number_id
    history = get_session(sender, tenant_id=tid)
    history.append({"role": "user", "content": user_text})
    try:
        response = await anthropic_client.messages.create(
            model=ANTHROPIC_MODEL, max_tokens=400,
            system=_build_order_system_prompt(tenant), messages=history[-20:],
        )
        reply = response.content[0].text
    except Exception as e:
        log.error(f"Claude API error (order): {e}")
        return tenant.msg().text("order.error_fallback")
    history.append({"role": "assistant", "content": reply})
    save_session(sender, history, tenant_id=tid)
    return reply


# ---------------------------------------------------------------------------
# Outgoing messages via Meta Graph API
# ---------------------------------------------------------------------------

async def send_whatsapp_message(
    to: str,
    text: str = "",
    interactive_payload: dict = None,
    tenant: Tenant = None,
) -> bool:
    """Send a WhatsApp message through the tenant's phone number."""
    if interactive_payload is not None:
        payload = interactive_payload
        # Ensure the 'to' field in the payload uses the recipient, not a stale value
        payload = {**payload, "to": to}
    else:
        payload = {"messaging_product": "whatsapp", "to": to,
                   "type": "text", "text": {"body": text}}

    # Use tenant's phone_number_id for the Graph URL if available
    if tenant is not None:
        graph_url = tenant.graph_url
    else:
        phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        graph_url = f"https://graph.facebook.com/v21.0/{phone_number_id}/messages"

    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(graph_url, headers=headers, json=payload)
        if r.status_code >= 400:
            log.error(f"Send failed {r.status_code}: {r.text}")
            return False
    return True


# ---------------------------------------------------------------------------
# Dashboard UI (mount last — SPA + static assets under /dashboard/)
# ---------------------------------------------------------------------------

@app.get("/dashboard", include_in_schema=False)
async def dashboard_redirect():
    if not _DASHBOARD_BUILT:
        raise HTTPException(
            status_code=503,
            detail=f"Dashboard UI not found at {_DASHBOARD_DIR}. Run: npm run build",
        )
    return RedirectResponse(url="/dashboard/", status_code=307)


if _DASHBOARD_BUILT:
    log.info("main: mounting dashboard UI from %s", _DASHBOARD_DIR)
    app.mount(
        "/dashboard",
        StaticFiles(directory=str(_DASHBOARD_DIR), html=True),
        name="dashboard-ui",
    )
else:

    @app.get("/dashboard/", include_in_schema=False)
    @app.get("/dashboard/{rest:path}", include_in_schema=False)
    async def dashboard_unavailable(rest: str = ""):
        raise HTTPException(
            status_code=503,
            detail=f"Dashboard UI not found at {_DASHBOARD_DIR}. Run: npm run build",
        )
