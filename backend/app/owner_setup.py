"""
Owner first-run business setup — collect profile answers, apply a vertical
template, fill knowledge_base + business_hours, and go live in one shot.
"""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any, Optional

from app.knowledge import empty_knowledge_base, validate_knowledge_base
from app.onboarding import patch_onboarding
from app.owner_tools import validate_business_hours
from app.prompt_data import sanitize_text
from app.templates import (
    build_draft_patch,
    get_template,
    list_templates,
    resolve_template_id,
)

_DAY_LABELS = (
    ("mon", "Monday"),
    ("tue", "Tuesday"),
    ("wed", "Wednesday"),
    ("thu", "Thursday"),
    ("fri", "Friday"),
    ("sat", "Saturday"),
    ("sun", "Sunday"),
)

_PHONE_RE = re.compile(r"[\d+]{8,}")


def resolve_setup_template(
    *,
    template_id: str | None,
    vertical: str | None,
    flow_mode: str,
) -> str:
    """Map template_id / vertical → registry id for the requested flow_mode."""
    mode = flow_mode if flow_mode in ("lead", "order") else "lead"
    items = list_templates(flow_mode=mode)

    if template_id:
        tid = resolve_template_id(template_id)
        tmpl = get_template(tid)
        if tmpl and (tmpl.get("flow_mode") or "lead") == mode:
            return tid
        if tmpl:
            vertical = vertical or tmpl.get("vertical")

    vert = (vertical or "").strip().lower()
    if vert:
        for it in items:
            if (it.get("vertical") or "").lower() == vert:
                return it["id"]
        # Allow passing template stem as vertical
        for it in items:
            if it["id"] == vert or it["id"].replace("_", "") == vert.replace("_", ""):
                return it["id"]

    return "generic_order" if mode == "order" else "generic_lead"


def format_hours_for_knowledge(bh: dict) -> str:
    """Human-readable hours for knowledge_base.sections.business_hours."""
    if not bh or not bh.get("enabled"):
        return "Open most days — message us anytime and we will confirm current hours."
    tz = str(bh.get("timezone") or "Asia/Karachi")
    lines = [f"Timezone: {tz}"]
    days = bh.get("days") or {}
    for key, label in _DAY_LABELS:
        slots = days.get(key) or []
        if not slots:
            lines.append(f"{label}: Closed")
        else:
            parts = ", ".join(f"{a}–{b}" for a, b in slots if len(a) and len(b))
            lines.append(f"{label}: {parts}" if parts else f"{label}: Closed")
    return "\n".join(lines)


def build_knowledge_from_answers(
    *,
    business_name: str,
    overview: str = "",
    offer: str = "",
    location: str = "",
    contact: str = "",
    business_hours: dict | None = None,
    extra: str = "",
) -> dict[str, Any]:
    """Build a published knowledge_base from short owner answers (no LLM)."""
    name = sanitize_text(business_name, max_len=256) or "Business"
    overview_s = sanitize_text(overview, max_len=4000)
    offer_s = sanitize_text(offer, max_len=4000)
    location_s = sanitize_text(location, max_len=2000)
    contact_s = sanitize_text(contact, max_len=2000)
    extra_s = sanitize_text(extra, max_len=4000)
    hours_text = format_hours_for_knowledge(business_hours or {})

    if not overview_s:
        overview_s = f"{name} serves customers on WhatsApp."

    sections = {k: "" for k in empty_knowledge_base()["sections"]}
    sections["overview"] = overview_s
    sections["products_services"] = offer_s
    sections["business_hours"] = hours_text
    sections["locations"] = location_s
    sections["contact"] = contact_s or f"WhatsApp: contact {name}"
    sections["additional"] = extra_s

    parts = [
        f"## {name}",
        overview_s,
    ]
    if offer_s:
        parts.append(f"Products and services:\n{offer_s}")
    if location_s:
        parts.append(f"Location / service area:\n{location_s}")
    if contact_s:
        parts.append(f"Contact:\n{contact_s}")
    parts.append(f"Business hours:\n{hours_text}")
    if extra_s:
        parts.append(extra_s)

    kb = validate_knowledge_base(
        {
            **empty_knowledge_base(),
            "enabled": True,
            "status": "published",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "sections": sections,
            "complete_knowledge": "\n\n".join(parts),
            "faq": [],
        }
    )
    return kb


