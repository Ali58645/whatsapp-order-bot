"""Instagram Messaging adapter (activates when Meta permissions + tenant config ready)."""

from __future__ import annotations

import logging

from app.channels.interactive_builder import render_outbound
from app.channels.types import NormalizedMessage, OutboundMessage

log = logging.getLogger("orderbot.channels.instagram")

GRAPH = "https://graph.facebook.com/v21.0"


def detect_instagram_payload(body: dict) -> bool:
    """IG webhooks use object=instagram and messaging array."""
    if body.get("object") == "instagram":
        return True
    try:
        entry = body["entry"][0]
        if entry.get("messaging"):
            return True
        change = entry.get("changes", [{}])[0]
        if change.get("field") == "messages" and "instagram" in str(body.get("object", "")):
            return True
    except (KeyError, IndexError, TypeError):
        pass
    return False


def parse_webhook(body: dict) -> list[NormalizedMessage]:
    """Parse Instagram messaging webhook."""
    out: list[NormalizedMessage] = []
    entries = body.get("entry") or []
    for entry in entries:
        account_id = str(entry.get("id", ""))
        for event in entry.get("messaging") or []:
            nm = _parse_messaging_event(event, account_id)
            if nm:
                out.append(nm)
    return out


def _parse_messaging_event(event: dict, account_id: str) -> NormalizedMessage | None:
    if event.get("message", {}).get("is_echo"):
        return None
    sender = (event.get("sender") or {}).get("id", "")
    if not sender:
        return None
    message = event.get("message") or {}
    text = message.get("text")
    if text is not None:
        text = str(text).strip()

    interactive_reply = None
    quick = message.get("quick_reply")
    if quick:
        interactive_reply = (str(quick.get("payload", "")), str(quick.get("payload", "")))

    postback = event.get("postback")
    if postback:
        interactive_reply = (
            str(postback.get("payload", "")),
            str(postback.get("title", "")),
        )

    attachments = message.get("attachments")
    media = None
    msg_type = "text"
    if attachments:
        msg_type = "media"
        media = {"attachments": attachments}

    referral = None
    if message.get("referral"):
        referral = message["referral"]

    return NormalizedMessage(
        channel="instagram",
        account_id=account_id,
        sender_id=sender,
        text=text,
        message_type=msg_type if not interactive_reply else "interactive",
        media=media,
        interactive_reply=interactive_reply,
        referral=referral,
    )


async def send_reply(
    msg: OutboundMessage,
    *,
    access_token: str,
    graph_account_id: str,
) -> bool:
    """Send via IG messaging API (graph_account_id = IG user id)."""
    import httpx

    if not access_token:
        log.error("instagram: no access token for tenant")
        return False
    payload = render_outbound(msg, to=msg.recipient_id)
    url = f"{GRAPH}/{graph_account_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, headers=headers, json=payload)
            if r.status_code >= 400:
                log.error("instagram: send failed %s: %s", r.status_code, r.text)
                return False
        return True
    except Exception as exc:
        log.error("instagram: send failed: %s", exc)
        return False
