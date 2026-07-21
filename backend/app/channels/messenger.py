"""Facebook Messenger adapter."""

from __future__ import annotations

import logging

from app.channels.instagram import _parse_messaging_event, send_reply as ig_send_reply
from app.channels.types import NormalizedMessage, OutboundMessage

log = logging.getLogger("orderbot.channels.messenger")


def detect_messenger_payload(body: dict) -> bool:
    return body.get("object") == "page"


def parse_webhook(body: dict) -> list[NormalizedMessage]:
    out: list[NormalizedMessage] = []
    for entry in body.get("entry") or []:
        account_id = str(entry.get("id", ""))
        for event in entry.get("messaging") or []:
            nm = _parse_messaging_event(event, account_id)
            if nm:
                nm.channel = "messenger"
                out.append(nm)
    return out


async def send_reply(
    msg: OutboundMessage,
    *,
    access_token: str,
    graph_account_id: str,
) -> bool:
    """Send via Page messages API."""
    msg_m = OutboundMessage(
        channel="messenger",
        recipient_id=msg.recipient_id,
        text=msg.text,
        choices=msg.choices,
        choice_style=msg.choice_style,
        list_button_label=msg.list_button_label,
        provider_payload=msg.provider_payload,
    )
    return await ig_send_reply(
        msg_m, access_token=access_token, graph_account_id=graph_account_id
    )
