"""
WhatsApp Bot — FastAPI + Meta Cloud API + Claude Haiku
Deploy target: Railway. Set env vars from .env.example before running.

FLOW_MODE=order  → original food-order bot (no gate)
FLOW_MODE=lead   → Bahi POS lead qualification with coexistence gate (default)
"""

import os
import asyncio
import logging
import httpx
from datetime import timedelta
from fastapi import FastAPI, Request, Response, HTTPException
from anthropic import AsyncAnthropic

from app.menu import load_menu, menu_as_text
from app.sessions import get_session, save_session, clear_session, get_sender_lock
from app.orders import detect_confirmed_order, forward_order_to_owner

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("orderbot")

# ---------------------------------------------------------------------------
# Config (all via environment variables — never hardcode)
# ---------------------------------------------------------------------------
VERIFY_TOKEN   = os.environ["WHATSAPP_VERIFY_TOKEN"]        # you invent this string
WHATSAPP_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]        # permanent system-user token
PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]    # from Meta dashboard
OWNER_WHATSAPP  = os.environ.get("OWNER_WHATSAPP", "")      # owner's number for cards/slips
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
FLOW_MODE       = os.environ.get("FLOW_MODE", "lead")       # "order" | "lead"

GRAPH_URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

anthropic_client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

app = FastAPI(title="WhatsApp Bot")


def _is_own_number(phone: str) -> bool:
    """
    Return True if *phone* normalizes to our business number or owner number.
    Used to prevent sheet writes or mutes for our own numbers.
    """
    from app.sheet import _normalize_phone
    normalized = _normalize_phone(phone)
    own = {_normalize_phone(n) for n in (OWNER_WHATSAPP, os.environ.get("BUSINESS_WA_ID", "")) if n}
    return normalized in own

# ---------------------------------------------------------------------------
# Order-flow assets (only used when FLOW_MODE=order)
# ---------------------------------------------------------------------------
MENU = load_menu()

ORDER_SYSTEM_PROMPT = f"""You are a friendly, efficient order-taking assistant for {MENU['shop_name']}, a food shop in Pakistan.

Rules:
- Speak simple English mixed with Roman Urdu, matching the customer's language.
- Only offer items from the menu below. Never invent items or prices.
- Keep every reply under 3 short lines. No long paragraphs.
- Flow: greet -> take items -> confirm quantities -> ask delivery address -> read back full order with total -> ask "Confirm karein? (yes/no)".
- When the customer confirms the final order, reply with the confirmation message AND on a new final line output exactly:
  ORDER_JSON: {{"items": [{{"name": ..., "qty": ..., "price": ...}}], "total": ..., "address": ...}}
- Never output ORDER_JSON before the customer explicitly confirms.
- If asked something unrelated to food orders, politely steer back to the menu.

MENU:
{menu_as_text(MENU)}
"""

# ---------------------------------------------------------------------------
# Lead-flow assets (only used when FLOW_MODE=lead)
# ---------------------------------------------------------------------------
if FLOW_MODE == "lead":
    from app.lead import (                                  # noqa: E402
        get_lead_meta, clear_lead_meta, has_active_lead,
        extract_lead_marker, extract_meta_from_turn,
        forward_lead_card, get_phase_interactive,
        apply_interactive_answer,
        classify_entry_intent, build_entry_response,
        INTENT_DEMO_FIRST,
    )
    from app.interactive import parse_interactive_reply     # noqa: E402
    from app.sheet import upsert_lead, parse_slot_datetime  # noqa: E402
    from app.sheet import (                                 # noqa: E402
        STATUS_NEW, STATUS_IN_PROGRESS,
        STATUS_DEMO_BOOKED, STATUS_NOT_RESPONDING,
    )


# ---------------------------------------------------------------------------
# Webhook verification (Meta calls GET once during setup)
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


# ---------------------------------------------------------------------------
# Incoming messages (Meta POSTs every event here)
# ---------------------------------------------------------------------------
@app.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()

    try:
        entry = body["entry"][0]["changes"][0]["value"]
    except (KeyError, IndexError):
        return {"status": "ignored"}

    if FLOW_MODE == "lead":
        return await _handle_lead_flow(entry)
    else:
        return await _handle_order_flow(entry)


