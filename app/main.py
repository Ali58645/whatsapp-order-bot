"""
WhatsApp Order Bot — FastAPI + Meta Cloud API + Claude Haiku
Deploy target: Railway. Set env vars from .env.example before running.
"""

import os
import json
import logging
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from anthropic import AsyncAnthropic

from app.menu import load_menu, menu_as_text
from app.sessions import get_session, save_session, clear_session
from app.orders import detect_confirmed_order, forward_order_to_owner

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("orderbot")

# ---------------------------------------------------------------------------
# Config (all via environment variables — never hardcode)
# ---------------------------------------------------------------------------
VERIFY_TOKEN = os.environ["WHATSAPP_VERIFY_TOKEN"]          # you invent this string
WHATSAPP_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]        # permanent system-user token
PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]    # from Meta dashboard
OWNER_WHATSAPP = os.environ.get("OWNER_WHATSAPP", "")       # shop owner's number for order slips
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

GRAPH_URL = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"

anthropic_client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

app = FastAPI(title="WhatsApp Order Bot")

MENU = load_menu()

SYSTEM_PROMPT = f"""You are a friendly, efficient order-taking assistant for {MENU['shop_name']}, a food shop in Pakistan.

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
# Webhook verification (Meta calls GET once during setup)
# ---------------------------------------------------------------------------
@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
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

    # Ignore status updates (delivered/read receipts)
    if "messages" not in entry:
        return {"status": "ignored"}

    message = entry["messages"][0]
    sender = message["from"]  # customer's WhatsApp number

    # Only handle text for v1; politely handle everything else
    if message.get("type") != "text":
        await send_whatsapp_message(sender, "Please send your order as a text message 🙂")
        return {"status": "ok"}

    user_text = message["text"]["body"].strip()
    log.info(f"Incoming from {sender}: {user_text}")

    # Simple reset command for testing
    if user_text.lower() in ("reset", "restart", "naya order"):
        clear_session(sender)
        await send_whatsapp_message(sender, "Order reset. Kya order karna chahenge? Type 'menu' to see the menu.")
        return {"status": "ok"}

    reply = await generate_reply(sender, user_text)

    # If Claude emitted a confirmed order, forward slip to owner and strip the JSON line
    order, clean_reply = detect_confirmed_order(reply)
    if order:
        await forward_order_to_owner(order, sender, OWNER_WHATSAPP, send_whatsapp_message)
        clear_session(sender)

    await send_whatsapp_message(sender, clean_reply)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Claude conversation
# ---------------------------------------------------------------------------
async def generate_reply(sender: str, user_text: str) -> str:
    history = get_session(sender)
    history.append({"role": "user", "content": user_text})

    try:
        response = await anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=history[-20:],  # cap context to last 20 turns
        )
        reply = response.content[0].text
    except Exception as e:
        log.error(f"Claude API error: {e}")
        return "Sorry, thora sa issue aa gaya. Please dobara message karein."

    history.append({"role": "assistant", "content": reply})
    save_session(sender, history)
    return reply


# ---------------------------------------------------------------------------
# Outgoing messages via Meta Graph API
# ---------------------------------------------------------------------------
async def send_whatsapp_message(to: str, text: str) -> None:
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


@app.get("/")
async def health():
    return {"status": "running", "shop": MENU["shop_name"]}
