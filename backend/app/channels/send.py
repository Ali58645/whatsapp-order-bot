"""Unified outbound send — picks adapter from channel + tenant config."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.channels.types import ChannelType, OutboundMessage

if TYPE_CHECKING:
    from app.tenants import Tenant

log = logging.getLogger("orderbot.channels.send")


async def send_channel_message(
    tenant: "Tenant",
    channel: ChannelType,
    recipient_id: str,
    *,
    text: str = "",
    provider_payload: dict | None = None,
    outbound: OutboundMessage | None = None,
) -> bool:
    """Send via the correct channel adapter."""
    from app.tenants import channel_config

    cfg = channel_config(tenant, channel)
    if not cfg.get("connected") and channel != "whatsapp":
        log.warning("channel %s not connected for tenant %s", channel, tenant.phone_number_id)
        return False

    if outbound is None:
        outbound = OutboundMessage(
            channel=channel,
            recipient_id=recipient_id,
            text=text,
            provider_payload=provider_payload,
        )
    else:
        outbound = OutboundMessage(
            channel=channel,
            recipient_id=recipient_id,
            text=outbound.text or text,
            choices=outbound.choices,
            choice_style=outbound.choice_style,
            list_button_label=outbound.list_button_label,
            provider_payload=outbound.provider_payload or provider_payload,
        )

    if channel == "whatsapp":
        from app.channels import whatsapp as wa

        account_id = cfg.get("account_id") or tenant.phone_number_id
        token = cfg.get("access_token")
        return await wa.send_reply(
            outbound,
            access_token=token,
            graph_account_id=account_id,
        )
    if channel == "instagram":
        from app.channels import instagram as ig

        return await ig.send_reply(
            outbound,
            access_token=cfg.get("access_token", ""),
            graph_account_id=cfg.get("account_id", ""),
        )
    if channel == "messenger":
        from app.channels import messenger as ms

        return await ms.send_reply(
            outbound,
            access_token=cfg.get("access_token", ""),
            graph_account_id=cfg.get("account_id", ""),
        )
    return False
