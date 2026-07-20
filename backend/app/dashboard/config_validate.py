"""
Tenant config validation for dashboard saves.
Reuses WhatsApp limits from app/interactive.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.interactive import BUTTON_TITLE_MAX, ROWS_MAX
from app.prompt_data import sanitize_text

FAQ_MAX_PAIRS = 30
FAQ_ANSWER_MAX = 500
FAQ_QUESTION_MAX = 200
GREETING_MAX = 500
FACTS_FIELD_MAX = 2000
CAMPAIGN_PHRASE_MAX = 128
DEMO_SLOT_MAX = 64
SHOP_NAME_MAX = 128
CATEGORY_NAME_MAX = 24
ITEM_NAME_MAX = BUTTON_TITLE_MAX


def _err(msg: str) -> None:
    raise HTTPException(status_code=400, detail=msg)


def validate_config_patch(flow_mode: str, patch: dict) -> dict:
    """Validate and sanitize a config patch; returns cleaned dict."""
    out: dict[str, Any] = {}

    if "greeting_text" in patch:
        out["greeting_text"] = sanitize_text(patch["greeting_text"], max_len=GREETING_MAX)

    if "greeting_language" in patch:
        lang = str(patch["greeting_language"]).strip().lower()
        if lang not in ("roman_urdu", "en", "ur"):
            _err("greeting_language must be roman_urdu, en, or ur")
        out["greeting_language"] = lang

    if "campaign_phrase" in patch:
        cp = sanitize_text(patch["campaign_phrase"], max_len=CAMPAIGN_PHRASE_MAX)
        if not cp:
            _err("campaign_phrase cannot be empty")
        out["campaign_phrase"] = cp

    if "demo_slots" in patch:
        slots = patch["demo_slots"]
        if not isinstance(slots, list) or len(slots) < 1:
            _err("demo_slots must be a non-empty list")
        cleaned = [sanitize_text(s, max_len=DEMO_SLOT_MAX) for s in slots[:2]]
        while len(cleaned) < 2:
            cleaned.append(cleaned[0])
        out["demo_slots"] = cleaned

    if "facts_features" in patch:
        out["facts_features"] = sanitize_text(patch["facts_features"], max_len=FACTS_FIELD_MAX)
    if "facts_pricing_note" in patch:
        out["facts_pricing_note"] = sanitize_text(patch["facts_pricing_note"], max_len=FACTS_FIELD_MAX)
    if "facts_claims_note" in patch:
        out["facts_claims_note"] = sanitize_text(patch["facts_claims_note"], max_len=FACTS_FIELD_MAX)

    if "faq" in patch:
        faq = patch["faq"]
        if not isinstance(faq, list):
            _err("faq must be a list")
        # Drop empty rows
        faq = [
            item for item in faq
            if isinstance(item, dict)
            and (str(item.get("question", "")).strip() or str(item.get("answer", "")).strip())
        ]
        if len(faq) > FAQ_MAX_PAIRS:
            _err(f"faq max {FAQ_MAX_PAIRS} pairs")
        cleaned_faq = []
        seen_q: set[str] = set()
        for i, item in enumerate(faq):
            if not isinstance(item, dict):
                _err(f"faq[{i}] must be an object")
            q = sanitize_text(item.get("question", ""), max_len=FAQ_QUESTION_MAX)
            a = sanitize_text(item.get("answer", ""), max_len=FAQ_ANSWER_MAX)
            if not q or not a:
                _err(f"faq[{i}] question and answer required")
            qkey = q.lower()
            if qkey in seen_q:
                _err(f"faq: duplicate question {q!r}")
            seen_q.add(qkey)
            cleaned_faq.append({"question": q, "answer": a})
        out["faq"] = cleaned_faq

    if "menu" in patch:
        if flow_mode != "order":
            _err("menu only valid for order flow_mode")
        menu = patch["menu"]
        if not isinstance(menu, dict):
            _err("menu must be an object")
        shop = sanitize_text(menu.get("shop_name", ""), max_len=SHOP_NAME_MAX)
        if not shop:
            _err("menu.shop_name required")
        cats = menu.get("categories", [])
        if not isinstance(cats, list) or not cats:
            _err("menu.categories required")
        if len(cats) > ROWS_MAX:
            _err(f"menu max {ROWS_MAX} categories")
        cleaned_cats = []
        for ci, cat in enumerate(cats):
            cname = sanitize_text(cat.get("name", ""), max_len=CATEGORY_NAME_MAX)
            if not cname:
                _err(f"category[{ci}] name required")
            items = cat.get("items", [])
            if not isinstance(items, list):
                _err(f"category[{ci}].items must be a list")
            cleaned_items = []
            for ii, it in enumerate(items):
                iname = sanitize_text(it.get("name", ""), max_len=ITEM_NAME_MAX)
                if not iname:
                    _err(f"item[{ci}.{ii}] name required")
                try:
                    price = int(it.get("price", 0))
                except (TypeError, ValueError):
                    _err(f"item[{ci}.{ii}] price must be integer")
                if price <= 0:
                    _err(f"item[{ci}.{ii}] price must be > 0")
                available = bool(it.get("available", True))
                cleaned_items.append({"name": iname, "price": price, "available": available})
            cleaned_cats.append({"name": cname, "items": cleaned_items})
        delivery_fee = menu.get("delivery_fee")
        if delivery_fee is not None:
            try:
                delivery_fee = int(delivery_fee)
            except (TypeError, ValueError):
                _err("delivery_fee must be integer")
        out["menu"] = {
            "shop_name": shop,
            "delivery_fee": delivery_fee,
            "delivery_area": sanitize_text(menu.get("delivery_area", ""), max_len=128),
            "categories": cleaned_cats,
        }

    # menu_v2 (published) + menu_v2_draft — WhatsApp-constraint-aware catalog
    for key in ("menu_v2", "menu_v2_draft"):
        if key in patch:
            if flow_mode != "order":
                _err(f"{key} only valid for order flow_mode")
            from app.menu_v2 import MenuV2Error, validate_menu_v2
            try:
                out[key] = validate_menu_v2(patch[key])
            except MenuV2Error as exc:
                _err(str(exc))

    # messages / messages_draft — full bot text catalog
    for key in ("messages", "messages_draft"):
        if key in patch:
            from app.messages import MessagesError, validate_messages_patch
            try:
                out[key] = validate_messages_patch(patch[key])
            except MessagesError as exc:
                _err(str(exc))

    # Pass-through fields (sanitized)
    for key in ("business_wa_id", "owner_whatsapp"):
        if key in patch:
            out[key] = sanitize_text(str(patch[key]), max_len=32)

    if "name" in patch:
        out["name"] = sanitize_text(patch["name"], max_len=256)

    if "sheet" in patch:
        sheet = patch["sheet"]
        if sheet is None:
            out["sheet"] = None
        elif isinstance(sheet, dict):
            from app.onboarding import parse_sheet_id
            gid = parse_sheet_id(str(sheet.get("gsheet_id") or sheet.get("url") or ""))
            if not gid and (sheet.get("gsheet_id") or sheet.get("url")):
                _err("sheet.gsheet_id / url invalid")
            out["sheet"] = {
                "gsheet_id": gid,
                "tab": sanitize_text(str(sheet.get("tab") or ""), max_len=128),
            }
        else:
            _err("sheet must be an object or null")

    if "onboarding" in patch and isinstance(patch["onboarding"], dict):
        # Allow storing wizard progress markers (booleans / short strings only)
        ob_in = patch["onboarding"]
        ob_out: dict[str, Any] = {}
        for k, v in ob_in.items():
            if isinstance(v, bool) or v is None:
                ob_out[k] = v
            elif isinstance(v, (int, float)):
                ob_out[k] = v
            elif isinstance(v, str):
                ob_out[k] = sanitize_text(v, max_len=256)
        out["onboarding"] = ob_out

    if "flow" in patch:
        if flow_mode != "lead":
            _err("flow only valid for lead flow_mode")
        from app.flow import FlowError, validate_flow
        try:
            out["flow"] = validate_flow(patch["flow"])
        except FlowError as exc:
            _err(str(exc))

    return out
