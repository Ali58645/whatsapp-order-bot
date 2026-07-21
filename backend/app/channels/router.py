"""Webhook channel detection and inbound parsing."""

from __future__ import annotations

import logging

from app.channels import instagram as ig_adapter
from app.channels import messenger as ms_adapter
from app.channels import whatsapp as wa_adapter
from app.channels.types import ChannelType, NormalizedMessage

log = logging.getLogger("orderbot.channels.router")


def detect_channel(body: dict) -> ChannelType | None:
    """Detect channel from webhook payload shape."""
    obj = str(body.get("object") or "")
    if obj == "page":
        return "messenger"
    if obj == "instagram":
        return "instagram"
    try:
        entry = body["entry"][0]
        if "changes" in entry:
            return "whatsapp"
        if entry.get("messaging") and obj in ("", "page"):
            return "messenger"
    except (KeyError, IndexError, TypeError):
        pass
    return None


def parse_inbound_webhook(body: dict) -> tuple[ChannelType | None, list[NormalizedMessage]]:
    """Route to adapter parse_webhook; unknown → (None, [])."""
    channel = detect_channel(body)
    if channel is None:
        log.debug("router: unknown webhook shape — ignored")
        return None, []
    if channel == "whatsapp":
        return channel, wa_adapter.parse_webhook(body)
    if channel == "instagram":
        return channel, ig_adapter.parse_webhook(body)
    if channel == "messenger":
        return channel, ms_adapter.parse_webhook(body)
    return None, []


def route_account_id(nm: NormalizedMessage) -> str:
    return nm.account_id
