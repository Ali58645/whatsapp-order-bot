"""Detect confirmed orders in Claude's reply and forward a clean slip to the owner."""

import json
import logging
import re
from typing import Optional, Tuple

log = logging.getLogger("orderbot.orders")

ORDER_MARKER = "ORDER_JSON:"


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


async def forward_order_to_owner(order: dict, customer_number: str,
                                 owner_number: str, send_fn) -> None:
    """Send a formatted order slip to the shop owner's WhatsApp."""
    if not owner_number:
        log.warning("OWNER_WHATSAPP not set — order not forwarded")
        return

    lines = ["🔔 *NEW ORDER*", ""]
    for item in order.get("items", []):
        lines.append(f"• {item['qty']}x {item['name']} — Rs. {item['price'] * item['qty']}")
    lines.append("")
    lines.append(f"*Total: Rs. {order.get('total', '?')}*")
    lines.append(f"📍 {order.get('address', 'No address')}")
    lines.append(f"📱 Customer: +{customer_number}")

    await send_fn(owner_number, "\n".join(lines))
    log.info(f"Order forwarded to owner: {order}")
