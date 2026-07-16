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
import httpx
from contextlib import asynccontextmanager
from datetime import timedelta
from fastapi import FastAPI, Request, Response, HTTPException
from anthropic import AsyncAnthropic

from app.menu import load_menu, menu_as_text
from app.sessions import get_session, save_session, clear_session, get_sender_lock
from app.orders import detect_confirmed_order, forward_order_to_owner
from app.tenants import get_tenant, Tenant

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
            from app.db.engine import get_db
            from app.db.repo import sync_tenants_to_db
            from app.tenants import get_all_tenants
            async with get_db() as db:
                await sync_tenants_to_db(db, get_all_tenants())
            log.info("main: tenant DB sync complete")
        except Exception as exc:
            log.error(f"main: tenant DB sync failed — {exc}")

    yield  # app runs here


app = FastAPI(title="WhatsApp Bot", lifespan=lifespan)

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
    fields = {k: meta[k] for k in ("business_name", "business_type", "current_system") if meta.get(k)}
    if fields:
        _sheet_upsert(sender, fields, tenant)


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

    tenant = get_tenant(phone_number_id)
    if tenant is None:
        return {"status": "ignored"}

    if tenant.flow_mode == "lead":
        return await _handle_lead_flow(entry, tenant)
    else:
        return await _handle_order_flow(entry, tenant)


@app.get("/")
async def health():
    from app.tenants import get_all_tenants
    return {"status": "running", "tenants": [t.phone_number_id for t in get_all_tenants()]}


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
            asyncio.create_task(_db_save_lead_state(sender, meta, tenant))
            return result

        user_text = gate.text or ""
        log.info(f"[{tid}] lead: {sender} [{meta.get('phase')}]: {user_text!r}")

        # Non-text
        if gate.message_type not in ("text",):
            lang = meta.get("lang", "ur")
            phase = meta.get("phase", "GREETING")
            if phase == "GREETING":
                meta["phase"] = "BUSINESS_NAME"
                meta["entry_intent"] = "GENERIC_INFO"
                from app.lead import _media_first_text
                reply_text = _media_first_text(lang)
            else:
                from app.lead import _t, build_reprompt
                _UNSUPPORTED = {"ur": "Barah-e-karam apna jawab text mein likhein.",
                                "en": "Kindly respond in text so we may assist you."}
                reply_text = f"{_t(_UNSUPPORTED, lang)}\n\n{build_reprompt(phase, lang)}"
            await send_whatsapp_message(sender, reply_text, tenant=tenant)
            asyncio.create_task(_db_save_lead_state(sender, meta, tenant))
            return {"status": "ok"}

        # Custom slot
        if meta.get("awaiting_custom_slot") and user_text:
            meta["demo_slot"] = user_text.strip()
            meta.pop("awaiting_custom_slot")
            meta["phase"] = "CONFIRMED"
            lang = meta.get("lang", "ur")
            from app.lead import _t, _CONFIRM_SLOT
            confirm_msg = _t(_CONFIRM_SLOT, lang).format(slot=meta["demo_slot"])
            await send_whatsapp_message(sender, confirm_msg, tenant=tenant)
            await forward_lead_card(sender, meta, tenant.owner_whatsapp,
                                    lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant))
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
            asyncio.create_task(_db_save_lead_state(sender, meta, tenant))
            return result

        phase = meta.get("phase", "")
        lang = meta.get("lang", "ur")

        if phase == "BUSINESS_NAME":
            result = await _handle_business_name_phase(sender, meta, user_text, lang, tenant)
            asyncio.create_task(_db_save_lead_state(sender, meta, tenant))
            return result
        if phase == "BUSINESS_TYPE":
            result = await _handle_text_at_interactive_phase(
                sender, meta, user_text, lang, _match_business_type, "LOCATIONS", "business_type", tenant)
            asyncio.create_task(_db_save_lead_state(sender, meta, tenant))
            return result
        if phase == "LOCATIONS":
            result = await _handle_text_at_interactive_phase(
                sender, meta, user_text, lang, _match_locations, "CURRENT_SYSTEM", "locations", tenant)
            asyncio.create_task(_db_save_lead_state(sender, meta, tenant))
            return result
        if phase == "CURRENT_SYSTEM":
            result = await _handle_text_at_interactive_phase(
                sender, meta, user_text, lang, _match_current_system, "SCHEDULING", "current_system", tenant)
            asyncio.create_task(_db_save_lead_state(sender, meta, tenant))
            return result

        result = await _handle_llm_turn(sender, meta, user_text, lang, tenant)
        asyncio.create_task(_db_save_lead_state(sender, meta, tenant))
        return result


