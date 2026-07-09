"""
Activation gate — coexistence mode.

Every incoming webhook event passes through `check_gate` BEFORE any reply
logic runs.  Returns a GateResult that tells the caller whether to proceed
and what lead metadata was detected.

Rules (in evaluation order):
  1. Echo guard   — silently drop messages whose sender == our own number.
  2. Human-override — if the *business app* sent a manual reply to a contact,
                      mute that contact for 24 h.  Also drop muted contacts.
  3. Lead detection — activate only if referral OR campaign phrase OR active session.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional

log = logging.getLogger("orderbot.gate")

# ── Config ──────────────────────────────────────────────────────────────────
BUSINESS_WA_ID: str = os.environ.get("BUSINESS_WA_ID", "")
CAMPAIGN_PHRASE: str = os.environ.get("CAMPAIGN_PHRASE", "Bahi POS")

MUTE_DURATION_S: int = 24 * 60 * 60  # 24 hours

# ── In-memory mute store  {wa_id: muted_until_unix_ts} ──────────────────────
_muted: Dict[str, float] = {}


# ── Public result type ───────────────────────────────────────────────────────
@dataclass
class GateResult:
    allowed: bool
    sender: str = ""
    text: Optional[str] = None          # None for non-text messages
    message_type: str = "text"
    referral: Optional[dict] = None     # raw referral object if present
    lead_source: Optional[str] = None   # human-readable source label
    is_status_event: bool = False       # True for delivered/read receipts


# ── Mute helpers ─────────────────────────────────────────────────────────────
def mute_contact(wa_id: str, duration_s: int = MUTE_DURATION_S) -> None:
    """Silence the bot for *wa_id* for *duration_s* seconds."""
    until = time.time() + duration_s
    _muted[wa_id] = until
    log.info(
        f"gate: muted {wa_id} until {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(until))}"
    )


def is_muted(wa_id: str) -> bool:
    until = _muted.get(wa_id)
    if until is None:
        return False
    if time.time() >= until:
        del _muted[wa_id]          # expired — clean up
        return False
    return True


def clear_mute(wa_id: str) -> None:
    _muted.pop(wa_id, None)


# ── Main gate function ────────────────────────────────────────────────────────
def check_gate(
    entry_value: dict,
    active_session: bool,
) -> GateResult:
    """
    Evaluate the gate for one webhook value payload.

    *entry_value* is body["entry"][0]["changes"][0]["value"].
    *active_session* is True if the sender already has a live lead session.

    Returns GateResult(allowed=False) for anything that should be silently ignored.
    """
    # ── 0. Status/receipt events — drop immediately, no echo/mute logic ──────
    # These arrive on the same webhook URL but must never trigger mute or note writes.
    if "statuses" in entry_value and "messages" not in entry_value:
        return GateResult(allowed=False, is_status_event=True)

    # ── 1. Must have a messages array ────────────────────────────────────────
    if "messages" not in entry_value:
        return GateResult(allowed=False)

    message = entry_value["messages"][0]
    sender: str = message.get("from", "")

    # ── 2. Echo guard — drop our own business number ──────────────────────────
    #    But do NOT return before checking for outbound echoes (which carry our
    #    number as sender AND a contacts list pointing to the real customer).
    #    Outbound echoes must mute the customer before we drop.

    # ── 3. Detect manual app echoes (message sent *by* the business app) ──────
    #   Reliable heuristic: contacts list is present AND the first contact wa_id
    #   does NOT match the "from" field → this is an outbound echo.
    contacts = entry_value.get("contacts", [])
    if contacts:
        contact_ids = {c.get("wa_id") for c in contacts}
        if sender not in contact_ids:
            # Outbound echo: mute the actual customer and drop
            customer_id = next(iter(contact_ids), None)
            if customer_id:
                mute_contact(customer_id)
            log.info(f"gate: outbound echo detected — muting customer {customer_id}")
            return GateResult(allowed=False, sender=sender)

    # Plain echo from own number (no contacts list, or contacts matched sender)
    if BUSINESS_WA_ID and sender == BUSINESS_WA_ID:
        log.info(f"gate: echo from own number {sender} — ignored")
        return GateResult(allowed=False, sender=sender)

    # ── 4. Human-override mute check ─────────────────────────────────────────
    if is_muted(sender):
        log.info(f"gate: {sender} is muted — silent")
        return GateResult(allowed=False, sender=sender)

    # ── 5. Lead detection ─────────────────────────────────────────────────────
    msg_type: str = message.get("type", "text")
    text: Optional[str] = None
    if msg_type == "text":
        text = message.get("text", {}).get("body", "").strip()
    # For interactive replies, text stays None — handled by parse_interactive_reply

    # 5a. Referral object (click-to-WhatsApp ad)
    referral: Optional[dict] = message.get("referral")
    if referral:
        source_label = referral.get("headline") or referral.get("source_id", "ad")
        log.info(f"gate: referral lead from {sender} — source: {source_label}")
        return GateResult(
            allowed=True,
            sender=sender,
            text=text,
            message_type=msg_type,
            referral=referral,
            lead_source=source_label,
        )

    # 5b. Campaign greeting phrase (text messages only)
    if text and CAMPAIGN_PHRASE.lower() in text.lower():
        log.info(f"gate: campaign phrase match from {sender}")
        return GateResult(
            allowed=True,
            sender=sender,
            text=text,
            message_type=msg_type,
            lead_source=f"campaign:{CAMPAIGN_PHRASE}",
        )

    # 5c. Already has an active lead session (includes interactive replies mid-flow)
    if active_session:
        return GateResult(
            allowed=True,
            sender=sender,
            text=text,
            message_type=msg_type,
            lead_source="active_session",
        )

    # ── 6. Default: silent ───────────────────────────────────────────────────
    log.info(f"gate: silent for {sender}")
    return GateResult(allowed=False, sender=sender)
