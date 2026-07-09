"""
WhatsApp Bot — FastAPI + Meta Cloud API + Claude Haiku
Deploy target: Railway. Set env vars from .env.example before running.

FLOW_MODE=order  → original food-order bot (no gate)
FLOW_MODE=lead   → Bahi POS lead qualification with coexistence gate (default)
"""

import os
import logging
import httpx
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
    )
    from app.interactive import parse_interactive_reply     # noqa: E402


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
        return {"status": "ignored"}

    sender = gate.sender

    async with get_sender_lock(sender):
        meta = get_lead_meta(sender)

        # Store lead source on first activation
        if gate.lead_source and "lead_source" not in meta:
            meta["lead_source"] = gate.lead_source
        if gate.referral:
            meta["referral_source_id"] = gate.referral.get("source_id", "")
            meta["referral_headline"] = gate.referral.get("headline", "")

        # ── Interactive reply (button tap / list selection) ───────────────
        if gate.message_type == "interactive":
            return await _handle_interactive_reply(sender, meta, entry)

        user_text = gate.text or ""
        log.info(f"lead: message from {sender} [{meta.get('phase')}]: {user_text!r}")

        # Non-text, non-interactive message — gentle redirect
        if gate.message_type not in ("text",):
            await send_whatsapp_message(
                sender,
                "Please apna message text mein likhein — main samajh sakunga 🙂",
            )
            return {"status": "ok"}

        # ── Capture custom slot if we're awaiting free-text after slot_other ─
        if meta.get("awaiting_custom_slot") and user_text:
            meta["demo_slot"] = user_text.strip()
            meta.pop("awaiting_custom_slot")
            meta["phase"] = "CONFIRMED"
            log.info(f"lead: custom slot captured: {meta['demo_slot']!r}")
            confirm_msg = (
                f"Perfect! {meta['demo_slot']} — hamari team aap se is number par "
                f"contact karegi. Shukriya! 🙏"
            )
            await send_whatsapp_message(sender, confirm_msg)
            await forward_lead_card(sender, meta, OWNER_WHATSAPP, send_whatsapp_message)
            clear_session(sender)
            clear_lead_meta(sender)
            return {"status": "ok"}

        # ── Normal LLM turn ───────────────────────────────────────────────
        reply = await _generate_lead_reply(sender, user_text)
        extract_meta_from_turn(meta, user_text, reply)

        marker, clean_reply = extract_lead_marker(reply)

        if marker == "CONFIRMED":
            meta["phase"] = "CONFIRMED"
            await send_whatsapp_message(sender, clean_reply)
            await forward_lead_card(sender, meta, OWNER_WHATSAPP, send_whatsapp_message)
            clear_session(sender)
            clear_lead_meta(sender)
            return {"status": "ok"}

        if marker == "STALLED":
            meta["phase"] = "STALLED"
            if meta.get("business_name") or meta.get("phase") not in ("GREETING", "BUSINESS_NAME"):
                await forward_lead_card(sender, meta, OWNER_WHATSAPP, send_whatsapp_message)
            clear_session(sender)
            clear_lead_meta(sender)
            return {"status": "ok"}

        # Send the LLM reply, then check if the *new* phase has an interactive widget
        await send_whatsapp_message(sender, clean_reply)
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
        confirm_msg = (
            f"Shukriya! {meta.get('demo_slot', '')} — hamari team aap se is "
            f"number par contact karegi. 🙏"
        )
        await send_whatsapp_message(sender, confirm_msg)
        await forward_lead_card(sender, meta, OWNER_WHATSAPP, send_whatsapp_message)
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
