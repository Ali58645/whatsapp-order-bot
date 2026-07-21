"""WhatsApp Cloud API adapter — byte-identical to pre-refactor behavior."""

from __future__ import annotations

import logging
import os
from typing import Any

from app.channels.interactive_builder import render_outbound
from app.channels.types import NormalizedMessage, OutboundMessage

log = logging.getLogger("orderbot.channels.whatsapp")

WHATSAPP_TOKEN_ENV = "WHATSAPP_ACCESS_TOKEN"


def detect_whatsapp_payload(body: dict) -> bool:
    """True if body looks like a WhatsApp Cloud API webhook."""
    try:
        entry = body["entry"][0]
        if "changes" in entry:
            return "whatsapp" in str(entry.get("changes", [{}])[0].get("field", "")).lower() or True
        return False
    except (KeyError, IndexError, TypeError):
        return False


def parse_webhook(body: dict) -> list[NormalizedMessage]:
    """
    Parse WhatsApp webhook body into normalized message(s).
    Returns empty list for status-only or unparseable payloads.
    """
    try:
        entry = body["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
    except (KeyError, IndexError, TypeError):
        return []

    account_id = (value.get("metadata") or {}).get("phone_number_id", "")
    if not account_id:
        account_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "default")

    # Status receipts — normalized as status event (gate drops)
    if "statuses" in value and "messages" not in value:
        return [
            NormalizedMessage(
                channel="whatsapp",
                account_id=account_id,
                sender_id="",
                is_status_event=True,
                raw_entry=value,
            )
        ]

    if "messages" not in value:
        return []

    message = value["messages"][0]
    sender = message.get("from", "")
    msg_type = message.get("type", "text")
    text = None
    if msg_type == "text":
        text = (message.get("text") or {}).get("body", "").strip()

    interactive_reply = None
    if msg_type == "interactive":
        from app.interactive import parse_interactive_reply

        rid, rtitle = parse_interactive_reply(message)
        if rid:
            interactive_reply = (rid, rtitle or "")

    return [
        NormalizedMessage(
            channel="whatsapp",
            account_id=account_id,
            sender_id=sender,
            text=text,
            message_type=msg_type,
            media=_extract_media(message) if msg_type not in ("text", "interactive") else None,
            interactive_reply=interactive_reply,
            referral=message.get("referral"),
            contacts=list(value.get("contacts") or []),
            raw_entry=value,
            raw_message=message,
        )
    ]


def _extract_media(message: dict) -> dict[str, Any] | None:
    mtype = message.get("type")
    if mtype and mtype in message:
        return {mtype: message.get(mtype)}
    return None


async def send_reply(
    msg: OutboundMessage,
    *,
    access_token: str | None = None,
    graph_account_id: str,
) -> bool:
    """POST to Graph API messages edge (same as legacy send_whatsapp_message)."""
    import httpx

    token = access_token or os.environ.get(WHATSAPP_TOKEN_ENV, "")
    if not token:
        log.error("whatsapp: WHATSAPP_ACCESS_TOKEN not configured")
        return False

    payload = render_outbound(msg, to=msg.recipient_id)
    graph_url = f"https://graph.facebook.com/v21.0/{graph_account_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(graph_url, headers=headers, json=payload)
            if r.status_code >= 400:
                log.error("whatsapp: send failed %s: %s", r.status_code, r.text)
                return False
        return True
    except Exception as exc:
        log.error("whatsapp: send failed (network): %s", exc)
        return False