async def _handle_entry_message(sender: str, meta: dict, user_text: str, tenant: Tenant) -> dict:
    intent = classify_entry_intent(user_text)
    meta["entry_intent"] = intent
    reply_text, next_phase = build_entry_response(intent)
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

    handled, follow_up = apply_interactive_answer(meta, reply_id, reply_title)

    if not handled:
        user_text = reply_title or reply_id
        reply = await _generate_lead_reply(sender, user_text, tenant)
        extract_meta_from_turn(meta, user_text, reply)
        marker, clean_reply = extract_lead_marker(reply)
        if marker == "CONFIRMED":
            meta["phase"] = "CONFIRMED"
            await send_whatsapp_message(sender, clean_reply, tenant=tenant)
            await forward_lead_card(sender, meta, tenant.owner_whatsapp,
                                    lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant))
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
        from app.lead import _t, _CONFIRM_SLOT
        confirm_msg = _t(_CONFIRM_SLOT, lang).format(slot=meta.get("demo_slot", ""))
        await send_whatsapp_message(sender, confirm_msg, tenant=tenant)
        await forward_lead_card(sender, meta, tenant.owner_whatsapp,
                                lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant))
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
    payload = get_phase_interactive(phase, sender, meta=meta)
    if payload:
        await send_whatsapp_message(sender, interactive_payload=payload, tenant=tenant)


async def _handle_business_name_phase(
    sender: str, meta: dict, user_text: str, lang: str, tenant: Tenant
) -> dict:
    from app.lead import (
        handle_business_name, _is_detour_question,
        extract_detour_done, _t, _Q_BUSINESS_NAME,
    )
    if _is_detour_question(user_text):
        detour_reply = await _generate_lead_reply(sender, user_text, tenant)
        _, clean_detour = extract_detour_done(detour_reply)
        re_ask = _t(_Q_BUSINESS_NAME, lang)
        combined = f"{clean_detour}\n\n{re_ask}" if clean_detour else re_ask
        await send_whatsapp_message(sender, combined, tenant=tenant)
        return {"status": "ok"}
    ack_text, accepted = handle_business_name(meta, user_text, lang)
    if accepted:
        _sheet_field_update(sender, meta, tenant)
        payload = get_phase_interactive("BUSINESS_TYPE", sender, lang, meta=meta)
        if payload:
            await send_whatsapp_message(sender, interactive_payload=payload, tenant=tenant)
        else:
            await send_whatsapp_message(sender, ack_text, tenant=tenant)
    else:
        await send_whatsapp_message(sender, ack_text, tenant=tenant)
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
        extract_detour_done, _is_detour_question,
        _t, _Q_BUSINESS_TYPE, _Q_LOCATIONS, _Q_CURRENT_SYSTEM, _Q_BUSINESS_NAME,
    )
    tid = tenant.phone_number_id
    display_val, sheet_val = match_fn(user_text)
    if display_val is not None:
        meta[field_key] = sheet_val
        meta["phase"] = advance_to
        reset_reprompts(meta)
        _sheet_field_update(sender, meta, tenant)
        payload = get_phase_interactive(advance_to, sender, lang, meta=meta)
        if payload:
            await send_whatsapp_message(sender, interactive_payload=payload, tenant=tenant)
        else:
            await send_whatsapp_message(sender, _t(_Q_BUSINESS_NAME, lang), tenant=tenant)
        return {"status": "ok"}

    if _is_detour_question(user_text):
        detour_reply = await _generate_lead_reply(sender, user_text, tenant)
        _, clean_detour = extract_detour_done(detour_reply)
        _phase_q = {"BUSINESS_TYPE": _Q_BUSINESS_TYPE, "LOCATIONS": _Q_LOCATIONS,
                    "CURRENT_SYSTEM": _Q_CURRENT_SYSTEM}
        phase = meta.get("phase", "")
        re_ask = _t(_phase_q.get(phase, _Q_BUSINESS_NAME), lang)
        combined = f"{clean_detour}\n\n{re_ask}" if clean_detour else re_ask
        await send_whatsapp_message(sender, combined, tenant=tenant)
        return {"status": "ok"}

    count = increment_reprompt(meta)
    if count > MAX_REPROMPTS:
        meta["phase"] = "STALLED"
        await send_whatsapp_message(sender, build_handoff(lang), tenant=tenant)
        await forward_lead_card(sender, meta, tenant.owner_whatsapp,
                                lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant))
        clear_session(sender, tenant_id=tid)
        clear_lead_meta(sender, tenant_id=tid)
    else:
        await send_whatsapp_message(sender, build_reprompt(meta.get("phase", ""), lang), tenant=tenant)
    return {"status": "ok"}


