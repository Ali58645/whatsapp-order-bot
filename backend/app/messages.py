"""
Tenant message catalog — every bot-authored string is data.

Published:  tenant.config["messages"]
Draft:      tenant.config["messages_draft"]

Template variables use {{name}} syntax. Unknown vars rejected at save time.
Runtime uses render() with fallback to DEFAULTS when a key is missing.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from app.prompt_data import sanitize_text

# WhatsApp surface limits
BODY_MAX = 1024
BUTTON_TITLE_MAX = 20
ROW_TITLE_MAX = 24
# Owner-facing editor allows longer labels; WhatsApp truncates on send.
OPTION_TITLE_EDIT_MAX = 50
OPTION_ROWS_MAX = 10
ROWS_MAX = 10  # WhatsApp list rows
ROW_DESC_MAX = 72

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")

# Variables allowed per message key
ALLOWED_VARS: dict[str, set[str]] = {
    # Lead
    "lead.greeting_line": set(),
    "lead.value_line": set(),
    "lead.q_business_name": set(),
    "lead.q_business_type": set(),
    "lead.q_locations": set(),
    "lead.q_current_system": set(),
    "lead.q_scheduling": set(),
    "lead.q_custom_slot": set(),
    "lead.confirm_slot": {"slot"},
    "lead.pricing_text": set(),
    "lead.info_text": set(),
    "lead.price_deflect_mid": {"current_question"},
    "lead.media_redirect_suffix": set(),
    "lead.handoff": set(),
    "lead.reprompt": {"current_question"},
    "lead.error_fallback": set(),
    "lead.unsupported_media": set(),
    "lead.entry_demo_suffix": set(),
    "lead.ack_business_name": {"name"},
    "lead.owner_card_title": set(),
    "lead.owner_card_body": {
        "business_name", "business_type", "locations", "current_system",
        "slot", "source", "referral_headline", "sender",
    },
    # Order
    "order.greeting": set(),
    "order.menu_button_label": set(),
    "order.category_choose": set(),
    "order.item_choose": {"category"},
    "order.item_choose_flat": set(),
    "order.modifier_prompt": {"item", "modifier"},
    "order.quantity_ask": {"item"},
    "order.more_items_ask": set(),
    "order.btn_more_yes": set(),
    "order.btn_more_no": set(),
    "order.btn_confirm": set(),
    "order.btn_cancel": set(),
    "order.confirm_note": set(),
    "order.cart_header": set(),
    "order.delivery_line": {"amount"},
    "order.delivery_free": set(),
    "order.total_line": {"total"},
    "order.order_received": set(),
    "order.order_cancel": set(),
    "order.nudge_menu": set(),
    "order.item_not_found": set(),
    "order.cart_empty": set(),
    "order.qty_invalid": set(),
    "order.pick_item_first": set(),
    "order.more_row_title": set(),
    "order.owner_slip_title": set(),
    "order.owner_slip_body": {"items", "total", "address", "customer"},
    "order.owner_fail_customer": set(),
    "order.reset_done": set(),
    "order.text_only": set(),
    "order.error_fallback": set(),
}

# Interactive option validation limits
INTERACTIVE_KEYS = ("business_types", "locations", "current_system")


class MessagesError(ValueError):
    pass


def _defaults_ur() -> dict:
    return {
        "lead": {
            "greeting_line": "Assalam o Alaikum 🙏 Aap ki dilchaspi ka shukriya.",
            "value_line": (
                "Hum aap ki madad ke liye yahan hain — thori si info dein taake "
                "hum aap ko sahi guide kar saken."
            ),
            "q_business_name": "Barah-e-karam apna naam ya company ka naam farmaayein.",
            "q_business_type": "Aap ko kaunsi service / option chahiye? Neeche se muntakhib karein.",
            "q_locations": "Aap kahan based hain ya kis area mein service chahiye?",
            "q_current_system": "Abhi aap ka process / system kaisa hai?",
            "q_scheduling": (
                "Hamari team aap ko mukammal walkthrough dikhana chahti hai.\n"
                "Demo / call ke liye kaunsa waqt aap ke liye munasib rahega?"
            ),
            "q_custom_slot": "Barah-e-karam apni pasandida tarikh aur waqt likh kar bataayein.",
            "confirm_slot": (
                "Shukriya. Aap ka slot {{slot}} ke liye booked ho gaya hai. "
                "Hamari team aap se is number par rabta karegi."
            ),
            "pricing_text": (
                "Pricing aap ki zarooriyaat ke mutabiq hoti hai. "
                "Hamari team call / demo ke dauran aap ko mukhtasar quote degi. "
                "Barah-e-karam ek time book karein."
            ),
            "info_text": (
                "Hum businesses ko WhatsApp aur automation ke zariye customers se "
                "better connect karne mein madad karte hain. "
                "Neeche jawab dein — team aap ki guide karegi."
            ),
            "price_deflect_mid": (
                "Pricing aap ki zarooriyaat ke mutabiq tay hoti hai — "
                "sahi quote call / demo mein milti hai. {{current_question}}"
            ),
            "media_redirect_suffix": "Barah-e-karam apna jawab text mein likhein.",
            "handoff": "Hamari team jald aap se rabta karegi. Shukriya apna waqt dene ka.",
            "reprompt": "Maazrat, jawab samajh nahi aaya. {{current_question}}",
            "error_fallback": (
                "Maafi chahte hain, abhi ek masla aa gaya hai. "
                "Thodi der baad dobara koshish farmaayein."
            ),
            "unsupported_media": "Barah-e-karam apna jawab text mein likhein.",
            "entry_demo_suffix": "Hamari team aap ko time choose karne mein madad karegi:",
            "ack_business_name": "Shukriya. Aap ki info record ho gayi.",
            "owner_card_title": "🔔 *NEW LEAD*",
            "owner_card_body": (
                "Business: {{business_name}} ({{business_type}})\n"
                "Locations: {{locations}}\n"
                "Current system: {{current_system}}\n"
                "Demo: {{slot}}\n"
                "Source: {{source}}\n"
                "Ad: {{referral_headline}}\n"
                "Number: wa.me/{{sender}}"
            ),
        },
        "order": {
            "greeting": "Assalam o Alaikum! Menu dekhne ke liye neeche tap karein.",
            "menu_button_label": "Menu dekhein",
            "category_choose": "Category choose karein:",
            "item_choose": "{{category}} — item choose karein:",
            "item_choose_flat": "Item choose karein:",
            "modifier_prompt": "{{item}} — {{modifier}} choose karein:",
            "quantity_ask": "{{item}} — kitni quantity? (1-9)",
            "more_items_ask": "Aur kuch add karein?",
            "btn_more_yes": "Haan",
            "btn_more_no": "Nahi, bas",
            "btn_confirm": "Confirm",
            "btn_cancel": "Cancel",
            "confirm_note": "Confirm karein?",
            "cart_header": "Aapka order:",
            "delivery_line": "Delivery: {{amount}}",
            "delivery_free": "Delivery: Free",
            "total_line": "Total: {{total}}",
            "order_received": "Shukriya! Order confirm ho gaya.",
            "order_cancel": "Order cancel. 'menu' likhein naya order ke liye.",
            "nudge_menu": "Menu se choose karein, ya 'menu' likhein.",
            "item_not_found": "Item nahi mila. Dobara try karein.",
            "cart_empty": "Cart khali hai. Menu se item choose karein.",
            "qty_invalid": "1 se 9 tak number likhein.",
            "pick_item_first": "Item select karein pehle.",
            "more_row_title": "Aur dekhein →",
            "owner_slip_title": "🔔 *NEW ORDER*",
            "owner_slip_body": (
                "{{items}}\n\n*Total: Rs. {{total}}*\n"
                "📍 {{address}}\n📱 Customer: +{{customer}}"
            ),
            "owner_fail_customer": (
                "Aapka order record ho gaya hai, hum thodi der mein confirm karenge. Shukriya! 🙏"
            ),
            "reset_done": "Order reset. What would you like to order?",
            "text_only": "Please send your order as a text message.",
            "error_fallback": "Sorry, an issue occurred. Please try again.",
        },
        "interactive": {
            "select_button_label": "Muntakhib karein",
            "slot_other_label": "Koi aur time",
            "business_types": [
                {"id": "svc_1", "title": "Consultation", "description": "Advice / quote", "value": "Consultation"},
                {"id": "svc_2", "title": "Demo / Call", "description": "Live walkthrough", "value": "Demo / Call"},
                {"id": "svc_3", "title": "Pricing", "description": "Packages", "value": "Pricing"},
                {"id": "svc_4", "title": "Support", "description": "Help", "value": "Support"},
                {"id": "other", "title": "Other", "description": "Kuch aur", "value": "Other"},
            ],
            "locations": [
                {"id": "loc_1", "title": "1", "value": "1"},
                {"id": "loc_2_5", "title": "2-5", "value": "2-5"},
                {"id": "loc_5plus", "title": "5+", "value": "5+"},
            ],
            "current_system": [
                {"id": "sys_manual", "title": "Manual", "sheet_value": "Manual"},
                {"id": "sys_software", "title": "Software / tools", "sheet_value": "Software"},
                {"id": "sys_none", "title": "Kuch nahi", "sheet_value": "No System"},
            ],
        },
    }


def _defaults_en() -> dict:
    d = _defaults_ur()
    d["lead"].update({
        "greeting_line": "Welcome 🙏 Thank you for your interest.",
        "value_line": (
            "We're here to help — share a few details so we can guide you properly."
        ),
        "q_business_name": "Kindly share your name or company name.",
        "q_business_type": "Which service or option do you need? Please select below.",
        "q_locations": "Where are you based, or which area do you need service in?",
        "q_current_system": "How do you currently handle this process?",
        "q_scheduling": (
            "Our team would love to walk you through everything.\n"
            "Which time works best for a demo or call?"
        ),
        "q_custom_slot": "Kindly specify your preferred date and time.",
        "confirm_slot": (
            "Thank you. Your slot has been booked for {{slot}}. "
            "Our team will contact you on this number."
        ),
        "pricing_text": (
            "Pricing depends on your requirements. "
            "Our team will share a quote during the call or demo. "
            "Please book a time so we can guide you."
        ),
        "info_text": (
            "We help businesses connect with customers through WhatsApp and automation. "
            "Answer below and our team will guide you."
        ),
        "price_deflect_mid": (
            "Pricing depends on your requirements and will be shared "
            "during the call or demo. {{current_question}}"
        ),
        "media_redirect_suffix": "Kindly respond in text so we may assist you properly.",
        "handoff": "Our team will be in touch with you shortly. Thank you for your time.",
        "reprompt": "We apologise — that response was not recognised. {{current_question}}",
        "error_fallback": "We apologise for the inconvenience. Please try again in a moment.",
        "unsupported_media": "Kindly respond in text so we may assist you.",
        "entry_demo_suffix": "Our team will help you select a time:",
        "ack_business_name": "Thank you. Your details have been noted.",
        "owner_card_title": "🔔 *NEW LEAD*",
    })
    d["interactive"]["select_button_label"] = "Select"
    d["interactive"]["slot_other_label"] = "Another time"
    for row in d["interactive"]["business_types"]:
        row.setdefault("value", row["title"])
        if str(row.get("description") or "").lower() in ("kuch aur",):
            row["description"] = "Something else"
    for row in d["interactive"]["current_system"]:
        if str(row.get("title") or "").lower() in ("kuch nahi",):
            row["title"] = "Nothing yet"
    d["order"].update(
        {
            "greeting": "Welcome! Tap below to browse the menu.",
            "menu_button_label": "View menu",
            "category_choose": "Please choose a category:",
            "item_choose": "{{category}} — please choose an item:",
            "item_choose_flat": "Please choose an item:",
            "modifier_prompt": "{{item}} — please choose {{modifier}}:",
            "quantity_ask": "{{item}} — how many? (1-9)",
            "more_items_ask": "Add anything else?",
            "btn_more_yes": "Yes",
            "btn_more_no": "No, that's all",
            "btn_confirm": "Confirm",
            "btn_cancel": "Cancel",
            "confirm_note": "Confirm order?",
            "cart_header": "Your order:",
            "delivery_line": "Delivery: {{amount}}",
            "delivery_free": "Delivery: Free",
            "total_line": "Total: {{total}}",
            "order_received": "Thank you! Your order is confirmed.",
            "order_cancel": "Order cancelled. Type 'menu' to start a new order.",
            "nudge_menu": "Please choose from the menu, or type 'menu'.",
            "item_not_found": "Item not found. Please try again.",
            "cart_empty": "Your cart is empty. Please choose an item from the menu.",
            "qty_invalid": "Please enter a number from 1 to 9.",
            "pick_item_first": "Please select an item first.",
            "more_row_title": "See more →",
            "owner_slip_title": "🔔 *NEW ORDER*",
            "owner_fail_customer": (
                "Your order has been recorded. We'll confirm shortly. Thank you!"
            ),
            "reset_done": "Order reset. What would you like to order?",
            "text_only": "Please send your order as a text message.",
            "error_fallback": "Sorry, an issue occurred. Please try again.",
        }
    )
    return d


def localize_demo_slots(slots: list | None, lang: str) -> list[str]:
    """Translate common Kal/Tomorrow demo slot labels for the selected language."""
    import re

    lang_key = "en" if lang in ("en", "english") else "roman_urdu"
    raw = [str(s or "").strip() for s in (slots or [])][:2]
    if lang_key == "en":
        mapped = []
        for t in raw:
            t = re.sub(r"(?i)\bkal\b", "Tomorrow", t)
            t = re.sub(r"(?i)\baaj\b", "Today", t)
            mapped.append(t[:64] if t else "")
        defaults = ["Tomorrow 11am", "Tomorrow 4pm"]
    else:
        mapped = []
        for t in raw:
            t = re.sub(r"(?i)\btomorrow\b", "Kal", t)
            t = re.sub(r"(?i)\btoday\b", "Aaj", t)
            mapped.append(t[:64] if t else "")
        defaults = ["Kal 11am", "Kal 4pm"]
    if not mapped or not any(mapped):
        mapped = list(defaults)
    while len(mapped) < 2:
        mapped.append(defaults[len(mapped)])
    return mapped[:2]


def default_messages(lang: str = "roman_urdu") -> dict:
    """Full default catalog. lang only affects which defaults are offered."""
    base = _defaults_en() if lang in ("en", "english") else _defaults_ur()
    return {
        "lang_hint": "en" if lang in ("en", "english") else "roman_urdu",
        **base,
    }


def extract_vars(template: str) -> set[str]:
    return set(_VAR_RE.findall(template or ""))


def render(template: str, variables: Optional[dict] = None, *, max_len: int | None = None) -> str:
    """Substitute {{vars}}. Missing vars become empty string."""
    variables = variables or {}

    def _sub(m: re.Match) -> str:
        key = m.group(1)
        val = variables.get(key)
        return "" if val is None else str(val)

    out = _VAR_RE.sub(_sub, template or "")
    # Drop empty "Ad: \n" style lines that only had optional vars
    lines = []
    for line in out.split("\n"):
        stripped = line.strip()
        if stripped.endswith(":") and len(stripped) < 40:
            # keep structural headers; skip trailing-empty labels like "Ad:"
            if stripped.lower() in ("ad:", "source:") and not any(
                variables.get(k) for k in ("referral_headline", "source")
            ):
                continue
        if stripped == "Ad:" or (stripped.startswith("Ad:") and len(stripped) <= 4):
            continue
        lines.append(line)
    out = "\n".join(lines).strip()
    if max_len is not None and len(out) > max_len:
        out = out[:max_len]
    return out


def get_msg(catalog: dict | None, dotted_key: str, *, lang_hint: str = "roman_urdu") -> str:
    """
    Resolve dotted key like 'lead.greeting_line' from catalog with default fallback.
    """
    defaults = default_messages(lang_hint)
    parts = dotted_key.split(".", 1)
    if len(parts) != 2:
        return ""
    section, key = parts
    custom = ((catalog or {}).get(section) or {}).get(key)
    if custom is not None and str(custom).strip() != "":
        return str(custom)
    return str(((defaults.get(section) or {}).get(key)) or "")


def get_interactive(catalog: dict | None, key: str, *, lang_hint: str = "roman_urdu") -> Any:
    defaults = default_messages(lang_hint)
    custom = ((catalog or {}).get("interactive") or {}).get(key)
    if custom is not None:
        return custom
    return (defaults.get("interactive") or {}).get(key)


class MessageResolver:
    """Per-tenant resolver — bind once from Tenant."""

    def __init__(self, tenant=None, *, use_draft: bool = False):
        self.tenant = tenant
        cfg = {}
        if tenant is not None:
            # Prefer published messages; draft only when explicitly requested
            raw_cfg = getattr(tenant, "_raw_config", None)
            if isinstance(raw_cfg, dict):
                cfg = raw_cfg
            messages = getattr(tenant, "messages", None)
            if use_draft and isinstance(cfg, dict) and cfg.get("messages_draft"):
                self.catalog = cfg["messages_draft"]
            elif messages:
                self.catalog = messages if isinstance(messages, dict) else {}
            elif isinstance(cfg, dict) and cfg.get("messages"):
                self.catalog = cfg["messages"]
            else:
                self.catalog = {}
        else:
            self.catalog = {}
        lang = getattr(tenant, "greeting_language", None) or (self.catalog.get("lang_hint") or "roman_urdu")
        self.lang_hint = "en" if lang in ("en", "english") else "roman_urdu"

    def text(self, key: str, variables: Optional[dict] = None, *, max_len: int | None = BODY_MAX) -> str:
        tmpl = get_msg(self.catalog, key, lang_hint=self.lang_hint)
        return render(tmpl, variables, max_len=max_len)

    def button(self, key: str, variables: Optional[dict] = None) -> str:
        return self.text(key, variables, max_len=BUTTON_TITLE_MAX)

    def interactive(self, key: str) -> Any:
        return get_interactive(self.catalog, key, lang_hint=self.lang_hint)


def validate_messages_patch(raw: Any) -> dict:
    """Validate + sanitize a messages / messages_draft object."""
    if raw is None:
        raise MessagesError("messages must be an object")
    if not isinstance(raw, dict):
        raise MessagesError("messages must be an object")

    lang = str(raw.get("lang_hint") or "roman_urdu").strip().lower()
    if lang in ("en", "english"):
        lang = "en"
    else:
        lang = "roman_urdu"
    defaults = default_messages(lang)
    out: dict[str, Any] = {"lang_hint": lang}

    for section in ("lead", "order"):
        sec_in = raw.get(section) or {}
        if not isinstance(sec_in, dict):
            raise MessagesError(f"messages.{section} must be an object")
        sec_out: dict[str, str] = {}
        default_sec = defaults.get(section) or {}
        # Merge: start from defaults so missing keys keep defaults on save
        for key, default_val in default_sec.items():
            val = sec_in.get(key, default_val)
            raw_s = str(val)
            dotted = f"{section}.{key}"
            # Length by surface — reject before truncate so save fails loudly
            if key.startswith("btn_") or key in (
                "menu_button_label", "btn_more_yes", "btn_more_no",
                "btn_confirm", "btn_cancel", "more_row_title",
            ):
                if len(raw_s) > BUTTON_TITLE_MAX:
                    raise MessagesError(f"{dotted}: max {BUTTON_TITLE_MAX} chars (button)")
            elif len(raw_s) > BODY_MAX:
                raise MessagesError(f"{dotted}: max {BODY_MAX} chars")
            s = sanitize_text(raw_s, max_len=BODY_MAX)
            allowed = ALLOWED_VARS.get(dotted, set())
            found = extract_vars(s)
            unknown = found - allowed
            if unknown:
                raise MessagesError(
                    f"{dotted}: unknown variables {sorted(unknown)}; allowed={sorted(allowed)}"
                )
            sec_out[key] = s
        # Also accept extra known keys from input that are in ALLOWED_VARS
        for key, val in sec_in.items():
            if key in sec_out:
                continue
            dotted = f"{section}.{key}"
            if dotted not in ALLOWED_VARS:
                continue
            s = sanitize_text(str(val), max_len=BODY_MAX)
            found = extract_vars(s)
            unknown = found - ALLOWED_VARS[dotted]
            if unknown:
                raise MessagesError(f"{dotted}: unknown variables {sorted(unknown)}")
            sec_out[key] = s
        out[section] = sec_out

    # Interactive
    inter_in = raw.get("interactive") or {}
    if not isinstance(inter_in, dict):
        raise MessagesError("messages.interactive must be an object")
    inter_def = defaults["interactive"]
    inter_out: dict[str, Any] = {}
    for label_key in ("select_button_label", "slot_other_label"):
        s = sanitize_text(
            str(inter_in.get(label_key, inter_def[label_key])),
            max_len=BUTTON_TITLE_MAX,
        )
        if len(s) > BUTTON_TITLE_MAX:
            raise MessagesError(f"interactive.{label_key}: max {BUTTON_TITLE_MAX}")
        inter_out[label_key] = s or inter_def[label_key]

    # business_types — list rows (empty titles stripped; order preserved)
    btypes_raw = inter_in.get("business_types", inter_def["business_types"])
    if not isinstance(btypes_raw, list):
        raise MessagesError("interactive.business_types required")
    btypes = [
        r for r in btypes_raw
        if isinstance(r, dict) and str(r.get("title", "")).strip()
    ]
    if not btypes:
        raise MessagesError("interactive.business_types required")
    if len(btypes) > OPTION_ROWS_MAX:
        raise MessagesError(f"interactive.business_types max {OPTION_ROWS_MAX} rows")
    cleaned_bt = []
    seen_titles: set[str] = set()
    for i, row in enumerate(btypes):
        rid = sanitize_text(str(row.get("id") or f"bt_{i}"), max_len=64)
        title_raw = str(row.get("title", ""))
        if len(title_raw) > OPTION_TITLE_EDIT_MAX:
            raise MessagesError(f"business_types[{i}].title max {OPTION_TITLE_EDIT_MAX}")
        title = sanitize_text(title_raw, max_len=OPTION_TITLE_EDIT_MAX)
        desc = sanitize_text(str(row.get("description", "")), max_len=ROW_DESC_MAX)
        value = sanitize_text(str(row.get("value", title) or title), max_len=64)
        if not rid or not title:
            raise MessagesError(f"business_types[{i}] id and title required")
        key = title.lower()
        if key in seen_titles:
            raise MessagesError(f"business_types: duplicate label {title!r}")
        seen_titles.add(key)
        cleaned_bt.append({
            "id": rid,
            "title": title,
            "description": desc,
            "value": value or title,
        })
        nk = sanitize_text(str(row.get("next_key") or ""), max_len=64).upper().replace(" ", "_")
        if nk:
            cleaned_bt[-1]["next_key"] = nk
    inter_out["business_types"] = cleaned_bt

    for set_key, value_field in (("locations", "value"), ("current_system", "sheet_value")):
        rows_raw = inter_in.get(set_key, inter_def[set_key])
        if not isinstance(rows_raw, list):
            raise MessagesError(f"interactive.{set_key} required")
        rows = [
            r for r in rows_raw
            if isinstance(r, dict) and str(r.get("title", "")).strip()
        ]
        if not rows:
            raise MessagesError(f"interactive.{set_key} required")
        if len(rows) > OPTION_ROWS_MAX:
            raise MessagesError(f"interactive.{set_key} max {OPTION_ROWS_MAX} rows")
        cleaned = []
        seen: set[str] = set()
        for i, row in enumerate(rows):
            rid = sanitize_text(str(row.get("id") or f"{set_key}_{i}"), max_len=64)
            title_raw = str(row.get("title", ""))
            if len(title_raw) > OPTION_TITLE_EDIT_MAX:
                raise MessagesError(f"{set_key}[{i}].title max {OPTION_TITLE_EDIT_MAX}")
            title = sanitize_text(title_raw, max_len=OPTION_TITLE_EDIT_MAX)
            val = sanitize_text(str(row.get(value_field, title) or title), max_len=64)
            if not rid or not title:
                raise MessagesError(f"{set_key}[{i}] id and title required")
            key = title.lower()
            if key in seen:
                raise MessagesError(f"{set_key}: duplicate label {title!r}")
            seen.add(key)
            item = {"id": rid, "title": title, value_field: val or title}
            nk = sanitize_text(str(row.get("next_key") or ""), max_len=64).upper().replace(" ", "_")
            if nk:
                item["next_key"] = nk
            cleaned.append(item)
        inter_out[set_key] = cleaned

    out["interactive"] = inter_out
    return out


def seed_messages_into_config(config: dict, *, flow_mode: str, greeting_language: str = "roman_urdu") -> dict:
    """
    Ensure config has messages (+ draft) matching today's Bahi POS defaults.
    Preserves existing messages if present. Zero behavior change when keys match defaults.
    """
    cfg = dict(config or {})
    lang = greeting_language or cfg.get("greeting_language") or "roman_urdu"
    defaults = default_messages(lang)
    # Overlay custom greeting_text into lead greeting if present and messages missing
    if not cfg.get("messages"):
        msgs = defaults
        custom = (cfg.get("greeting_text") or "").strip()
        if custom and flow_mode == "lead":
            msgs = {**defaults, "lead": {**defaults["lead"], "greeting_line": custom}}
        cfg["messages"] = msgs
        cfg["messages_draft"] = msgs
    elif not cfg.get("messages_draft"):
        cfg["messages_draft"] = cfg["messages"]
    return cfg