# ---------------------------------------------------------------------------
# Lead flow
# ---------------------------------------------------------------------------
async def _handle_lead_flow(entry: dict) -> dict:
    from app.gate import check_gate  # always available in lead mode

    # Determine if sender has active session (needed by gate before we lock)
    pre_sender = ""
    try:
        pre_sender = entry["messages"][0]["from"]
    except (KeyError, IndexError):
        pass
    active = has_active_lead(pre_sender) if pre_sender else False

    gate = check_gate(entry, active_session=active)

    if not gate.allowed:
        # ── Sheet: human took over (outbound echo from business app) ─────
        # Only run for genuine outbound message echoes — never for status/receipt events.
        if not gate.is_status_event:
            try:
                contacts = entry.get("contacts", [])
                if contacts and "messages" in entry:
                    contact_ids = {c.get("wa_id") for c in contacts}
                    if pre_sender not in contact_ids:
                        customer_id = next(iter(contact_ids), None)
                        if customer_id and not _is_own_number(customer_id):
                            from app.sheet import _karachi_now
                            ts = _karachi_now().strftime("%Y-%m-%d %H:%M")
                            asyncio.create_task(upsert_lead(customer_id, {
                                "notes": f"Human took over {ts}",
                            }))
            except Exception:
                pass
        return {"status": "ignored"}

    sender = gate.sender

    async with get_sender_lock(sender):
        meta = get_lead_meta(sender)

        # Store lead source on first activation
        if gate.lead_source and "lead_source" not in meta:
            meta["lead_source"] = gate.lead_source
            # ── Sheet: activation event (skip own/owner numbers) ─────────
            if not _is_own_number(sender):
                profile_name = ""
                try:
                    contacts = entry.get("contacts", [])
                    if contacts:
                        profile_name = contacts[0].get("profile", {}).get("name", "")
                except Exception:
                    pass
                asyncio.create_task(upsert_lead(sender, {
                    "name":     profile_name,
                    "status":   STATUS_NEW,
                    "interest": gate.lead_source,
                }))
        if gate.referral:
            meta["referral_source_id"] = gate.referral.get("source_id", "")
            meta["referral_headline"] = gate.referral.get("headline", "")

        # ── Interactive reply (button tap / list selection) ───────────────
        if gate.message_type == "interactive":
            return await _handle_interactive_reply(sender, meta, entry)

        user_text = gate.text or ""
        log.info(f"lead: message from {sender} [{meta.get('phase')}]: {user_text!r}")

        # ── Non-text, non-interactive message (voice/image/sticker/video) ─
        if gate.message_type not in ("text",):
            lang = meta.get("lang", "ur")
            phase = meta.get("phase", "GREETING")
            is_first = (phase == "GREETING")
            if is_first:
                # First contact: full greeting + redirect note
                meta["phase"] = "BUSINESS_NAME"
                meta["entry_intent"] = "GENERIC_INFO"
                from app.lead import _media_first_text
                reply_text = _media_first_text(lang)
            else:
                # Mid-flow: one-line formal redirect + re-ask current question
                from app.lead import _t, build_reprompt
                _UNSUPPORTED = {
                    "ur": "Barah-e-karam apna jawab text mein likhein.",
                    "en": "Kindly respond in text so we may assist you.",
                }
                redirect = _t(_UNSUPPORTED, lang)
                re_ask = build_reprompt(phase, lang)
                reply_text = f"{redirect}\n\n{re_ask}"
            await send_whatsapp_message(sender, reply_text)
            return {"status": "ok"}

        # ── Capture custom slot if we're awaiting free-text after slot_other ─
        if meta.get("awaiting_custom_slot") and user_text:
            meta["demo_slot"] = user_text.strip()
            meta.pop("awaiting_custom_slot")
            meta["phase"] = "CONFIRMED"
            log.info(f"lead: custom slot captured: {meta['demo_slot']!r}")
            lang = meta.get("lang", "ur")
            from app.lead import _t, _CONFIRM_SLOT  # noqa: E402
            confirm_msg = _t(_CONFIRM_SLOT, lang).format(slot=meta["demo_slot"])
            await send_whatsapp_message(sender, confirm_msg)
            await forward_lead_card(sender, meta, OWNER_WHATSAPP, send_whatsapp_message)
            # Sheet: demo booked with custom slot
            demo_date, demo_time = parse_slot_datetime(meta["demo_slot"])
            asyncio.create_task(upsert_lead(sender, {
                "status":        STATUS_DEMO_BOOKED,
                "notes":         f"Demo confirmed via bot: {meta['demo_slot']}",
                "next_followup": demo_date or "",
                "demo_date":     demo_date or "",
                "demo_time":     demo_time or "",
                "business_name":  meta.get("business_name", ""),
                "business_type":  meta.get("business_type", ""),
                "current_system": meta.get("current_system", ""),
            }))
            clear_session(sender)
            clear_lead_meta(sender)
            return {"status": "ok"}

        # ── Entry intent: first message from a freshly-activated lead ─────
        if meta.get("phase") == "GREETING":
            return await _handle_entry_message(sender, meta, user_text)

        # ── Text at an interactive phase: try deterministic match first ───
        # This prevents the double-send bug (LLM reply + _maybe_send_interactive).
        # Interactive phases: BUSINESS_TYPE, LOCATIONS, CURRENT_SYSTEM, SCHEDULING.
        phase = meta.get("phase", "")
        lang = meta.get("lang", "ur")

        if phase == "BUSINESS_NAME":
            return await _handle_business_name_phase(sender, meta, user_text, lang)

        if phase == "BUSINESS_TYPE":
            return await _handle_text_at_interactive_phase(
                sender, meta, user_text, lang,
                match_fn=_match_business_type,
                advance_to="LOCATIONS",
                field_key="business_type",
            )

        if phase == "LOCATIONS":
            return await _handle_text_at_interactive_phase(
                sender, meta, user_text, lang,
                match_fn=_match_locations,
                advance_to="CURRENT_SYSTEM",
                field_key="locations",
            )

        if phase == "CURRENT_SYSTEM":
            return await _handle_text_at_interactive_phase(
                sender, meta, user_text, lang,
                match_fn=_match_current_system,
                advance_to="SCHEDULING",
                field_key="current_system",
            )

        # ── Normal LLM turn (BUSINESS_NAME and non-interactive phases) ───
        return await _handle_llm_turn(sender, meta, user_text, lang)


