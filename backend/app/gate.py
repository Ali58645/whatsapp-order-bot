"""
Activation gate — coexistence mode, multi-tenant.

Every incoming webhook event passes through `check_gate` BEFORE any reply
logic runs.  Returns a GateResult that tells the caller whether to proceed
and what lead metadata was detected.

check_gate() now accepts a Tenant object so campaign_phrase / business_wa_id
are read from per-tenant config rather than global env vars.

Rules (in evaluation order):
  1. Status/receipt events — drop immediately.
  2. Echo guard — drop own business number.
  3. Outbound echo detection — mute customer if detected.
  4. Human-override mute check.
  5. Lead detection — referral / campaign phrase / active session.
  6. Catch-all — allow every unmuted text/interactive through.
"""

import logging
import time
import asyncio
from dataclasses import dataclass
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.tenants import Tenant

log = logging.getLogger("orderbot.gate")

MUTE_DURATION_S: int = 24 * 60 * 60  # 24 hours

# ── In-memory mute store  {(tenant_id, wa_id): muted_until_unix_ts} ──────────
_muted: Dict[tuple[str, str], float] = {}


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

def mute_contact(wa_id: str, tenant_id: str = "", duration_s: int = MUTE_DURATION_S) -> None:
    """Silence the bot for *wa_id* within *tenant_id* for *duration_s* seconds."""
    key = (tenant_id, wa_id)
    until = time.time() + duration_s
    _muted[key] = until
    log.info(
        f"gate: muted {wa_id} (tenant={tenant_id}) until "
        f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(until))}"
    )


def _schedule_mute_persist(wa_id: str, tenant: "Tenant", duration_s: int = MUTE_DURATION_S) -> None:
    """Fire-and-forget DB mute + human_takeover event (memory already updated)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _persist() -> None:
        try:
            from datetime import datetime, timezone, timedelta
            from app.db.engine import DB_ENABLED, get_db
            from app.db.repo import get_db_tenant_id, set_mute
            from app.db.store import EventStore

            if DB_ENABLED:
                muted_until = datetime.now(timezone.utc) + timedelta(seconds=duration_s)
                async with get_db() as db:
                    tid = await get_db_tenant_id(db, tenant.phone_number_id)
                    if tid is not None:
                        await set_mute(db, tid, wa_id, muted_until)
            await EventStore.append(
                tenant, "human_takeover", {"wa_id": wa_id}, wa_id=wa_id
            )
        except Exception as exc:
            log.error(f"gate: DB mute persist failed for {wa_id} — {exc}")

    loop.create_task(_persist())


def is_muted(wa_id: str, tenant_id: str = "") -> bool:
    key = (tenant_id, wa_id)
    until = _muted.get(key)
    if until is None:
        return False
    if time.time() >= until:
        del _muted[key]
        return False
    return True


def clear_mute(wa_id: str, tenant_id: str = "") -> None:
    _muted.pop((tenant_id, wa_id), None)


# ── Main gate function ────────────────────────────────────────────────────────

def check_gate(
    entry_value: dict,
    active_session: bool,
    tenant: "Tenant",
) -> GateResult:
    """
    Evaluate the gate for one webhook value payload.

    *entry_value* is body["entry"][0]["changes"][0]["value"].
    *active_session* is True if the sender already has a live lead session.
    *tenant* provides campaign_phrase and business_wa_id.

    Returns GateResult(allowed=False) for anything that should be silently ignored.
    """
    tenant_id = tenant.phone_number_id

    # ── 0. Status/receipt events ─────────────────────────────────────────────
    if "statuses" in entry_value and "messages" not in entry_value:
        return GateResult(allowed=False, is_status_event=True)

    # ── 1. Must have a messages array ────────────────────────────────────────
    if "messages" not in entry_value:
        return GateResult(allowed=False)

    message = entry_value["messages"][0]
    sender: str = message.get("from", "")

    # ── 2 & 3. Outbound echo detection ───────────────────────────────────────
    contacts = entry_value.get("contacts", [])
    if contacts:
        contact_ids = {c.get("wa_id") for c in contacts}
        if sender not in contact_ids:
            customer_id = next(iter(contact_ids), None)
            if customer_id:
                mute_contact(customer_id, tenant_id)
                _schedule_mute_persist(customer_id, tenant)
            log.info(f"gate: outbound echo detected — muting customer {customer_id}")
            return GateResult(allowed=False, sender=sender)

    if tenant.business_wa_id and sender == tenant.business_wa_id:
        log.info(f"gate: echo from own number {sender} — ignored")
        return GateResult(allowed=False, sender=sender)

    # ── 4. Human-override mute check ─────────────────────────────────────────
    if is_muted(sender, tenant_id):
        log.info(f"gate: {sender} is muted — silent")
        return GateResult(allowed=False, sender=sender)

    # ── 5. Lead detection ─────────────────────────────────────────────────────
    msg_type: str = message.get("type", "text")
    text: Optional[str] = None
    if msg_type == "text":
        text = message.get("text", {}).get("body", "").strip()

    # 5a. Referral object
    referral: Optional[dict] = message.get("referral")
    if referral:
        source_label = referral.get("headline") or referral.get("source_id", "ad")
        log.info(f"gate: referral lead from {sender} — source: {source_label}")
        return GateResult(
            allowed=True, sender=sender, text=text,
            message_type=msg_type, referral=referral, lead_source=source_label,
        )

    # 5b. Campaign greeting phrase
    if text and tenant.campaign_phrase.lower() in text.lower():
        log.info(f"gate: campaign phrase match from {sender}")
        return GateResult(
            allowed=True, sender=sender, text=text,
            message_type=msg_type,
            lead_source=f"campaign:{tenant.campaign_phrase}",
        )

    # 5c. Already has an active lead session
    if active_session:
        return GateResult(
            allowed=True, sender=sender, text=text,
            message_type=msg_type, lead_source="active_session",
        )

    # ── 6. Catch-all ─────────────────────────────────────────────────────────
    if msg_type in ("text", "interactive"):
        log.info(f"gate: direct message from {sender} — catch-all allow")
        return GateResult(
            allowed=True, sender=sender, text=text,
            message_type=msg_type, lead_source="direct",
        )

    log.info(f"gate: non-text ({msg_type}) from {sender} — catch-all allow")
    return GateResult(
        allowed=True, sender=sender, text=None,
        message_type=msg_type, lead_source="direct",
    )
