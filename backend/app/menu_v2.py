"""
menu_v2 — WhatsApp-constraint-aware ordering catalog.

Single source of truth for:
  - schema validation (API layer)
  - interactive list/button payloads (runtime + Settings preview)
  - cart / modifier / delivery math

Stored in tenants.config as:
  menu_v2         → published (customers see this)
  menu_v2_draft   → draft (preview + test-send)
"""

from __future__ import annotations

import copy
import uuid
from typing import Any, Optional

from app.interactive import (
    BUTTONS_MAX,
    ROWS_MAX,
    build_buttons,
    build_list,
)

# WhatsApp Cloud API limits (also enforced at API)
CATEGORY_NAME_MAX = 24   # list section title
ITEM_NAME_MAX = 24       # list row title
ITEM_DESC_MAX = 72       # list row description
OPTION_LABEL_MAX = 20    # reply button title (= BUTTON_TITLE_MAX)
MODIFIER_GROUPS_MAX = 1
MODIFIER_OPTIONS_MAX = 3
MORE_ROW_ID = "menu:more"
MORE_ROW_TITLE = "Aur dekhein →"
PAGE_SIZE = ROWS_MAX - 1  # 9 items + "more" when paginating


class MenuV2Error(ValueError):
    """Raised on invalid menu_v2 payloads (API maps to HTTP 400)."""


def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def empty_menu_v2() -> dict:
    return {
        "categories": [],
        "items": [],
        "settings": {
            "greeting_text": "Assalam o Alaikum! Menu dekhne ke liye neeche tap karein.",
            "menu_button_label": "Menu dekhein",
            "delivery": {
                "enabled": True,
                "charge": 100,
                "free_above": 0,
                "area_note": "",
            },
            "order_confirm_note": "Confirm karein?",
            "currency": "PKR",
        },
    }


def _require_str(val: Any, field: str, max_len: int, *, allow_empty: bool = False) -> str:
    if val is None:
        val = ""
    s = str(val).strip()
    if not allow_empty and not s:
        raise MenuV2Error(f"{field} required")
    if len(s) > max_len:
        raise MenuV2Error(f"{field} max {max_len} chars (got {len(s)})")
    return s