def _sheet_field_update(sender: str, meta: dict) -> None:
    """Fire-and-forget sheet update for mid-flow field captures."""
    if _is_own_number(sender):
        return
    fields = {}
    for key in ("business_name", "business_type", "current_system"):
        if meta.get(key):
            fields[key] = meta[key]
    if fields:
        asyncio.create_task(upsert_lead(sender, fields))


async def _handle_business_name_phase(
    sender: str, meta: dict, user_text: str, lang: str
) -> dict:
    """
    Deterministic handler for the BUSINESS_NAME phase.
    Never calls the LLM to judge validity of a name.

    - Detour question  → Claude one-liner + re-ask name question (one send)
    - 1-6 word input   → accept verbatim, advance to BUSINESS_TYPE,
                         send ack + business-type interactive list (one send)
    - Empty / >6 words → re-prompt (one send, phase unchanged)
    """
    from app.lead import (
        handle_business_name, _is_detour_question,
        extract_detour_done,
        _t, _Q_BUSINESS_NAME,
    )

    if _is_detour_question(user_text):
        detour_reply = await _generate_lead_reply(sender, user_text)
        _, clean_detour = extract_detour_done(detour_reply)
        re_ask = _t(_Q_BUSINESS_NAME, lang)
        combined = f"{clean_detour}\n\n{re_ask}" if clean_detour else re_ask
        await send_whatsapp_message(sender, combined)
        return {"status": "ok"}

    ack_text, accepted = handle_business_name(meta, user_text, lang)

    if accepted:
        # Name recorded, phase advanced to BUSINESS_TYPE — send the list widget
        _sheet_field_update(sender, meta)
        payload = get_phase_interactive("BUSINESS_TYPE", sender, lang)
        if payload:
            await send_whatsapp_message(sender, interactive_payload=payload)
        else:
            await send_whatsapp_message(sender, ack_text)
    else:
        # Re-prompt (includes > 6 word case)
        await send_whatsapp_message(sender, ack_text)

    return {"status": "ok"}


