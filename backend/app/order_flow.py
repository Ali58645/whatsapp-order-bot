"""
Interactive order flow driven by menu_v2.

Phases stored in session meta (lead-style) via sessions + optional DB:
  ORDER_BROWSE → ORDER_MODIFIER → ORDER_QTY → ORDER_MORE → ORDER_CONFIRM → done

Falls back to LLM text flow when tenant has no menu_v2.
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Awaitable

from app.menu_v2 import (
    MORE_ROW_ID,
    build_category_list_payload,
    build_confirm_buttons,
    build_greeting_and_entry,
    build_item_list_payload,
    build_modifier_buttons_payload,
    build_more_items_buttons,
    build_quantity_ask_payload,
    cart_grand_total,
    find_item,
    format_cart_summary,
    resolve_modifier_delta,
    validate_menu_v2,
    visible_categories,
)
from app.interactive import parse_interactive_reply
from app.sessions import clear_session, get_sender_lock
from app.tenants import Tenant

log = logging.getLogger("orderbot.order_flow")

SendFn = Callable[..., Awaitable[bool]]


def _meta_key(tenant_id: str, sender: str) -> str:
    return f"{tenant_id}:{sender}"


# In-memory order carts (mirrors lead meta pattern; also persisted into session history notes)
_order_meta: dict[str, dict] = {}


def get_order_meta(sender: str, tenant_id: str = "default") -> dict:
    return _order_meta.setdefault(_meta_key(tenant_id, sender), {
        "phase": "ORDER_BROWSE",
        "cart": [],
        "pending_item_id": None,
        "pending_mod": None,
        "page": 0,
        "category_id": None,
    })


def clear_order_meta(sender: str, tenant_id: str = "default") -> None:
    _order_meta.pop(_meta_key(tenant_id, sender), None)


def tenant_has_menu_v2(tenant: Tenant) -> bool:
    return bool(tenant.menu_v2)


async def handle_order_interactive(
    entry: dict,
    tenant: Tenant,
    send: SendFn,
    *,
    on_confirm: Callable[[dict, str, Tenant], Awaitable[None]] | None = None,
) -> dict:
    """
    Handle one inbound webhook value for menu_v2 order flow.
    Returns {"status": "ok"|"ignored"}.
    """
    menu = validate_menu_v2(tenant.menu_v2)
    tid = tenant.phone_number_id

    if "messages" not in entry:
        return {"status": "ignored"}
    message = entry["messages"][0]
    sender = message["from"]
    msg_type = message.get("type")

    async with get_sender_lock(sender, tenant_id=tid):
        meta = get_order_meta(sender, tenant_id=tid)

        # Reset commands
        if msg_type == "text":
            text = (message.get("text") or {}).get("body", "").strip().lower()
            if text in ("reset", "restart", "naya order", "menu", "start"):
                clear_order_meta(sender, tenant_id=tid)
                clear_session(sender, tenant_id=tid)
                meta = get_order_meta(sender, tenant_id=tid)
                for p in build_greeting_and_entry(sender, menu, tenant=tenant):
                    if p.get("type") == "text":
                        await send(sender, text=p["text"]["body"], tenant=tenant)
                    else:
                        await send(sender, interactive_payload=p, tenant=tenant)
                return {"status": "ok"}

        # First message with no cart phase → start browse
        if meta.get("phase") == "ORDER_BROWSE" and not meta.get("started"):
            meta["started"] = True
            for p in build_greeting_and_entry(sender, menu, tenant=tenant):
                if p.get("type") == "text":
                    await send(sender, text=p["text"]["body"], tenant=tenant)
                else:
                    await send(sender, interactive_payload=p, tenant=tenant)
            # If they also sent interactive, fall through; if text only, done
            if msg_type != "interactive":
                return {"status": "ok"}

        if msg_type == "interactive":
            reply_id, reply_title = parse_interactive_reply(message)
            if not reply_id:
                return {"status": "ignored"}
            return await _handle_reply(
                sender, meta, menu, tenant, send, reply_id, reply_title, on_confirm
            )

        if msg_type == "text" and meta.get("phase") == "ORDER_QTY":
            return await _handle_qty_text(sender, meta, menu, tenant, send, message)

        # Fallback nudge
        await send(
            sender,
            text=tenant.msg().text("order.nudge_menu"),
            tenant=tenant,
        )
        return {"status": "ok"}


async def _handle_reply(
    sender: str,
    meta: dict,
    menu: dict,
    tenant: Tenant,
    send: SendFn,
    reply_id: str,
    reply_title: str,
    on_confirm,
) -> dict:
    mr = tenant.msg()
    # Category pick
    if reply_id.startswith("cat:"):
        cat_id = reply_id[4:]
        if cat_id == "empty":
            return {"status": "ok"}
        meta["category_id"] = cat_id
        meta["page"] = 0
        meta["phase"] = "ORDER_BROWSE"
        payload = build_item_list_payload(
            sender, menu, category_id=cat_id, page=0, tenant=tenant
        )
        await send(sender, interactive_payload=payload, tenant=tenant)
        return {"status": "ok"}

    # Pagination
    if reply_id.startswith(MORE_ROW_ID):
        # menu:more:<cat|all>:<page>
        parts = reply_id.split(":")
        cat_part = parts[2] if len(parts) > 2 else "all"
        page = int(parts[3]) if len(parts) > 3 else 1
        cat_id = None if cat_part == "all" else cat_part
        meta["category_id"] = cat_id
        meta["page"] = page
        payload = build_item_list_payload(
            sender, menu, category_id=cat_id, page=page, tenant=tenant
        )
        await send(sender, interactive_payload=payload, tenant=tenant)
        return {"status": "ok"}

    # Item pick
    if reply_id.startswith("item:"):
        item_id = reply_id[5:]
        if item_id == "empty":
            return {"status": "ok"}
        item = find_item(menu, item_id)
        if not item:
            await send(sender, text=mr.text("order.item_not_found"), tenant=tenant)
            return {"status": "ok"}
        meta["pending_item_id"] = item_id
        meta["pending_mod"] = None
        mod_payload = build_modifier_buttons_payload(sender, item, tenant=tenant)
        if mod_payload:
            meta["phase"] = "ORDER_MODIFIER"
            await send(sender, interactive_payload=mod_payload, tenant=tenant)
        else:
            meta["phase"] = "ORDER_QTY"
            await send(
                sender,
                text=build_quantity_ask_payload(sender, item["name"], tenant=tenant)["text"]["body"],
                tenant=tenant,
            )
        return {"status": "ok"}

    # Modifier pick
    if reply_id.startswith("mod:"):
        # mod:itemId:modId:optId
        parts = reply_id.split(":")
        if len(parts) < 4:
            return {"status": "ignored"}
        _, item_id, mod_id, opt_id = parts[0], parts[1], parts[2], parts[3]
        item = find_item(menu, item_id)
        if not item:
            return {"status": "ignored"}
        delta, label = resolve_modifier_delta(item, mod_id, opt_id)
        meta["pending_item_id"] = item_id
        meta["pending_mod"] = {"mod_id": mod_id, "opt_id": opt_id, "delta": delta, "label": label}
        meta["phase"] = "ORDER_QTY"
        await send(
            sender,
            text=build_quantity_ask_payload(sender, item["name"], tenant=tenant)["text"]["body"],
            tenant=tenant,
        )
        return {"status": "ok"}

    # Cart more / done
    if reply_id == "cart:more":
        meta["phase"] = "ORDER_BROWSE"
        cats = visible_categories(menu)
        if len(cats) > 1:
            await send(
                sender,
                interactive_payload=build_category_list_payload(sender, menu, tenant=tenant),
                tenant=tenant,
            )
        else:
            cat_id = cats[0]["id"] if cats else meta.get("category_id")
            await send(
                sender,
                interactive_payload=build_item_list_payload(
                    sender, menu, category_id=cat_id, page=0, tenant=tenant
                ),
                tenant=tenant,
            )
        return {"status": "ok"}

    if reply_id == "cart:done":
        return await _send_confirm(sender, meta, menu, tenant, send)

    if reply_id == "order:confirm":
        cart = meta.get("cart") or []
        if not cart:
            await send(sender, text=mr.text("order.cart_empty"), tenant=tenant)
            return {"status": "ok"}
        order = _cart_to_order(menu, cart)
        if on_confirm:
            await on_confirm(order, sender, tenant)
        clear_order_meta(sender, tenant_id=tenant.phone_number_id)
        clear_session(sender, tenant_id=tenant.phone_number_id)
        await send(sender, text=mr.text("order.order_received"), tenant=tenant)
        return {"status": "ok"}

    if reply_id == "order:cancel":
        clear_order_meta(sender, tenant_id=tenant.phone_number_id)
        await send(sender, text=mr.text("order.order_cancel"), tenant=tenant)
        return {"status": "ok"}

    log.info(f"order_flow: unhandled reply_id={reply_id!r} title={reply_title!r}")
    return {"status": "ok"}


async def _handle_qty_text(sender, meta, menu, tenant, send, message) -> dict:
    mr = tenant.msg()
    text = (message.get("text") or {}).get("body", "").strip()
    m = re.search(r"\b([1-9])\b", text)
    if not m:
        await send(sender, text=mr.text("order.qty_invalid"), tenant=tenant)
        return {"status": "ok"}
    qty = int(m.group(1))
    item_id = meta.get("pending_item_id")
    item = find_item(menu, item_id) if item_id else None
    if not item:
        meta["phase"] = "ORDER_BROWSE"
        await send(sender, text=mr.text("order.pick_item_first"), tenant=tenant)
        return {"status": "ok"}
    pend = meta.get("pending_mod") or {}
    line = {
        "item_id": item["id"],
        "name": item["name"],
        "qty": qty,
        "unit_price": item["price"],
        "price_delta": int(pend.get("delta", 0) or 0),
        "modifier_label": pend.get("label") or "",
    }
    meta.setdefault("cart", []).append(line)
    meta["pending_item_id"] = None
    meta["pending_mod"] = None
    meta["phase"] = "ORDER_MORE"
    summary = format_cart_summary(menu, meta["cart"], tenant=tenant)
    await send(sender, text=summary, tenant=tenant)
    await send(
        sender, interactive_payload=build_more_items_buttons(sender, tenant=tenant), tenant=tenant
    )
    return {"status": "ok"}


async def _send_confirm(sender, meta, menu, tenant, send) -> dict:
    mr = tenant.msg()
    cart = meta.get("cart") or []
    if not cart:
        await send(sender, text=mr.text("order.cart_empty"), tenant=tenant)
        return {"status": "ok"}
    summary = format_cart_summary(menu, cart, tenant=tenant)
    note = (menu.get("settings") or {}).get("order_confirm_note") or mr.text("order.confirm_note")
    meta["phase"] = "ORDER_CONFIRM"
    await send(
        sender,
        interactive_payload=build_confirm_buttons(sender, summary, note, tenant=tenant),
        tenant=tenant,
    )
    return {"status": "ok"}


def _cart_to_order(menu: dict, cart: list[dict]) -> dict:
    items = []
    for line in cart:
        items.append({
            "name": line["name"] + (f" ({line['modifier_label']})" if line.get("modifier_label") else ""),
            "qty": line["qty"],
            "price": int(line["unit_price"]) + int(line.get("price_delta") or 0),
        })
    return {
        "items": items,
        "total": cart_grand_total(menu, cart),
        "address": "",
    }