def greeting_options(
    template_id: str,
    *,
    business_name: str,
    greeting_language: str = "roman_urdu",
    flow_mode: str | None = None,
    overview: str = "",
) -> list[dict[str, str]]:
    """2–3 greeting suggestions — strictly in the selected language only."""
    name = sanitize_text(business_name, max_len=80) or "Business"
    lang = greeting_language or "roman_urdu"
    en = lang in ("en", "english")
    tmpl = get_template(template_id) or {}
    mode = flow_mode or tmpl.get("flow_mode") or "lead"
    overview_s = sanitize_text(overview, max_len=160)
    options: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(oid: str, text: str) -> None:
        t = (text or "").strip()
        if not t or t.lower() in seen:
            return
        seen.add(t.lower())
        options.append({"id": oid, "text": t[:900]})

    # Prefer template greeting only when it matches the selected language
    patch = build_draft_patch(
        template_id,
        flow_mode=mode,
        greeting_language="en" if en else "roman_urdu",
        business_name=name,
    )
    primary = _scrub_branded((patch.get("greeting_text") or "").strip(), name)
    if primary:
        looks_ur = bool(
            re.search(
                r"\b(aap|kya|hai|mein|kaise|shukriya|assalam|farmaayein|karein|dilchaspi|muntakhib)\b",
                primary,
                re.I,
            )
        )
        looks_en = bool(
            re.search(r"\b(welcome|thanks|please|how can|hello)\b", primary, re.I)
        )
        # Strict: English never keeps Assalam / Roman Urdu greetings
        if en and looks_en and not looks_ur:
            _add("template", primary)
        if not en and (looks_ur or not looks_en):
            _add("template", primary)

    if mode == "order":
        if en:
            _add("short", f"Welcome to {name}! Message us to browse the menu and place your order.")
            _add("friendly", f"Hi! You're chatting with {name}. Tap below or reply to see the menu.")
            if overview_s:
                _add("overview", f"Welcome to {name}! {overview_s}")
        else:
            _add(
                "short",
                f"Assalam o Alaikum! {name} mein khush amdeed. Menu dekhne ke liye message karein.",
            )
            _add(
                "friendly",
                f"Assalam o Alaikum! Aap {name} se baat kar rahe hain. Menu ke liye message karein.",
            )
            if overview_s:
                _add("overview", f"Assalam o Alaikum! {name} — {overview_s}")
    else:
        if en:
            _add("short", f"Welcome to {name}! How can we help you today?")
            _add(
                "thanks",
                f"Thanks for contacting {name}. Reply below and our team will guide you.",
            )
            if overview_s:
                _add("overview", f"Welcome to {name}! {overview_s}")
        else:
            _add(
                "short",
                f"Assalam o Alaikum! {name} mein khush amdeed. Kaise madad kar sakte hain?",
            )
            _add(
                "thanks",
                f"Assalam o Alaikum! {name} mein aap ki dilchaspi ka shukriya. Neeche jawab dein.",
            )
            if overview_s:
                _add("overview", f"Assalam o Alaikum! {name} — {overview_s}")

    return options[:3]