# ── Per-phase free-text match functions ──────────────────────────────────────
# Return (matched_value_for_meta, sheet_value) or (None, None) if no match.

def _match_business_type(text: str) -> tuple[str | None, str | None]:
    from app.lead import match_free_text_business_type, _BUSINESS_TYPE_LABELS
    btype_id = match_free_text_business_type(text)
    if btype_id:
        label = _BUSINESS_TYPE_LABELS[btype_id]
        return label, label
    return None, None


def _match_locations(text: str) -> tuple[str | None, str | None]:
    """Accept a digit word or Urdu/English number 1-20."""
    import re
    _URDU_EN_NUMBERS = {
        "ek": "1", "one": "1", "do": "2", "two": "2", "teen": "3", "three": "3",
        "char": "4", "four": "4", "paanch": "5", "five": "5", "chay": "6", "six": "6",
        "saat": "7", "seven": "7", "aath": "8", "eight": "8", "nau": "9", "nine": "9",
        "das": "10", "ten": "10",
    }
    lower = text.lower().strip()
    # Digit
    m = re.search(r"\b(\d+)\b", lower)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 20:
            val = str(n)
            return val, val
    # Word
    for word, digit in _URDU_EN_NUMBERS.items():
        if word in lower.split():
            return digit, digit
    # Accept "2-5", "5+" style
    if re.fullmatch(r"\d+[\-\+]\d*", lower.strip()):
        return lower.strip(), lower.strip()
    return None, None


def _match_current_system(text: str) -> tuple[str | None, str | None]:
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
    sender: str,
    meta: dict,
    user_text: str,
    lang: str,
    match_fn,
    advance_to: str,
    field_key: str,
) -> dict:
    """
    Handle free text at a phase that normally shows an interactive widget.

    1. Try match_fn(user_text) → if matched: record, advance, send ONE message
       (ack + next question as interactive widget or plain text).
    2. If it looks like a detour question → call Claude for one-liner, combine
       with re-asked question, send ONE message, phase unchanged.
    3. Otherwise → reprompt (increment budget); if budget exceeded → handoff.
    All branches send exactly ONE message.
    """
    from app.lead import (
        build_reprompt, build_handoff,
        increment_reprompt, reset_reprompts, MAX_REPROMPTS,
        extract_detour_done, _is_detour_question,
    )

    display_val, sheet_val = match_fn(user_text)

    if display_val is not None:
        # ── Matched: record, advance, send next interactive ──────────────
        meta[field_key] = sheet_val
        meta["phase"] = advance_to
        reset_reprompts(meta)
        _sheet_field_update(sender, meta)
        # Send next phase's interactive widget; if none, send its plain question
        payload = get_phase_interactive(advance_to, sender, lang)
        if payload:
            await send_whatsapp_message(sender, interactive_payload=payload)
        else:
            from app.lead import _t, _Q_BUSINESS_NAME
            await send_whatsapp_message(sender, _t(_Q_BUSINESS_NAME, lang))
        return {"status": "ok"}

    if _is_detour_question(user_text):
        # ── Detour: call Claude, combine answer + re-asked question ──────
        detour_reply = await _generate_lead_reply(sender, user_text)
        is_detour, clean_detour = extract_detour_done(detour_reply)
        from app.lead import _t, _Q_BUSINESS_TYPE, _Q_LOCATIONS, _Q_CURRENT_SYSTEM, _Q_BUSINESS_NAME
        _phase_q = {
            "BUSINESS_TYPE":  _Q_BUSINESS_TYPE,
            "LOCATIONS":      _Q_LOCATIONS,
            "CURRENT_SYSTEM": _Q_CURRENT_SYSTEM,
        }
        phase = meta.get("phase", "")
        re_ask = _t(_phase_q.get(phase, _Q_BUSINESS_NAME), lang)
        combined = f"{clean_detour}\n\n{re_ask}" if clean_detour else re_ask
        await send_whatsapp_message(sender, combined)
        return {"status": "ok"}

    # ── Unrecognised: reprompt or handoff ────────────────────────────────
    count = increment_reprompt(meta)
    if count > MAX_REPROMPTS:
        # Budget exhausted → handoff
        meta["phase"] = "STALLED"
        handoff_msg = build_handoff(lang)
        await send_whatsapp_message(sender, handoff_msg)
        await forward_lead_card(sender, meta, OWNER_WHATSAPP, send_whatsapp_message)
        clear_session(sender)
        clear_lead_meta(sender)
    else:
        # Still within budget → re-prompt
        phase = meta.get("phase", "")
        await send_whatsapp_message(sender, build_reprompt(phase, lang))
    return {"status": "ok"}