def validate_menu_v2(raw: Any, *, strict_limits: bool = True) -> dict:
    """
    Validate and normalize a menu_v2 object.
    Rejects over-limit strings (does not silently truncate) when strict_limits=True.
    """
    if raw is None:
        return empty_menu_v2()
    if not isinstance(raw, dict):
        raise MenuV2Error("menu_v2 must be an object")

    settings_in = raw.get("settings") or {}
    if not isinstance(settings_in, dict):
        raise MenuV2Error("menu_v2.settings must be an object")

    delivery_in = settings_in.get("delivery") or {}
    if not isinstance(delivery_in, dict):
        raise MenuV2Error("menu_v2.settings.delivery must be an object")

    try:
        charge = int(delivery_in.get("charge", 0) or 0)
        free_above = int(delivery_in.get("free_above", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise MenuV2Error("delivery charge/free_above must be integers") from exc
    if charge < 0 or free_above < 0:
        raise MenuV2Error("delivery charge/free_above must be >= 0")

    settings = {
        "greeting_text": _require_str(
            settings_in.get("greeting_text", ""),
            "settings.greeting_text",
            500,
            allow_empty=True,
        ),
        "menu_button_label": _require_str(
            settings_in.get("menu_button_label", "Menu dekhein") or "Menu dekhein",
            "settings.menu_button_label",
            OPTION_LABEL_MAX,
        ),
        "delivery": {
            "enabled": bool(delivery_in.get("enabled", True)),
            "charge": charge,
            "free_above": free_above,
            "area_note": _require_str(
                delivery_in.get("area_note", ""),
                "settings.delivery.area_note",
                128,
                allow_empty=True,
            ),
        },
        "order_confirm_note": _require_str(
            settings_in.get("order_confirm_note", "Confirm karein?") or "Confirm karein?",
            "settings.order_confirm_note",
            200,
            allow_empty=True,
        ),
        "currency": _require_str(
            settings_in.get("currency", "PKR") or "PKR",
            "settings.currency",
            8,
        ),
    }

    cats_in = raw.get("categories") or []
    if not isinstance(cats_in, list):
        raise MenuV2Error("menu_v2.categories must be a list")

    categories: list[dict] = []
    cat_ids: set[str] = set()
    for i, cat in enumerate(cats_in):
        if not isinstance(cat, dict):
            raise MenuV2Error(f"categories[{i}] must be an object")
        cid = str(cat.get("id") or new_id("cat")).strip()
        if cid in cat_ids:
            raise MenuV2Error(f"duplicate category id {cid}")
        cat_ids.add(cid)
        name = _require_str(cat.get("name", ""), f"categories[{i}].name", CATEGORY_NAME_MAX)
        try:
            sort = int(cat.get("sort", i))
        except (TypeError, ValueError) as exc:
            raise MenuV2Error(f"categories[{i}].sort must be int") from exc
        categories.append({
            "id": cid,
            "name": name,
            "sort": sort,
            "visible": bool(cat.get("visible", True)),
        })
    categories.sort(key=lambda c: c["sort"])

    items_in = raw.get("items") or []
    if not isinstance(items_in, list):
        raise MenuV2Error("menu_v2.items must be a list")

    items: list[dict] = []
    item_ids: set[str] = set()
    for i, it in enumerate(items_in):
        if not isinstance(it, dict):
            raise MenuV2Error(f"items[{i}] must be an object")
        iid = str(it.get("id") or new_id("item")).strip()
        if iid in item_ids:
            raise MenuV2Error(f"duplicate item id {iid}")
        item_ids.add(iid)
        cat_id = str(it.get("category_id") or "").strip()
        if cat_id and cat_id not in cat_ids:
            raise MenuV2Error(f"items[{i}].category_id unknown: {cat_id}")
        name = _require_str(it.get("name", ""), f"items[{i}].name", ITEM_NAME_MAX)
        desc = _require_str(
            it.get("description", ""), f"items[{i}].description", ITEM_DESC_MAX, allow_empty=True
        )
        try:
            price = int(it.get("price", 0))
        except (TypeError, ValueError) as exc:
            raise MenuV2Error(f"items[{i}].price must be int") from exc
        if price <= 0:
            raise MenuV2Error(f"items[{i}].price must be > 0")
        try:
            sort = int(it.get("sort", i))
        except (TypeError, ValueError) as exc:
            raise MenuV2Error(f"items[{i}].sort must be int") from exc

        modifiers_out: list[dict] = []
        mods = it.get("modifiers") or []
        if mods:
            if not isinstance(mods, list):
                raise MenuV2Error(f"items[{i}].modifiers must be a list")
            if len(mods) > MODIFIER_GROUPS_MAX:
                raise MenuV2Error(
                    f"items[{i}]: max {MODIFIER_GROUPS_MAX} modifier group (got {len(mods)})"
                )
            for mi, mod in enumerate(mods):
                if not isinstance(mod, dict):
                    raise MenuV2Error(f"items[{i}].modifiers[{mi}] must be an object")
                mid = str(mod.get("id") or new_id("mod")).strip()
                mname = _require_str(
                    mod.get("name", ""), f"items[{i}].modifiers[{mi}].name", 40
                )
                opts_in = mod.get("options") or []
                if not isinstance(opts_in, list) or not opts_in:
                    raise MenuV2Error(f"items[{i}].modifiers[{mi}].options required")
                if len(opts_in) > MODIFIER_OPTIONS_MAX:
                    raise MenuV2Error(
                        f"items[{i}].modifiers[{mi}]: max {MODIFIER_OPTIONS_MAX} options "
                        f"(reply-button limit)"
                    )
                if len(opts_in) > BUTTONS_MAX:
                    raise MenuV2Error(
                        f"items[{i}].modifiers[{mi}]: max {BUTTONS_MAX} reply buttons"
                    )
                opts_out = []
                for oi, opt in enumerate(opts_in):
                    if not isinstance(opt, dict):
                        raise MenuV2Error(
                            f"items[{i}].modifiers[{mi}].options[{oi}] must be an object"
                        )
                    oid = str(opt.get("id") or new_id("opt")).strip()
                    label = _require_str(
                        opt.get("label", ""),
                        f"items[{i}].modifiers[{mi}].options[{oi}].label",
                        OPTION_LABEL_MAX,
                    )
                    try:
                        delta = int(opt.get("price_delta", 0) or 0)
                    except (TypeError, ValueError) as exc:
                        raise MenuV2Error(
                            f"items[{i}].modifiers[{mi}].options[{oi}].price_delta must be int"
                        ) from exc
                    opts_out.append({"id": oid, "label": label, "price_delta": delta})
                modifiers_out.append({"id": mid, "name": mname, "options": opts_out})

        items.append({
            "id": iid,
            "category_id": cat_id,
            "name": name,
            "description": desc,
            "price": price,
            "available": bool(it.get("available", True)),
            "sort": sort,
            "modifiers": modifiers_out,
        })
    items.sort(key=lambda x: (x["category_id"], x["sort"]))

    return {"categories": categories, "items": items, "settings": settings}


# ── Lookups ───────────────────────────────────────────────────────────────────

def visible_categories(menu: dict) -> list[dict]:
    return [c for c in menu.get("categories", []) if c.get("visible", True)]


def available_items(menu: dict, category_id: str | None = None) -> list[dict]:
    items = [
        it for it in menu.get("items", [])
        if it.get("available", True)
        and (category_id is None or it.get("category_id") == category_id)
    ]
    return sorted(items, key=lambda x: x.get("sort", 0))


def find_item(menu: dict, item_id: str) -> Optional[dict]:
    for it in menu.get("items", []):
        if it["id"] == item_id:
            return it
    return None


def find_category(menu: dict, category_id: str) -> Optional[dict]:
    for c in menu.get("categories", []):
        if c["id"] == category_id:
            return c
    return None


# ── Payload builders (runtime === preview) ────────────────────────────────────

def build_greeting_and_entry(to: str, menu: dict) -> list[dict]:
    """
    Returns a list of outbound payloads to start the order flow:
      1) greeting text
      2) category list OR first category item list (if single visible category)
    """
    settings = menu.get("settings") or {}
    greeting = settings.get("greeting_text") or "Menu dekhne ke liye neeche tap karein."
    button = settings.get("menu_button_label") or "Menu dekhein"
    payloads: list[dict] = [
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": greeting},
        }
    ]
    cats = visible_categories(menu)
    if len(cats) == 0:
        # Flat: all available items
        payloads.append(build_item_list_payload(to, menu, category_id=None, page=0, button_label=button))
    elif len(cats) == 1:
        payloads.append(
            build_item_list_payload(to, menu, category_id=cats[0]["id"], page=0, button_label=button)
        )
    else:
        payloads.append(build_category_list_payload(to, menu, button_label=button))
    return payloads


def build_category_list_payload(to: str, menu: dict, button_label: str | None = None) -> dict:
    settings = menu.get("settings") or {}
    label = button_label or settings.get("menu_button_label") or "Menu dekhein"
    cats = visible_categories(menu)
    rows = []
    for c in cats[:ROWS_MAX]:
        count = len(available_items(menu, c["id"]))
        rows.append((f"cat:{c['id']}", c["name"], f"{count} items" if count else ""))
    if not rows:
        rows.append(("cat:empty", "No categories", "Add items in Menu Builder"))
    return build_list(to, "Category choose karein:", label[:OPTION_LABEL_MAX], rows)


def build_item_list_payload(
    to: str,
    menu: dict,
    category_id: str | None,
    page: int = 0,
    button_label: str | None = None,
) -> dict:
    """
    Build item list for a category (or all items if category_id is None).
    Auto-paginates: if more than 10 available items, page shows 9 + 'Aur dekhein →'.
    """
    settings = menu.get("settings") or {}
    label = button_label or settings.get("menu_button_label") or "Menu dekhein"
    currency = settings.get("currency") or "PKR"
    items = available_items(menu, category_id)
    cat = find_category(menu, category_id) if category_id else None
    body = f"{cat['name']} — item choose karein:" if cat else "Item choose karein:"

    start = max(0, page) * PAGE_SIZE
    remaining = items[start:]
    needs_more = len(remaining) > ROWS_MAX
    if needs_more:
        page_items = remaining[:PAGE_SIZE]
        rows = [
            (
                f"item:{it['id']}",
                it["name"][:ITEM_NAME_MAX],
                _price_desc(it, currency),
            )
            for it in page_items
        ]
        next_page = page + 1
        more_id = f"{MORE_ROW_ID}:{category_id or 'all'}:{next_page}"
        rows.append((more_id, MORE_ROW_TITLE[:ITEM_NAME_MAX], "Agli list"))
    else:
        rows = [
            (
                f"item:{it['id']}",
                it["name"][:ITEM_NAME_MAX],
                _price_desc(it, currency),
            )
            for it in remaining[:ROWS_MAX]
        ]
    if not rows:
        rows = [("item:empty", "No items", "Abhi available nahi")]
    return build_list(to, body, label[:OPTION_LABEL_MAX], rows)


def _price_desc(it: dict, currency: str) -> str:
    desc = it.get("description") or ""
    price = f"{currency} {it['price']}"
    if desc:
        combined = f"{price} · {desc}"
        return combined[:ITEM_DESC_MAX]
    return price[:ITEM_DESC_MAX]


def build_modifier_buttons_payload(to: str, item: dict) -> Optional[dict]:
    """Max 1 group, max 3 options → reply buttons. None if no modifiers."""
    mods = item.get("modifiers") or []
    if not mods:
        return None
    mod = mods[0]
    opts = mod.get("options") or []
    if not opts:
        return None
    if len(opts) > BUTTONS_MAX:
        raise MenuV2Error(f"modifier options max {BUTTONS_MAX}")
    buttons = []
    for opt in opts[:BUTTONS_MAX]:
        title = opt["label"]
        if opt.get("price_delta"):
            delta = opt["price_delta"]
            suffix = f" +{delta}" if delta > 0 else f" {delta}"
            # Keep within button title limit
            base = title[: max(1, OPTION_LABEL_MAX - len(suffix))]
            title = (base + suffix)[:OPTION_LABEL_MAX]
        buttons.append((f"mod:{item['id']}:{mod['id']}:{opt['id']}", title))
    body = f"{item['name']} — {mod.get('name', 'Option')} choose karein:"
    return build_buttons(to, body, buttons)


def build_quantity_ask_payload(to: str, item_name: str) -> dict:
    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": f"{item_name} — kitni quantity? (1-9)"},
    }