def _offer_button_rows(offer: str, *, lang: str) -> list[dict[str, str]]:
    """Split owner offer text into WhatsApp list rows (max 10)."""
    raw = offer or ""
    parts: list[str] = []
    for chunk in re.split(r"[\n,;/|]+", raw):
        item = sanitize_text(chunk, max_len=48).strip(" -•*")
        if len(item) >= 2:
            parts.append(item)
    # Also try "and" / "aur" splits for short lists
    if len(parts) <= 1 and raw.strip():
        for chunk in re.split(r"\s+(?:and|aur|&)\s+", raw, flags=re.I):
            item = sanitize_text(chunk, max_len=48).strip(" -•*")
            if len(item) >= 2 and item not in parts:
                parts.append(item)
    rows: list[dict[str, str]] = []
    for i, title in enumerate(parts[:9]):
        short = title[:24]
        rows.append(
            {
                "id": f"svc_{i+1}",
                "title": short,
                "description": title[:60] if title != short else (title[:40] or "Option"),
                "value": title[:80],
            }
        )
    if not rows:
        if lang in ("en", "english"):
            rows = [
                {"id": "svc_1", "title": "Consultation", "description": "Advice", "value": "Consultation"},
                {"id": "svc_2", "title": "Demo / Call", "description": "Walkthrough", "value": "Demo / Call"},
                {"id": "svc_3", "title": "Pricing", "description": "Packages", "value": "Pricing"},
                {"id": "other", "title": "Other", "description": "Something else", "value": "Other"},
            ]
        else:
            rows = [
                {"id": "svc_1", "title": "Consultation", "description": "Advice", "value": "Consultation"},
                {"id": "svc_2", "title": "Demo / Call", "description": "Walkthrough", "value": "Demo / Call"},
                {"id": "svc_3", "title": "Pricing", "description": "Packages", "value": "Pricing"},
                {"id": "other", "title": "Other", "description": "Kuch aur", "value": "Other"},
            ]
    else:
        rows.append(
            {
                "id": "other",
                "title": "Other" if lang in ("en", "english") else "Other",
                "description": "Something else" if lang in ("en", "english") else "Kuch aur",
                "value": "Other",
            }
        )
    return rows[:10]


def _scrub_branded(text: str, business_name: str) -> str:
    """Replace legacy Bahi POS / [Business] placeholders with the owner name."""
    if not text:
        return text
    name = business_name or "Business"
    out = text
    for pat in (
        r"Bahi\s*POS",
        r"\[Business\]",
        r"\{Business\}",
    ):
        out = re.sub(pat, name, out, flags=re.I)
    return out


