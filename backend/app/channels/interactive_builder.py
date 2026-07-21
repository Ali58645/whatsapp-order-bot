"""Render channel-neutral outbound messages to provider-specific payloads."""

from __future__ import annotations

from app.channels.types import InteractiveChoice, OutboundMessage

IG_QUICK_REPLY_MAX = 13
IG_TITLE_MAX = 20


def render_outbound(msg: OutboundMessage, *, to: str) -> dict:
    """Build provider API body for send_reply."""
    if msg.provider_payload is not None:
        payload = dict(msg.provider_payload)
        payload["to"] = to
        return payload

    if msg.channel == "whatsapp":
        return _render_whatsapp(msg, to)
    if msg.channel == "instagram":
        return _render_instagram(msg, to)
    if msg.channel == "messenger":
        return _render_messenger(msg, to)
    raise ValueError(f"Unknown channel: {msg.channel}")


def _render_whatsapp(msg: OutboundMessage, to: str) -> dict:
    from app.interactive import build_buttons, build_list

    if not msg.choices:
        return {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": msg.text},
        }
    if msg.choice_style == "list":
        rows = [
            (c.id, c.title, c.description or c.title) for c in msg.choices[:10]
        ]
        return build_list(to, msg.text, msg.list_button_label, rows)
    buttons = [(c.id, c.title) for c in msg.choices[:3]]
    return build_buttons(to, msg.text, buttons)


def _render_instagram(msg: OutboundMessage, to: str) -> dict:
    """IG DM quick replies (max 13, title 20 chars)."""
    if not msg.choices:
        return {"recipient": {"id": to}, "message": {"text": msg.text}}
    quick_replies = [
        {
            "content_type": "text",
            "title": _trim(c.title, IG_TITLE_MAX),
            "payload": c.id,
        }
        for c in msg.choices[:IG_QUICK_REPLY_MAX]
    ]
    return {
        "recipient": {"id": to},
        "message": {"text": msg.text, "quick_replies": quick_replies},
    }


def _render_messenger(msg: OutboundMessage, to: str) -> dict:
    """Messenger quick replies (max 13)."""
    if not msg.choices:
        return {"recipient": {"id": to}, "message": {"text": msg.text}}
    quick_replies = [
        {
            "content_type": "text",
            "title": _trim(c.title, IG_TITLE_MAX),
            "payload": c.id,
        }
        for c in msg.choices[:IG_QUICK_REPLY_MAX]
    ]
    return {
        "recipient": {"id": to},
        "messaging_type": "RESPONSE",
        "message": {"text": msg.text, "quick_replies": quick_replies},
    }


def choices_from_whatsapp_payload(payload: dict) -> list[InteractiveChoice]:
    """Extract choices from a WhatsApp interactive payload for cross-channel reuse."""
    interactive = payload.get("interactive") or {}
    itype = interactive.get("type")
    if itype == "button":
        out = []
        for btn in (interactive.get("action") or {}).get("buttons") or []:
            reply = btn.get("reply") or {}
            out.append(InteractiveChoice(id=reply.get("id", ""), title=reply.get("title", "")))
        return out
    if itype == "list":
        out = []
        for section in (interactive.get("action") or {}).get("sections") or []:
            for row in section.get("rows") or []:
                out.append(
                    InteractiveChoice(
                        id=row.get("id", ""),
                        title=row.get("title", ""),
                        description=row.get("description", ""),
                    )
                )
        return out
    return []


def _trim(s: str, max_len: int) -> str:
    return s if len(s) <= max_len else s[:max_len]