async def _handle_llm_turn(sender: str, meta: dict, user_text: str, lang: str) -> dict:
    """
    LLM turn for phases that don't have deterministic interactive matching
    (primarily BUSINESS_NAME, and SCHEDULING free-text).
    Handles DETOUR_DONE, LEAD_CONFIRMED, LEAD_STALLED markers.
    Sends exactly one message.
    """
    from app.lead import extract_detour_done

    reply = await _generate_lead_reply(sender, user_text)

    # ── Detour one-liner ─────────────────────────────────────────────────
    is_detour, clean_reply = extract_detour_done(reply)
    if is_detour:
        # Combine one-liner with the re-asked current question
        from app.lead import build_reprompt
        phase = meta.get("phase", "")
        re_ask = build_reprompt(phase, lang).split(". ", 1)[-1]  # strip "Maazrat..." prefix
        combined = f"{clean_reply}\n\n{re_ask}" if clean_reply else re_ask
        await send_whatsapp_message(sender, combined)
        return {"status": "ok"}

    extract_meta_from_turn(meta, user_text, reply)
    marker, clean_reply = extract_lead_marker(reply)

    if marker == "CONFIRMED":
        meta["phase"] = "CONFIRMED"
        await send_whatsapp_message(sender, clean_reply)
        await forward_lead_card(sender, meta, OWNER_WHATSAPP, send_whatsapp_message)
        demo_date, demo_time = parse_slot_datetime(meta.get("demo_slot", ""))
        asyncio.create_task(upsert_lead(sender, {
            "status":        STATUS_DEMO_BOOKED,
            "notes":         f"Demo confirmed via bot: {meta.get('demo_slot', '?')}",
            "next_followup": demo_date or "",
            "demo_date":     demo_date or "",
            "demo_time":     demo_time or "",
            "business_name": meta.get("business_name", ""),
            "business_type": meta.get("business_type", ""),
            "current_system": meta.get("current_system", ""),
        }))
        clear_session(sender)
        clear_lead_meta(sender)
        return {"status": "ok"}

    if marker == "STALLED":
        meta["phase"] = "STALLED"
        if meta.get("business_name"):
            await forward_lead_card(sender, meta, OWNER_WHATSAPP, send_whatsapp_message)
        tomorrow = (_karachi_now().date() + timedelta(days=1)).strftime("%Y-%m-%d")
        asyncio.create_task(upsert_lead(sender, {
            "status":        STATUS_NOT_RESPONDING,
            "notes":         f"Bot: stalled at {meta.get('phase', '?')}",
            "next_followup": tomorrow,
            "business_name": meta.get("business_name", ""),
            "business_type": meta.get("business_type", ""),
            "current_system": meta.get("current_system", ""),
        }))
        clear_session(sender)
        clear_lead_meta(sender)
        return {"status": "ok"}

    _sheet_field_update(sender, meta)
    # For BUSINESS_NAME phase, after recording the name, send the BUSINESS_TYPE
    # interactive list as ONE combined response (no separate LLM text).
    new_phase = meta.get("phase", "")
    interactive_payload = get_phase_interactive(new_phase, sender, lang)
    if interactive_payload:
        # Phase has an interactive widget — send it instead of the LLM text.
        # The LLM text is discarded to enforce one-send-per-turn.
        await send_whatsapp_message(sender, interactive_payload=interactive_payload)
    else:
        await send_whatsapp_message(sender, clean_reply)
    return {"status": "ok"}


