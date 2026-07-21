"""Parse a single WhatsApp webhook value dict (no outer body wrapper)."""

from __future__ import annotations

import os

from app.channels.types import NormalizedMessage


def entry_value_to_normalized(value: dict, account_id: str = "") -> NormalizedMessage | None:
    """Build NormalizedMessage from changes[].value — used by gate wrapper."""
    aid = account_id or (value.get("metadata") or {}).get("phone_number_id", "")
    if not aid:
        aid = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "default")

    if "statuses" in value and "messages" not in value:
        return NormalizedMessage(
            channel="whatsapp",
            account_id=aid,
            sender_id="",
            is_status_event=True,
            raw_entry=value,
        )

    if "messages" not in value:
        return None

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

    return NormalizedMessage(
        channel="whatsapp",
        account_id=aid,
        sender_id=sender,
        text=text,
        message_type=msg_type,
        interactive_reply=interactive_reply,
        referral=message.get("referral"),
        contacts=list(value.get("contacts") or []),
        raw_entry=value,
        raw_message=message,
    )