def build_more_items_buttons(to: str) -> dict:
    return build_buttons(
        to,
        "Aur kuch add karein?",
        [("cart:more", "Haan"), ("cart:done", "Nahi, bas")],
    )


def build_confirm_buttons(to: str, summary: str, confirm_note: str = "Confirm karein?") -> dict:
    body = f"{summary}\n\n{confirm_note}"
    return build_buttons(
        to,
        body[:1024],
        [("order:confirm", "Confirm"), ("order:cancel", "Cancel")],
    )


def preview_flow_steps(menu: dict, to: str = "preview") -> list[dict]:
    """
    Full preview sequence for Settings live mockup.
    Each step: {kind, label, payload}
    """
    steps: list[dict] = []
    entry = build_greeting_and_entry(to, menu)
    for i, p in enumerate(entry):
        kind = p.get("type", "text")
        steps.append({"id": f"entry_{i}", "kind": kind, "payload": p, "label": "Entry"})

    cats = visible_categories(menu)
    cat_id = cats[0]["id"] if len(cats) == 1 else (cats[0]["id"] if cats else None)
    if len(cats) > 1 and cats:
        # Simulate tapping first category
        item_payload = build_item_list_payload(to, menu, category_id=cats[0]["id"], page=0)
        steps.append({"id": "items", "kind": "interactive", "payload": item_payload, "label": "Items"})
        cat_id = cats[0]["id"]
    elif len(cats) == 0:
        cat_id = None

    items = available_items(menu, cat_id)
    if items:
        first = items[0]
        mod_p = build_modifier_buttons_payload(to, first)
        if mod_p:
            steps.append({"id": "modifier", "kind": "interactive", "payload": mod_p, "label": "Modifier"})
        steps.append({
            "id": "qty",
            "kind": "text",
            "payload": build_quantity_ask_payload(to, first["name"]),
            "label": "Quantity",
        })
        # Demo cart with 1x first item (no modifier)
        line = {
            "item_id": first["id"],
            "name": first["name"],
            "qty": 1,
            "unit_price": first["price"],
            "price_delta": 0,
            "modifier_label": "",
        }
        summary = format_cart_summary(menu, [line])
        steps.append({
            "id": "more",
            "kind": "interactive",
            "payload": build_more_items_buttons(to),
            "label": "Add more?",
        })
        note = (menu.get("settings") or {}).get("order_confirm_note") or "Confirm karein?"
        steps.append({
            "id": "confirm",
            "kind": "interactive",
            "payload": build_confirm_buttons(to, summary, note),
            "label": "Confirm",
        })
    return steps


