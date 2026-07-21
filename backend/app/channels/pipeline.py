"""Shared inbound webhook pipeline — channel adapters → tenant resolve → brain."""

from __future__ import annotations

import asyncio
import logging

from app.channels.router import parse_inbound_webhook
from app.channels.types import NormalizedMessage

log = logging.getLogger("orderbot.pipeline")


def synthetic_entry(nm: NormalizedMessage) -> dict:
    """Build a minimal WhatsApp-shaped entry for handlers when raw_entry absent."""
    msg: dict = {"from": nm.sender_id, "type": nm.message_type}
    if nm.text is not None:
        msg["type"] = "text"
        msg["text"] = {"body": nm.text}
    if nm.interactive_reply:
        rid, title = nm.interactive_reply
        msg["type"] = "interactive"
        msg["interactive"] = {
            "type": "button_reply",
            "button_reply": {"id": rid, "title": title},
        }
    if nm.referral:
        msg["referral"] = nm.referral
    if nm.media:
        for k, v in nm.media.items():
            msg["type"] = k if k != "attachments" else nm.message_type
            msg[k] = v
    return {"messages": [msg], "contacts": nm.contacts or []}


def entry_for_handlers(nm: NormalizedMessage) -> dict:
    if nm.raw_entry:
        return nm.raw_entry
    return synthetic_entry(nm)


async def process_webhook_body(body: dict) -> dict:
    """
    Parse webhook, route each inbound message through tenant + flow handlers.
    Unknown channel → ignored (200).
    """
    from app.main import _handle_lead_flow, _handle_order_flow
    from app.tenant_resolver import resolve_tenant_for_channel

    channel, messages = parse_inbound_webhook(body)
    if channel is None or not messages:
        return {"status": "ignored"}

    result: dict = {"status": "ignored"}
    for nm in messages:
        if nm.is_status_event:
            continue

        tenant = await resolve_tenant_for_channel(nm.channel, nm.account_id)
        if tenant is None:
            log.info(
                "pipeline: no tenant for channel=%s account=%s",
                nm.channel,
                nm.account_id,
            )
            continue

        if not tenant.is_channel_live(nm.channel):
            log.info(
                "pipeline: tenant %s channel %s not live — no reply",
                tenant.phone_number_id,
                nm.channel,
            )
            try:
                from app.db.store import EventStore

                asyncio.create_task(
                    EventStore.append(
                        tenant,
                        "inbound_paused",
                        {
                            "status": tenant.channel_status(nm.channel),
                            "channel": nm.channel,
                            "account_id": nm.account_id,
                        },
                        wa_id=nm.sender_id or None,
                    )
                )
            except Exception:
                pass
            result = {"status": "ok", "bot": "paused"}
            continue

        from app.owner_tools import away_message, is_within_business_hours

        if not is_within_business_hours(tenant):
            entry = entry_for_handlers(nm)
            sender = nm.sender_id or ""
            if sender and tenant.flow_mode == "lead":
                from app.main import send_whatsapp_message

                await send_whatsapp_message(sender, away_message(tenant), tenant=tenant)
            result = {"status": "ok", "bot": "away"}
            continue

        entry = entry_for_handlers(nm)
        if tenant.flow_mode == "lead":
            result = await _handle_lead_flow(entry, tenant)
        else:
            result = await _handle_order_flow(entry, tenant)
    return result
