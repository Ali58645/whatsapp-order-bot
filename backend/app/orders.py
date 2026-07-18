"""Detect confirmed orders in Claude's reply and forward a clean slip to the owner."""

import asyncio
import json
import logging
import re
from typing import Optional, Tuple

log = logging.getLogger("orderbot.orders")

ORDER_MARKER = "ORDER_JSON:"

# Retry config for owner-forwarding
_RETRY_DELAYS = (1, 2, 4)  # seconds — exponential backoff across 3 attempts


def detect_confirmed_order(reply: str) -> Tuple[Optional[dict], str]:
    """
    Returns (order_dict or None, reply_with_json_line_removed).
    Claude appends 'ORDER_JSON: {...}' on the final line only after
    the customer confirms.
    """
    if ORDER_MARKER not in reply:
        return None, reply

    idx = reply.index(ORDER_MARKER)
    clean_reply = reply[:idx].strip()
    json_part = reply[idx + len(ORDER_MARKER):].strip()

    # Strip markdown fences if the model added them
    json_part = re.sub(r"^```(json)?|```$", "", json_part, flags=re.MULTILINE).strip()

    try:
        order = json.loads(json_part)
    except json.JSONDecodeError:
        log.error(f"Failed to parse order JSON: {json_part}")
        return None, clean_reply

    return order, clean_reply


async def forward_order_to_owner(
    order: dict,
    customer_number: str,
    owner_number: str,
    send_fn,
    tenant=None,
) -> None:
    """
    Send a formatted order slip to the shop owner's WhatsApp.
    Retries up to 3 times (1s / 2s / 4s backoff).
    On total failure: logs CRITICAL with full order payload and notifies the customer.
    """
    if not owner_number:
        log.warning("OWNER_WHATSAPP not set — order not forwarded")
        return

    from app.messages import MessageResolver

    mr = MessageResolver(tenant)
    items_lines = []
    for item in order.get("items", []):
        items_lines.append(
            f"• {item['qty']}x {item['name']} — Rs. {item['price'] * item['qty']}"
        )
    items_block = "\n".join(items_lines)
    slip = (
        mr.text("order.owner_slip_title")
        + "\n\n"
        + mr.text(
            "order.owner_slip_body",
            {
                "items": items_block,
                "total": order.get("total", "?"),
                "address": order.get("address", "No address"),
                "customer": customer_number,
            },
        )
    ).strip()

    # Try up to 3 times with exponential backoff
    for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
        sent = await send_fn(owner_number, slip)
        if sent:
            log.info(f"Order forwarded to owner (attempt {attempt}): {order}")
            return
        if attempt < len(_RETRY_DELAYS):
            log.warning(f"Owner send attempt {attempt} failed — retrying in {delay}s")
            await asyncio.sleep(delay)

    # All retries exhausted
    log.critical(
        f"UNDELIVERED ORDER — all 3 send attempts to owner failed. "
        f"Customer: +{customer_number}. Full order: {json.dumps(order)}"
    )
    # Notify the customer so they're not left hanging
    await send_fn(
        customer_number,
        mr.text("order.owner_fail_customer"),
    )