async def _handle_llm_turn(sender: str, meta: dict, user_text: str, lang: str, tenant: Tenant) -> dict:
    from app.lead import extract_detour_done, build_reprompt
    tid = tenant.phone_number_id
    reply = await _generate_lead_reply(sender, user_text, tenant)
    is_detour, clean_reply = extract_detour_done(reply)
    if is_detour:
        phase = meta.get("phase", "")
        re_ask = build_reprompt(phase, lang).split(". ", 1)[-1]
        combined = f"{clean_reply}\n\n{re_ask}" if clean_reply else re_ask
        await send_whatsapp_message(sender, combined, tenant=tenant)
        return {"status": "ok"}

    extract_meta_from_turn(meta, user_text, reply)
    marker, clean_reply = extract_lead_marker(reply)

    if marker == "CONFIRMED":
        meta["phase"] = "CONFIRMED"
        await send_whatsapp_message(sender, clean_reply, tenant=tenant)
        await forward_lead_card(sender, meta, tenant.owner_whatsapp,
                                lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant))
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
                                    lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant))
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
    interactive_payload = get_phase_interactive(new_phase, sender, lang, meta=meta)
    if interactive_payload:
        await send_whatsapp_message(sender, interactive_payload=interactive_payload, tenant=tenant)
    else:
        await send_whatsapp_message(sender, clean_reply, tenant=tenant)
    return {"status": "ok"}


async def _generate_lead_reply(sender: str, user_text: str, tenant: Tenant) -> str:
    from app.lead import SYSTEM_PROMPT_LEAD
    tid = tenant.phone_number_id
    history = get_session(sender, tenant_id=tid)
    history.append({"role": "user", "content": user_text})
    try:
        response = await anthropic_client.messages.create(
            model=ANTHROPIC_MODEL, max_tokens=400,
            system=SYSTEM_PROMPT_LEAD, messages=history[-20:],
        )
        reply = response.content[0].text
    except Exception as e:
        log.error(f"Claude API error (lead): {e}")
        return "Sorry, thora sa masla aa gaya. Thodi der baad dobara try karein."
    history.append({"role": "assistant", "content": reply})
    save_session(sender, history, tenant_id=tid)
    return reply


# ---------------------------------------------------------------------------
# Order flow
# ---------------------------------------------------------------------------

async def _handle_order_flow(entry: dict, tenant: Tenant) -> dict:
    if "messages" not in entry:
        return {"status": "ignored"}
    message = entry["messages"][0]
    sender = message["from"]
    tid = tenant.phone_number_id
    if message.get("type") != "text":
        await send_whatsapp_message(sender, "Please send your order as a text message.", tenant=tenant)
        return {"status": "ok"}
    user_text = message["text"]["body"].strip()
    if user_text.lower() in ("reset", "restart", "naya order"):
        clear_session(sender, tenant_id=tid)
        await send_whatsapp_message(sender, "Order reset. What would you like to order?", tenant=tenant)
        return {"status": "ok"}
    async with get_sender_lock(sender, tenant_id=tid):
        reply = await _generate_order_reply(sender, user_text, tenant)
        order, clean_reply = detect_confirmed_order(reply)
        if order:
            await forward_order_to_owner(order, sender, tenant.owner_whatsapp,
                                         lambda to, txt: send_whatsapp_message(to, txt, tenant=tenant))
            clear_session(sender, tenant_id=tid)
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
        return "Sorry, an issue occurred. Please try again."
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