def _karachi_now():
    """Re-export for use in main without importing ZoneInfo directly."""
    from app.sheet import _karachi_now as _kn
    return _kn()


async def _handle_entry_message(sender: str, meta: dict, user_text: str) -> dict:
    """
    Handle the very first message from a freshly-activated lead (phase == GREETING).
    Classifies intent deterministically and responds without an LLM call.
    """
    intent = classify_entry_intent(user_text)
    meta["entry_intent"] = intent
    reply_text, next_phase = build_entry_response(intent)
    meta["phase"] = next_phase

    log.info(f"lead: entry intent={intent} from {sender!r}, → phase={next_phase}")

    await send_whatsapp_message(sender, reply_text)

    # Sheet: first reply sent → In Progress (skip own/owner numbers)
    if not _is_own_number(sender):
        asyncio.create_task(upsert_lead(sender, {
            "status":   STATUS_IN_PROGRESS,
            "interest": intent,
        }))

    # DEMO_FIRST: immediately follow up with the scheduling interactive widget
    if intent == INTENT_DEMO_FIRST:
        await _maybe_send_interactive(sender, meta)

    return {"status": "ok"}


async def _handle_interactive_reply(sender: str, meta: dict, entry: dict) -> dict:
    """
    Handle an inbound interactive reply (button tap or list selection).
    Applies the answer deterministically without an LLM call when recognised.
    """
    message = entry["messages"][0]
    reply_id, reply_title = parse_interactive_reply(message)

    if reply_id is None:
        # Malformed — ignore gracefully
        log.warning(f"lead: malformed interactive payload from {sender}")
        return {"status": "ignored"}

    handled, follow_up = apply_interactive_answer(meta, reply_id, reply_title)

    if not handled:
        # Unknown id for this phase — treat as free text through LLM
        user_text = reply_title or reply_id
        reply = await _generate_lead_reply(sender, user_text)
        extract_meta_from_turn(meta, user_text, reply)
        marker, clean_reply = extract_lead_marker(reply)
        if marker == "CONFIRMED":
            meta["phase"] = "CONFIRMED"
            await send_whatsapp_message(sender, clean_reply)
            await forward_lead_card(sender, meta, OWNER_WHATSAPP, send_whatsapp_message)
            clear_session(sender)
            clear_lead_meta(sender)
        else:
            await send_whatsapp_message(sender, clean_reply)
            await _maybe_send_interactive(sender, meta)
        return {"status": "ok"}

    # Deterministic path handled
    if follow_up:
        # slot_other: send the "what time?" question as plain text
        await send_whatsapp_message(sender, follow_up)
        return {"status": "ok"}

    # Phase advanced — check if CONFIRMED now (slot_1 / slot_2 direct confirm)
    if meta.get("phase") == "CONFIRMED":
        lang = meta.get("lang", "ur")
        from app.lead import _t, _CONFIRM_SLOT  # noqa: E402
        confirm_msg = _t(_CONFIRM_SLOT, lang).format(slot=meta.get("demo_slot", ""))
        await send_whatsapp_message(sender, confirm_msg)
        await forward_lead_card(sender, meta, OWNER_WHATSAPP, send_whatsapp_message)
        # Sheet: demo booked via interactive button
        demo_date, demo_time = parse_slot_datetime(meta.get("demo_slot", ""))
        asyncio.create_task(upsert_lead(sender, {
            "status":        STATUS_DEMO_BOOKED,
            "notes":         f"Demo confirmed via bot: {meta.get('demo_slot', '?')}",
            "next_followup": demo_date or "",
            "demo_date":     demo_date or "",
            "demo_time":     demo_time or "",
            "business_name":  meta.get("business_name", ""),
            "business_type":  meta.get("business_type", ""),
            "current_system": meta.get("current_system", ""),
        }))
        clear_session(sender)
        clear_lead_meta(sender)
        return {"status": "ok"}

    # Otherwise send next phase's interactive widget (or LLM prompt for BUSINESS_NAME)
    await _maybe_send_interactive(sender, meta)
    return {"status": "ok"}