# ── Cart math ─────────────────────────────────────────────────────────────────

def line_total(line: dict) -> int:
    return (int(line.get("unit_price", 0)) + int(line.get("price_delta", 0))) * int(line.get("qty", 1))


def cart_subtotal(lines: list[dict]) -> int:
    return sum(line_total(line) for line in lines)


def delivery_charge_for(menu: dict, subtotal: int) -> int:
    d = (menu.get("settings") or {}).get("delivery") or {}
    if not d.get("enabled", True):
        return 0
    charge = int(d.get("charge", 0) or 0)
    free_above = int(d.get("free_above", 0) or 0)
    if free_above > 0 and subtotal >= free_above:
        return 0
    return charge


def cart_grand_total(menu: dict, lines: list[dict]) -> int:
    sub = cart_subtotal(lines)
    return sub + delivery_charge_for(menu, sub)


def format_cart_summary(menu: dict, lines: list[dict]) -> str:
    currency = (menu.get("settings") or {}).get("currency") or "PKR"
    parts = ["Aapka order:"]
    for line in lines:
        mod = f" ({line['modifier_label']})" if line.get("modifier_label") else ""
        parts.append(f"• {line['qty']}x {line['name']}{mod} — {currency} {line_total(line)}")
    sub = cart_subtotal(lines)
    delivery = delivery_charge_for(menu, sub)
    if delivery:
        parts.append(f"Delivery: {currency} {delivery}")
    elif ((menu.get("settings") or {}).get("delivery") or {}).get("enabled"):
        parts.append("Delivery: Free")
    parts.append(f"Total: {currency} {sub + delivery}")
    return "\n".join(parts)


