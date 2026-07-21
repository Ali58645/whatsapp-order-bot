"""
Vertical starter template registry.

JSON seeds live alongside this package (*.json). Loading a template populates
draft config only (messages_draft / menu_v2_draft); published config is untouched
until the owner publishes.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger("orderbot.templates")

TEMPLATES_DIR = Path(__file__).resolve().parent

# Legacy onboarding ids → new registry ids
LEGACY_ID_MAP = {
    "pos-lead": "pos_lead",
    "restaurant-order": "restaurant",
    "salon-booking": "salon_booking",
    "generic": "generic_lead",
}

_BUSINESS_RE = re.compile(r"\[Business\]", re.I)


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = copy.deepcopy(base)
    for key, val in (overlay or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = copy.deepcopy(val)
    return out


def resolve_template_id(template_id: str) -> str:
    tid = (template_id or "").strip()
    return LEGACY_ID_MAP.get(tid, tid)


def _load_raw(template_id: str) -> dict | None:
    tid = resolve_template_id(template_id)
    path = TEMPLATES_DIR / f"{tid}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.error(f"templates: failed to load {path.name}: {exc}")
        return None


def list_templates(*, flow_mode: str | None = None) -> list[dict]:
    """Metadata for UI pickers (no heavy config payloads)."""
    items: list[dict] = []
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning(f"templates: skip {path.name}: {exc}")
            continue
        fm = data.get("flow_mode") or "lead"
        if flow_mode and fm != flow_mode:
            continue
        items.append({
            "id": data.get("id") or path.stem,
            "name": data.get("name") or path.stem,
            "vertical": data.get("vertical") or path.stem,
            "flow_mode": fm,
            "blurb": data.get("blurb") or data.get("description") or "",
            "icon": data.get("icon") or "store",
            "languages": data.get("languages") or ["roman_urdu", "english"],
        })
    return items


def get_template(template_id: str) -> dict | None:
    return _load_raw(template_id)


def validate_template(data: dict) -> list[str]:
    """Return list of validation errors (empty = ok)."""
    errors: list[str] = []
    tid = data.get("id", "?")
    flow = data.get("flow_mode")
    if flow not in ("lead", "order"):
        errors.append(f"{tid}: flow_mode must be lead|order")
    cfg = data.get("config") or {}
    if not isinstance(cfg, dict):
        errors.append(f"{tid}: config must be object")
        return errors

    if flow == "order":
        menu = cfg.get("menu_v2")
        if not menu:
            errors.append(f"{tid}: order template missing menu_v2")
        else:
            try:
                from app.menu_v2 import validate_menu_v2
                validate_menu_v2(menu)
            except Exception as exc:
                errors.append(f"{tid}: menu_v2 — {exc}")
    else:
        overlay = cfg.get("messages_overlay") or {}
        inter = overlay.get("interactive") or {}
        for key in ("locations", "current_system"):
            rows = inter.get(key)
            if rows is not None and len(rows) > 10:
                errors.append(f"{tid}: interactive.{key} max 10 rows (got {len(rows)})")
        bt = inter.get("business_types") or []
        if len(bt) > 10:
            errors.append(f"{tid}: business_types max 10 rows")

    # Always ensure messages overlay (if present) merges cleanly with defaults
    try:
        from app.messages import default_messages, validate_messages_patch
        lang = cfg.get("greeting_language") or "roman_urdu"
        base = default_messages(lang)
        overlay = cfg.get("messages_overlay") or {}
        if overlay:
            merged = _deep_merge(base, overlay)
            validate_messages_patch(merged)
    except Exception as exc:
        errors.append(f"{tid}: messages — {exc}")

    return errors


def validate_all_templates() -> dict[str, list[str]]:
    """Validate every seed file; returns {id: [errors]}."""
    out: dict[str, list[str]] = {}
    for path in sorted(TEMPLATES_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        errs = validate_template(data)
        out[data.get("id") or path.stem] = errs
    return out


def _replace_business(obj: Any, business_name: str) -> Any:
    if isinstance(obj, str):
        return _BUSINESS_RE.sub(business_name or "Business", obj)
    if isinstance(obj, list):
        return [_replace_business(x, business_name) for x in obj]
    if isinstance(obj, dict):
        return {k: _replace_business(v, business_name) for k, v in obj.items()}
    return obj


def build_draft_patch(
    template_id: str,
    *,
    flow_mode: str | None = None,
    greeting_language: str = "roman_urdu",
    business_name: str = "",
) -> dict:
    """
    Build a config patch that only touches draft fields (+ shared facts/greeting).
    Never includes published messages / menu_v2.
    """
    from app.messages import default_messages

    data = get_template(template_id)
    if data is None:
        raise ValueError(f"Unknown template: {template_id}")

    tmpl_flow = data.get("flow_mode") or "lead"
    flow = flow_mode or tmpl_flow
    cfg_in = _replace_business(copy.deepcopy(data.get("config") or {}), business_name)
    lang = greeting_language or cfg_in.get("greeting_language") or "roman_urdu"
    if lang in ("en", "english"):
        lang = "en"
        # Prefer English greeting from i18n when available
        en = (cfg_in.get("i18n") or {}).get("english") or {}
        if en.get("greeting_text"):
            cfg_in["greeting_text"] = en["greeting_text"]
    else:
        lang = "roman_urdu"

    patch: dict[str, Any] = {
        "greeting_language": lang,
        "greeting_text": cfg_in.get("greeting_text") or "",
        "campaign_phrase": cfg_in.get("campaign_phrase") or data.get("name") or "Hello",
        "demo_slots": cfg_in.get("demo_slots") or ["Kal 11am", "Kal 4pm"],
        "facts_features": cfg_in.get("facts_features") or "",
        "facts_pricing_note": cfg_in.get("facts_pricing_note") or "",
        "facts_claims_note": cfg_in.get("facts_claims_note") or "",
        # Replace FAQ with template's list (empty clears prior vertical FAQs)
        "faq": cfg_in.get("faq") if isinstance(cfg_in.get("faq"), list) else [],
        "onboarding": {
            "template_id": data.get("id"),
            "content_set": True,
            "template_notes": cfg_in.get("template_notes") or "",
        },
    }

    # Messages draft: defaults + overlay (questions, buttons, reply texts)
    base = default_messages(lang)
    overlay = cfg_in.get("messages_overlay") or {}
    msgs = _deep_merge(base, overlay) if overlay else base
    if flow == "lead" and patch["greeting_text"]:
        msgs = {
            **msgs,
            "lead": {**msgs.get("lead", {}), "greeting_line": patch["greeting_text"]},
        }
    if flow == "order" and patch["greeting_text"]:
        msgs = {
            **msgs,
            "order": {**msgs.get("order", {}), "greeting": patch["greeting_text"]},
        }
    patch["messages_draft"] = msgs

    # Reset lead conversation steps to the classic built-in flow
    if flow == "lead":
        from app.flow import default_bahi_pos_flow

        patch["flow"] = default_bahi_pos_flow()
        # Clear owner greeting variants / image so template greeting is the source of truth
        patch["greeting_variants"] = []
        patch["greeting_image_url"] = ""
        patch["greeting_blocks"] = []

    if flow == "order":
        menu = cfg_in.get("menu_v2")
        if menu:
            from app.menu_v2 import validate_menu_v2
            menu = validate_menu_v2(menu)
            if patch["greeting_text"]:
                menu = {
                    **menu,
                    "settings": {
                        **menu.get("settings", {}),
                        "greeting_text": patch["greeting_text"],
                    },
                }
            patch["menu_v2_draft"] = menu
            # Legacy menu for compat — leaf categories only (parents have no items)
            leaf_cats = [
                c for c in (menu.get("categories") or [])
                if not any(
                    (x.get("parent_id") or "") == c.get("id")
                    for x in (menu.get("categories") or [])
                )
            ]
            # WhatsApp legacy menu row limit — keep first 10 leaves
            leaf_cats = leaf_cats[:10]
            patch["menu"] = {
                "shop_name": business_name or "Shop",
                "delivery_fee": (menu.get("settings") or {}).get("delivery", {}).get("charge", 100),
                "delivery_area": (menu.get("settings") or {}).get("delivery", {}).get("area_note", ""),
                "categories": [
                    {
                        "name": c.get("name", "Items"),
                        "items": [
                            {"name": it.get("name", "Item"), "price": it.get("price", 0)}
                            for it in (menu.get("items") or [])
                            if it.get("category_id") == c.get("id")
                        ],
                    }
                    for c in leaf_cats
                ],
            }
        else:
            from app.menu_v2 import empty_menu_v2
            patch["menu_v2_draft"] = empty_menu_v2()

    return patch


def apply_template_full_config(
    config: dict,
    *,
    template_id: str,
    flow_mode: str,
    greeting_language: str = "roman_urdu",
    business_name: str = "",
    publish_drafts: bool = True,
) -> dict:
    """
    For onboarding create: apply template into a full config (draft + published
    when publish_drafts=True so a brand-new tenant is immediately usable).
    """
    patch = build_draft_patch(
        template_id,
        flow_mode=flow_mode,
        greeting_language=greeting_language,
        business_name=business_name,
    )
    cfg = dict(config or {})
    cfg.update(patch)
    if publish_drafts:
        if "messages_draft" in patch:
            cfg["messages"] = copy.deepcopy(patch["messages_draft"])
        if "menu_v2_draft" in patch:
            cfg["menu_v2"] = copy.deepcopy(patch["menu_v2_draft"])
    return cfg
