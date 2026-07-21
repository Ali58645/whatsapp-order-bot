"""Multi-channel adapters — WhatsApp, Instagram, Messenger."""

from app.channels.types import (
    CHANNELS,
    ChannelType,
    InteractiveChoice,
    NormalizedMessage,
    OutboundMessage,
)
from app.channels.router import detect_channel, parse_inbound_webhook, route_account_id

__all__ = [
    "CHANNELS",
    "ChannelType",
    "InteractiveChoice",
    "NormalizedMessage",
    "OutboundMessage",
    "detect_channel",
    "parse_inbound_webhook",
    "route_account_id",
]