def personalize_setup_messages(
    patch: dict,
    *,
    business_name: str,
    overview: str = "",
    offer: str = "",
    location: str = "",
    lang: str = "roman_urdu",
    flow_mode: str = "lead",
) -> dict:
    """
    Rewrite ALL bot copy for the selected language (strict — no mixed EN/UR).
    Uses default_messages(lang) as the base so template overlays cannot leak
    the wrong language into questions / more replies / interactive labels.
    """
    from app.messages import default_messages

    patch = copy.deepcopy(patch)
    name = sanitize_text(business_name, max_len=80) or "Business"
    overview_s = sanitize_text(overview, max_len=400)
    offer_s = sanitize_text(offer, max_len=400)
    location_s = sanitize_text(location, max_len=120)
    en = lang in ("en", "english")
    lang_key = "en" if en else "roman_urdu"

    patch["campaign_phrase"] = name
    patch["greeting_language"] = lang_key

    # Clean language catalog — ignore template overlays that may be the other language
    msgs = copy.deepcopy(default_messages(lang_key))

    if flow_mode == "lead":
        lead = dict(msgs.get("lead") or {})
        interactive = dict(msgs.get("interactive") or {})

        if en:
            lead["greeting_line"] = f"Welcome! Thanks for your interest in {name}."
            lead["value_line"] = (
                overview_s
                or offer_s
                or f"{name} is here to help — share a few details so we can guide you."
            )[:280]
            lead["info_text"] = (
                "\n\n".join(p for p in (overview_s, offer_s) if p)
                or lead.get("info_text")
                or f"{name} helps customers get started quickly."
            )[:700]
            lead["q_business_name"] = "Kindly share your name or company name."
            lead["q_business_type"] = (
                f"Which {name} service do you need? Please select below."
            )
            lead["q_locations"] = (
                "Where are you based?"
                + (f" (We serve: {location_s})" if location_s else "")
            )
            lead["q_current_system"] = "How do you currently handle this today?"
            offer_bit = f" — including {offer_s[:120]}" if offer_s else ""
            lead["q_scheduling"] = (
                f"Our team at {name} would love to walk you through{offer_bit}.\n"
                "Which time works best for a demo or call?"
            )
            lead["q_custom_slot"] = "Kindly share your preferred date and time."
            lead["confirm_slot"] = (
                f"Thank you. Your {name} slot is booked for {{{{slot}}}}. "
                "Our team will contact you on this number."
            )
            lead["ack_business_name"] = f"Thank you — noted for {name}."
            lead["handoff"] = (
                f"Our {name} team will contact you shortly. Thank you for your time."
            )
            lead["owner_card_title"] = f"🔔 *NEW LEAD — {name}*"
            lead["pricing_text"] = (
                f"Pricing for {name} depends on your needs. "
                "We'll share a quote on the call or demo — please book a time."
            )
            lead["entry_demo_suffix"] = "Our team will help you pick a time:"
            lead["reprompt"] = "Sorry, we didn't catch that. {{current_question}}"
            interactive["select_button_label"] = "Select"
            interactive["slot_other_label"] = "Another time"
            interactive["current_system"] = [
                {"id": "sys_manual", "title": "Manual", "sheet_value": "Manual"},
                {"id": "sys_software", "title": "Software / tools", "sheet_value": "Software"},
                {"id": "sys_none", "title": "Nothing yet", "sheet_value": "No System"},
            ]
            other_loc = {"id": "loc_other", "title": "Other / remote", "value": "Other / remote"}
        else:
            lead["greeting_line"] = (
                f"Assalam o Alaikum 🙏 {name} mein aap ki dilchaspi ka shukriya."
            )
            lead["value_line"] = (
                overview_s
                or offer_s
                or f"{name} aap ki madad ke liye yahan hai — thori si info dein."
            )[:280]
            lead["info_text"] = (
                "\n\n".join(p for p in (overview_s, offer_s) if p)
                or lead.get("info_text")
                or f"{name} aap ko guide karega — neeche jawab dein."
            )[:700]
            lead["q_business_name"] = (
                "Barah-e-karam apna naam ya company ka naam farmaayein."
            )
            lead["q_business_type"] = (
                f"{name} ki kaunsi service / option chahiye? Neeche se muntakhib karein."
            )
            lead["q_locations"] = (
                "Aap kahan based hain ya kis area mein service chahiye?"
                + (f" (Hum: {location_s})" if location_s else "")
            )
            lead["q_current_system"] = "Abhi aap ka process / system kaisa hai?"
            offer_bit = f" ({offer_s[:120]})" if offer_s else ""
            lead["q_scheduling"] = (
                f"Hamari team ({name}) aap ko mukammal walkthrough dikhana chahti hai"
                f"{offer_bit}.\n"
                "Demo / call ke liye kaunsa waqt aap ke liye munasib rahega?"
            )
            lead["q_custom_slot"] = (
                "Barah-e-karam apni pasandida tarikh aur waqt likh kar bataayein."
            )
            lead["confirm_slot"] = (
                f"Shukriya. Aap ka {name} slot {{{{slot}}}} ke liye booked ho gaya hai. "
                "Hamari team aap se is number par rabta karegi."
            )
            lead["ack_business_name"] = (
                f"Shukriya — {name} ke liye aap ki info record ho gayi."
            )
            lead["handoff"] = (
                f"{name} ki team jald aap se rabta karegi. Shukriya apna waqt dene ka."
            )
            lead["owner_card_title"] = f"🔔 *NEW LEAD — {name}*"
            lead["pricing_text"] = (
                f"{name} ki pricing aap ki zarooriyaat ke mutabiq hoti hai. "
                "Call / demo mein quote milti hai — barah-e-karam time book karein."
            )
            lead["entry_demo_suffix"] = (
                "Hamari team aap ko time choose karne mein madad karegi:"
            )
            lead["reprompt"] = "Maazrat, jawab samajh nahi aaya. {{current_question}}"
            interactive["select_button_label"] = "Muntakhib karein"
            interactive["slot_other_label"] = "Koi aur time"
            interactive["current_system"] = [
                {"id": "sys_manual", "title": "Manual", "sheet_value": "Manual"},
                {"id": "sys_software", "title": "Software / tools", "sheet_value": "Software"},
                {"id": "sys_none", "title": "Kuch nahi", "sheet_value": "No System"},
            ]
            other_loc = {
                "id": "loc_other",
                "title": "Doosra / remote",
                "value": "Doosra / remote",
            }

        interactive["business_types"] = _offer_button_rows(offer_s, lang=lang_key)
        if location_s:
            interactive["locations"] = [
                {
                    "id": "loc_area",
                    "title": location_s[:24],
                    "value": location_s[:80],
                },
                other_loc,
            ]
        else:
            # Keep defaults but ensure labels match language (already from default_messages)
            interactive["locations"] = list(
                (default_messages(lang_key).get("interactive") or {}).get("locations") or []
            )

        msgs["lead"] = lead
        msgs["interactive"] = interactive
        patch["messages_draft"] = msgs
        # Always align top-level greeting with the selected language
        patch["greeting_text"] = lead["greeting_line"]

        if overview_s or offer_s:
            patch["facts_features"] = (offer_s or overview_s)[:800]
        if overview_s:
            patch["facts_claims_note"] = overview_s[:400]

    else:
        order = dict(msgs.get("order") or {})
        if en:
            order["greeting"] = (
                f"Welcome to {name}! Tap below to browse the menu."
            )
            order["menu_button_label"] = "View menu"
            order["owner_slip_title"] = f"🔔 *NEW ORDER — {name}*"
        else:
            order["greeting"] = (
                f"Assalam o Alaikum! {name} — menu dekhne ke liye neeche tap karein."
            )
            order["menu_button_label"] = "Menu dekhein"
            order["owner_slip_title"] = f"🔔 *NEW ORDER — {name}*"
        msgs["order"] = order
        patch["messages_draft"] = msgs
        patch["greeting_text"] = order["greeting"]

    # Final scrub for any leftover brand tokens
    def _walk(obj: Any) -> Any:
        if isinstance(obj, str):
            return _scrub_branded(obj, name)
        if isinstance(obj, list):
            return [_walk(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _walk(v) for k, v in obj.items()}
        return obj

    patch["messages_draft"] = _walk(patch["messages_draft"])

    # Demo slots always match language (Kal ↔ Tomorrow)
    from app.messages import localize_demo_slots

    existing_slots = patch.get("demo_slots")
    if not isinstance(existing_slots, list) or not existing_slots:
        existing_slots = ["Kal 11am", "Kal 4pm"]
    patch["demo_slots"] = localize_demo_slots(existing_slots, lang_key)
    return patch


def setup_preview(
    *,
    template_id: str,
    business_name: str,
    greeting_language: str = "roman_urdu",
    flow_mode: str | None = None,
    overview: str = "",
    offer: str = "",
    location: str = "",
) -> dict[str, Any]:
    """Preview greetings + question/message highlights before apply."""
    tid = resolve_template_id(template_id)
    tmpl = get_template(tid)
    if tmpl is None:
        raise ValueError(f"Unknown template: {tid}")
    mode = flow_mode or tmpl.get("flow_mode") or "lead"
    name = sanitize_text(business_name, max_len=256) or "Business"
    lang = greeting_language or "roman_urdu"
    patch = build_draft_patch(
        tid,
        flow_mode=mode,
        greeting_language=lang,
        business_name=name,
    )
    patch = personalize_setup_messages(
        patch,
        business_name=name,
        overview=overview,
        offer=offer,
        location=location,
        lang=lang,
        flow_mode=mode,
    )
    msgs = patch.get("messages_draft") or {}
    lead = msgs.get("lead") or {}
    order = msgs.get("order") or {}
    interactive = msgs.get("interactive") or {}

    question_preview: list[dict[str, str]] = []
    if mode == "lead":
        for key, label in (
            ("q_business_name", "Name"),
            ("q_business_type", "Type / service"),
            ("q_locations", "Location"),
            ("q_current_system", "Follow-up"),
            ("q_scheduling", "Scheduling"),
        ):
            text = (lead.get(key) or "").strip()
            if text:
                question_preview.append({"key": key, "label": label, "text": text})
        for key in ("business_types", "locations", "current_system"):
            rows = interactive.get(key) or []
            if rows:
                question_preview.append(
                    {
                        "key": f"buttons_{key}",
                        "label": f"Buttons · {key}",
                        "text": ", ".join(
                            str(r.get("title") or r.get("value") or "") for r in rows[:8]
                        ),
                    }
                )
    else:
        menu = patch.get("menu_v2_draft") or {}
        cats = menu.get("categories") or []
        items = menu.get("items") or []
        question_preview.append(
            {
                "key": "menu",
                "label": "Starter menu",
                "text": f"{len(cats)} categories · {len(items)} items (edit prices anytime)",
            }
        )
        if order.get("greeting"):
            question_preview.append(
                {"key": "order_greeting", "label": "Order greeting", "text": order["greeting"]}
            )

    more_keys = ("confirm_slot", "handoff", "ack_business_name")
    more_preview = [
        {"key": k, "text": str(lead.get(k) or order.get(k) or "").strip()}
        for k in more_keys
        if (lead.get(k) or order.get(k))
    ]

    return {
        "template_id": tid,
        "template_name": tmpl.get("name") or tid,
        "vertical": tmpl.get("vertical") or "",
        "flow_mode": mode,
        "blurb": tmpl.get("blurb") or "",
        "greetings": greeting_options(
            tid,
            business_name=name,
            greeting_language=lang,
            flow_mode=mode,
            overview=overview,
        ),
        "questions": question_preview,
        "more_replies": more_preview,
    }


def owner_setup_needed(row) -> bool:
    """
    True when the owner should see the first-run wizard.
    Skip once setup/content is marked, or when greeting already looks customized.
    """
    cfg = dict(row.config or {})
    ob = dict(cfg.get("onboarding") or {})
    if ob.get("owner_setup_complete") or ob.get("content_set"):
        return False

    kb = cfg.get("knowledge_base") if isinstance(cfg.get("knowledge_base"), dict) else {}
    sections = kb.get("sections") if isinstance(kb.get("sections"), dict) else {}
    has_kb = bool((kb.get("complete_knowledge") or "").strip()) or any(
        (sections.get(k) or "").strip()
        for k in ("overview", "products_services", "contact", "locations")
    )
    if has_kb and str(kb.get("status") or "") == "published":
        return False

    greet = (cfg.get("greeting_text") or "").strip().lower()
    defaultish = (
        not greet
        or "[business]" in greet
        or "kaise madad" in greet
        or "assalam o alaikum! menu" in greet
    )
    return defaultish


def _apply_greeting_choice(patch: dict, greeting_text: str, flow_mode: str) -> dict:
    text = sanitize_text(greeting_text, max_len=900)
    if not text:
        return patch
    patch = dict(patch)
    patch["greeting_text"] = text
    patch["greeting_blocks"] = [{"text": text, "image_url": ""}]
    patch["greeting_variants"] = []
    patch["greeting_image_url"] = ""
    msgs = copy.deepcopy(patch.get("messages_draft") or {})
    if flow_mode == "lead":
        lead = dict(msgs.get("lead") or {})
        lead["greeting_line"] = text
        msgs["lead"] = lead
    else:
        order = dict(msgs.get("order") or {})
        order["greeting"] = text
        msgs["order"] = order
        menu = copy.deepcopy(patch.get("menu_v2_draft") or {})
        if menu:
            settings = dict(menu.get("settings") or {})
            settings["greeting_text"] = text
            menu["settings"] = settings
            patch["menu_v2_draft"] = menu
    patch["messages_draft"] = msgs
    return patch


def _maybe_owner_whatsapp(contact: str) -> Optional[str]:
    raw = (contact or "").strip()
    if not raw:
        return None
    m = _PHONE_RE.search(raw.replace(" ", "").replace("-", ""))
    if not m:
        return None
    digits = re.sub(r"[^\d]", "", m.group(0))
    if len(digits) < 10:
        return None
    return digits[-15:]


def _apply_message_overrides(
    patch: dict, overrides: dict | None, flow_mode: str, *, lang: str = "roman_urdu"
) -> dict:
    """Merge owner-edited greeting/questions/more-replies into messages_draft."""
    if not overrides or not isinstance(overrides, dict):
        return patch
    patch = copy.deepcopy(patch)
    msgs = dict(patch.get("messages_draft") or {})
    if flow_mode == "lead":
        lead = dict(msgs.get("lead") or {})
        lead_in = overrides.get("lead") if isinstance(overrides.get("lead"), dict) else {}
        for key, val in lead_in.items():
            if not isinstance(key, str):
                continue
            text = sanitize_text(str(val or ""), max_len=900)
            if text:
                lead[key] = text
        msgs["lead"] = lead

        interactive = dict(msgs.get("interactive") or {})
        inter_in = (
            overrides.get("interactive") if isinstance(overrides.get("interactive"), dict) else {}
        )
        # Allow comma/newline list for business_types titles
        raw_types = inter_in.get("business_types_text")
        if isinstance(raw_types, str) and raw_types.strip():
            interactive["business_types"] = _offer_button_rows(raw_types, lang=lang)
        msgs["interactive"] = interactive
    else:
        order = dict(msgs.get("order") or {})
        order_in = overrides.get("order") if isinstance(overrides.get("order"), dict) else {}
        for key, val in order_in.items():
            if not isinstance(key, str):
                continue
            text = sanitize_text(str(val or ""), max_len=900)
            if text:
                order[key] = text
        msgs["order"] = order
    patch["messages_draft"] = msgs
    return patch


def retarget_config_language(
    cfg: dict,
    *,
    business_name: str,
    flow_mode: str,
    greeting_language: str,
) -> dict:
    """
    Rewrite greeting + Questions + more replies into greeting_language.
    Keeps knowledge_base / hours / flow structure; replaces customer-facing copy.
    """
    lang = greeting_language or "roman_urdu"
    if lang in ("en", "english"):
        lang_key = "en"
    else:
        lang_key = "roman_urdu"

    name = sanitize_text(business_name, max_len=256) or "Business"
    kb = cfg.get("knowledge_base") if isinstance(cfg.get("knowledge_base"), dict) else {}
    sections = kb.get("sections") if isinstance(kb.get("sections"), dict) else {}
    overview = str(sections.get("overview") or "")[:400]
    offer = str(sections.get("products_services") or "")[:400]
    location = str(sections.get("locations") or "")[:200]
    if not overview:
        overview = str(kb.get("complete_knowledge") or "")[:400]

    mode = flow_mode if flow_mode in ("lead", "order") else "lead"
    # Preserve service button titles (owner-custom) when retargeting language
    existing_draft = cfg.get("messages_draft") or cfg.get("messages") or {}
    existing_types = ((existing_draft.get("interactive") or {}).get("business_types") or [])
    types_text = ", ".join(
        str(r.get("title") or r.get("value") or "").strip()
        for r in existing_types
        if isinstance(r, dict) and (r.get("title") or r.get("value"))
    )

    patch: dict[str, Any] = {
        "greeting_text": cfg.get("greeting_text") or "",
        "messages_draft": copy.deepcopy(existing_draft) if isinstance(existing_draft, dict) else {},
        "campaign_phrase": cfg.get("campaign_phrase") or name,
    }
    patch = personalize_setup_messages(
        patch,
        business_name=name,
        overview=overview,
        offer=offer or types_text,
        location=location,
        lang=lang_key,
        flow_mode=mode,
    )
    if types_text.strip():
        patch = _apply_message_overrides(
            patch,
            {"interactive": {"business_types_text": types_text}},
            mode,
            lang=lang_key,
        )

    greet = (
        (patch.get("greeting_text") or "").strip()
        or ((patch.get("messages_draft") or {}).get("lead") or {}).get("greeting_line")
        or ((patch.get("messages_draft") or {}).get("order") or {}).get("greeting")
        or ""
    )
    greet = sanitize_text(str(greet), max_len=900)

    out = dict(cfg)
    out["greeting_language"] = lang_key
    out["greeting_text"] = greet
    out["campaign_phrase"] = patch.get("campaign_phrase") or name
    # Keep extra greeting bubbles but rewrite the first; drop empty
    prev_blocks = out.get("greeting_blocks") if isinstance(out.get("greeting_blocks"), list) else []
    img0 = ""
    if prev_blocks and isinstance(prev_blocks[0], dict):
        img0 = str(prev_blocks[0].get("image_url") or "")
    out["greeting_blocks"] = [{"text": greet, "image_url": img0}] if greet else []
    out["greeting_variants"] = []
    out["greeting_image_url"] = img0

    # Full replace — greeting, Questions, and More replies (confirm_slot / handoff / …)
    draft = copy.deepcopy(patch.get("messages_draft") or {})
    out["messages_draft"] = draft
    out["messages"] = copy.deepcopy(draft)

    # Demo slot button labels — keep times, translate "Kal" ↔ "Tomorrow"
    from app.messages import localize_demo_slots

    if mode == "lead":
        out["demo_slots"] = localize_demo_slots(out.get("demo_slots") or [], lang_key)

    # Clear baked-in flow question_text so Questions UI + WhatsApp use messages catalog
    flow = out.get("flow")
    if isinstance(flow, list):
        cleaned_flow = []
        for step in flow:
            if not isinstance(step, dict):
                cleaned_flow.append(step)
                continue
            s = dict(step)
            qk = str(s.get("question_key") or "").strip()
            if qk.startswith("q_"):
                s["question_text"] = ""
            cleaned_flow.append(s)
        out["flow"] = cleaned_flow

    return out


def apply_owner_setup_to_config(
    row,
    *,
    business_name: str,
    flow_mode: str,
    template_id: str,
    greeting_language: str,
    greeting_text: str,
    business_hours: dict | None,
    overview: str = "",
    offer: str = "",
    location: str = "",
    contact: str = "",
    extra: str = "",
    message_overrides: dict | None = None,
) -> tuple[dict, str]:
    """
    Build the full live config for owner setup.
    Returns (new_config, resolved_template_id). Does not persist.
    """
    mode = flow_mode if flow_mode in ("lead", "order") else "lead"
    tid = resolve_setup_template(
        template_id=template_id, vertical=None, flow_mode=mode
    )
    name = sanitize_text(business_name, max_len=256)
    if not name:
        raise ValueError("Business name is required")

    lang = greeting_language or "roman_urdu"
    if lang in ("en", "english"):
        lang = "en"
    else:
        lang = "roman_urdu"

    bh = validate_business_hours(business_hours or {"enabled": False})
    kb = build_knowledge_from_answers(
        business_name=name,
        overview=overview,
        offer=offer,
        location=location,
        contact=contact,
        business_hours=bh,
        extra=extra,
    )

    patch = build_draft_patch(
        tid,
        flow_mode=mode,
        greeting_language=lang,
        business_name=name,
    )
    patch = personalize_setup_messages(
        patch,
        business_name=name,
        overview=overview,
        offer=offer,
        location=location,
        lang=lang,
        flow_mode=mode,
    )
    patch = _apply_message_overrides(patch, message_overrides, mode, lang=lang)
    chosen = (greeting_text or "").strip() or patch.get("greeting_text") or ""
    patch = _apply_greeting_choice(patch, chosen, mode)

    cfg = dict(row.config or {})
    cfg.update(patch)
    # Always publish drafts for owner setup
    if "messages_draft" in patch:
        cfg["messages"] = copy.deepcopy(patch["messages_draft"])
    if "menu_v2_draft" in patch:
        cfg["menu_v2"] = copy.deepcopy(patch["menu_v2_draft"])
    if "menu" in patch:
        cfg["menu"] = patch["menu"]
    if "flow" in patch:
        cfg["flow"] = patch["flow"]

    cfg["business_hours"] = bh
    cfg["knowledge_base"] = kb
    cfg["faq"] = list(kb.get("faq") or [])

    wa = _maybe_owner_whatsapp(contact)
    if wa:
        cfg["owner_whatsapp"] = wa

    cfg = patch_onboarding(
        cfg,
        template_id=tid,
        content_set=True,
        owner_setup_complete=True,
        template_notes=(patch.get("onboarding") or {}).get("template_notes") or "",
    )
    return cfg, tid
