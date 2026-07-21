"""Channel-neutral message model consumed by gate / flow / lead / sheet."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ChannelType = Literal["whatsapp", "instagram", "messenger"]
CHANNELS: tuple[ChannelType, ...] = ("whatsapp", "instagram", "messenger")


@dataclass
class InteractiveChoice:
    """One selectable option (button, list row, or quick reply)."""

    id: str
    title: str
    description: str = ""


@dataclass
class NormalizedMessage:
    """
    Inbound message after channel adapter parsing.

    account_id: channel routing key (WA phone_number_id, IG ig_id, FB page_id).
    sender_id: end-user id on that channel.
    """

    channel: ChannelType
    account_id: str
    sender_id: str
    text: str | None = None
    message_type: str = "text"
    media: dict[str, Any] | None = None
    interactive_reply: tuple[str, str] | None = None  # (id, title)
    referral: dict[str, Any] | None = None
    contacts: list[dict[str, Any]] = field(default_factory=list)
    is_status_event: bool = False
    # WhatsApp-only: preserved for order_flow / legacy handlers (byte-identical path)
    raw_entry: dict[str, Any] | None = None
    raw_message: dict[str, Any] | None = None

    @property
    def tenant_routing_id(self) -> str:
        """Key used with resolve_tenant (whatsapp phone_number_id for now)."""
        return self.account_id


@dataclass
class OutboundMessage:
    """Channel-neutral outbound — adapters render to provider payloads."""

    channel: ChannelType
    recipient_id: str
    text: str = ""
    choices: list[InteractiveChoice] = field(default_factory=list)
    choice_style: Literal["buttons", "list", "quick_replies"] = "buttons"
    list_button_label: str = "Options"
    # Pre-built provider payload (WhatsApp interactive dict) — pass-through when set
    provider_payload: dict[str, Any] | None = None