async def _maybe_send_interactive(sender: str, meta: dict) -> None:
    """
    If the current phase has an interactive widget defined, send it.
    Uses send_whatsapp_message with an interactive payload.
    """
    phase = meta.get("phase", "GREETING")
    payload = get_phase_interactive(phase, sender)
    if payload:
        await send_whatsapp_message(sender, interactive_payload=payload)


async def _generate_lead_reply(sender: str, user_text: str) -> str:
    from app.lead import SYSTEM_PROMPT_LEAD  # available in lead mode
    history = get_session(sender)
    history.append({"role": "user", "content": user_text})

    try:
        response = await anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=400,
            system=SYSTEM_PROMPT_LEAD,
            messages=history[-20:],
        )
        reply = response.content[0].text
    except Exception as e:
        log.error(f"Claude API error (lead): {e}")
        return "Sorry, thora sa masla aa gaya. Thodi der baad dobara try karein 🙏"

    history.append({"role": "assistant", "content": reply})
    save_session(sender, history)
    return reply


# ---------------------------------------------------------------------------
# Order flow (unchanged from v1)
# ---------------------------------------------------------------------------
async def _handle_order_flow(entry: dict) -> dict:
    # Ignore status updates (delivered/read receipts)
    if "messages" not in entry:
        return {"status": "ignored"}

    message = entry["messages"][0]
    sender = message["from"]

    # Only handle text for v1; politely handle everything else
    if message.get("type") != "text":
        await send_whatsapp_message(sender, "Please send your order as a text message 🙂")
        return {"status": "ok"}

    user_text = message["text"]["body"].strip()
    log.info(f"order: incoming from {sender}: {user_text}")

    # Simple reset command
    if user_text.lower() in ("reset", "restart", "naya order"):
        clear_session(sender)
        await send_whatsapp_message(
            sender,
            "Order reset. Kya order karna chahenge? Type 'menu' to see the menu.",
        )
        return {"status": "ok"}

    async with get_sender_lock(sender):
        reply = await _generate_order_reply(sender, user_text)

        order, clean_reply = detect_confirmed_order(reply)
        if order:
            await forward_order_to_owner(order, sender, OWNER_WHATSAPP, send_whatsapp_message)
            clear_session(sender)

    await send_whatsapp_message(sender, clean_reply)
    return {"status": "ok"}


async def _generate_order_reply(sender: str, user_text: str) -> str:
    history = get_session(sender)
    history.append({"role": "user", "content": user_text})

    try:
        response = await anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=400,
            system=ORDER_SYSTEM_PROMPT,
            messages=history[-20:],
        )
        reply = response.content[0].text
    except Exception as e:
        log.error(f"Claude API error (order): {e}")
        return "Sorry, thora sa issue aa gaya. Please dobara message karein."

    history.append({"role": "assistant", "content": reply})
    save_session(sender, history)
    return reply


# ---------------------------------------------------------------------------
# Outgoing messages via Meta Graph API
# ---------------------------------------------------------------------------
async def send_whatsapp_message(
    to: str,
    text: str = "",
    interactive_payload: dict = None,
) -> bool:
    """
    Send a WhatsApp message.

    Pass *interactive_payload* (a full message dict from build_buttons /
    build_list) to send an interactive message instead of plain text.
    When interactive_payload is supplied, *text* is ignored.
    Returns True on success, False on HTTP error.
    """
    if interactive_payload is not None:
        payload = interactive_payload
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(GRAPH_URL, headers=headers, json=payload)
        if r.status_code >= 400:
            log.error(f"Send failed {r.status_code}: {r.text}")
            return False
    return True


@app.get("/")
async def health():
    return {"status": "running", "mode": FLOW_MODE}