def resolve_modifier_delta(item: dict, mod_id: str, opt_id: str) -> tuple[int, str]:
    for mod in item.get("modifiers") or []:
        if mod["id"] != mod_id:
            continue
        for opt in mod.get("options") or []:
            if opt["id"] == opt_id:
                return int(opt.get("price_delta", 0) or 0), str(opt.get("label", ""))
    return 0, ""


def migrate_legacy_menu(legacy: dict | None) -> dict:
    """Best-effort convert old menu → menu_v2."""
    base = empty_menu_v2()
    if not legacy or not isinstance(legacy, dict):
        return base
    base["settings"]["greeting_text"] = f"Welcome to {legacy.get('shop_name', 'our shop')}!"
    if legacy.get("delivery_fee") is not None:
        base["settings"]["delivery"]["charge"] = int(legacy["delivery_fee"])
    if legacy.get("delivery_area"):
        base["settings"]["delivery"]["area_note"] = str(legacy["delivery_area"])[:128]
    cats = []
    items = []
    for ci, cat in enumerate(legacy.get("categories") or []):
        cid = new_id("cat")
        cname = str(cat.get("name", f"Category {ci+1}"))[:CATEGORY_NAME_MAX]
        cats.append({"id": cid, "name": cname, "sort": ci, "visible": True})
        for ii, it in enumerate(cat.get("items") or []):
            items.append({
                "id": new_id("item"),
                "category_id": cid,
                "name": str(it.get("name", "Item"))[:ITEM_NAME_MAX],
                "description": "",
                "price": int(it.get("price", 1) or 1),
                "available": bool(it.get("available", True)),
                "sort": ii,
                "modifiers": [],
            })
    base["categories"] = cats
    base["items"] = items
    return validate_menu_v2(base)


def deep_copy_menu(menu: dict) -> dict:
    return copy.deepcopy(menu)
