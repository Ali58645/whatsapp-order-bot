"""
Lead conversation flow — DB-driven step list with Bahi POS default.

tenant.config.flow = ordered list of steps. When absent, default_bahi_pos_flow()
is used so runtime stays byte-identical to the classic phase machine.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Optional

from app.interactive import (
    BUTTON_TITLE_MAX,
    BUTTONS_MAX,
    ROWS_MAX,
    build_buttons,
    build_list,
)

FLOW_MAX_STEPS = 12
STEP_TYPES = frozenset({
    "text_question",
    "button_options",
    "list_options",
    "free_text_capture",
})

# Keys that cannot be deleted (may be reordered)
RESERVED_KEYS = frozenset({"GREETING", "SCHEDULING", "CONFIRMED"})

# Standard capture fields + custom_1..custom_5
STANDARD_CAPTURE_FIELDS = frozenset({
    "business_name",
    "business_type",
    "locations",
    "current_system",
    "demo_slot",
    "custom_1",
    "custom_2",
    "custom_3",
    "custom_4",
    "custom_5",
})

# Sheet COLUMN_MAP keys we may write for capture_field
SHEET_CAPTURE_FIELDS = frozenset({
    "business_name",
    "business_type",
    "current_system",
    "demo_slot",  # written as demo_date/time via parse
    "city",
    "notes",
    "interest",
})

_CAPTURE_RE = re.compile(r"^(business_name|business_type|locations|current_system|demo_slot|city|notes|interest|custom_[1-5])$")

# Question catalog keys used when question_text is empty (byte-identical defaults)
_DEFAULT_QUESTION_KEYS = {
    "BUSINESS_NAME": "q_business_name",
    "BUSINESS_TYPE": "q_business_type",
    "LOCATIONS": "q_locations",
    "CURRENT_SYSTEM": "q_current_system",
    "SCHEDULING": "q_scheduling",
}


class FlowError(ValueError):
    pass


def default_bahi_pos_flow() -> list[dict]:
    """
    Seed matching classic PHASES / interactive builders.
    options empty + options_key → runtime resolves from messages.interactive
    (same IDs/titles as today).
    """
    return [
        {
            "id": "step_greeting",
            "key": "GREETING",
            "type": "text_question",
            "question_text": "",
            "options": [],
            "capture_field": None,
            "required": True,
            "skip_if_declined": False,
            "reserved": True,
            "system": True,
        },
        {
            "id": "step_business_name",
            "key": "BUSINESS_NAME",
            "type": "text_question",
            "question_text": "",
            "question_key": "q_business_name",
            "options": [],
            "capture_field": "business_name",
            "required": True,
            "skip_if_declined": False,
            "reserved": False,
            "system": False,
        },
        {
            "id": "step_business_type",
            "key": "BUSINESS_TYPE",
            "type": "list_options",
            "question_text": "",
            "question_key": "q_business_type",
            "options_key": "business_types",
            "options": [],
            "capture_field": "business_type",
            "required": True,
            "skip_if_declined": False,
            "reserved": False,
            "system": False,
        },
        {
            "id": "step_locations",
            "key": "LOCATIONS",
            "type": "button_options",
            "question_text": "",
            "question_key": "q_locations",
            "options_key": "locations",
            "options": [],
            "capture_field": "locations",
            "required": True,
            "skip_if_declined": False,
            "reserved": False,
            "system": False,
        },
        {
            "id": "step_current_system",
            "key": "CURRENT_SYSTEM",
            "type": "button_options",
            "question_text": "",
            "question_key": "q_current_system",
            "options_key": "current_system",
            "options": [],
            "capture_field": "current_system",
            "required": True,
            "skip_if_declined": False,
            "reserved": False,
            "system": False,
        },
        {
            "id": "step_scheduling",
            "key": "SCHEDULING",
            "type": "button_options",
            "question_text": "",
            "question_key": "q_scheduling",
            "options": [],  # built from demo_slots + slot_other at runtime
            "capture_field": "demo_slot",
            "required": True,
            "skip_if_declined": False,
            "reserved": True,
            "system": True,
        },
        {
            "id": "step_confirmed",
            "key": "CONFIRMED",
            "type": "text_question",
            "question_text": "",
            "options": [],
            "capture_field": None,
            "required": True,
            "skip_if_declined": False,
            "reserved": True,
            "system": True,
        },
    ]


def seed_flow_into_config(cfg: dict) -> dict:
    """Ensure config has flow; mutate copy and return."""
    out = dict(cfg or {})
    if not out.get("flow"):
        out["flow"] = default_bahi_pos_flow()
    return out


def get_tenant_flow(tenant=None) -> list[dict]:
    """Resolve ordered steps for a tenant (default if unset)."""
    if tenant is None:
        return default_bahi_pos_flow()
    raw = getattr(tenant, "_raw_config", None) or {}
    flow = raw.get("flow")
    if isinstance(flow, list) and flow:
        return flow
    # Also allow attribute if ever typed
    flow = getattr(tenant, "flow", None)
    if isinstance(flow, list) and flow:
        return flow
    return default_bahi_pos_flow()


def find_step(flow: list[dict], key: str) -> Optional[dict]:
    for s in flow:
        if s.get("key") == key:
            return s
    return None


def next_step_after(flow: list[dict], key: str) -> Optional[dict]:
    for i, s in enumerate(flow):
        if s.get("key") == key and i + 1 < len(flow):
            return flow[i + 1]
    return None


def next_phase_key(tenant, current_key: str) -> str:
    """Next phase key after current; CONFIRMED if end."""
    flow = get_tenant_flow(tenant)
    nxt = next_step_after(flow, current_key)
    if nxt:
        return str(nxt["key"])
    return "CONFIRMED"


def walkable_steps(flow: list[dict]) -> list[dict]:
    """Steps the bot asks (excludes GREETING + CONFIRMED terminals)."""
    return [
        s for s in flow
        if s.get("key") not in ("GREETING", "CONFIRMED", "STALLED")
    ]


def activation_path_ok(flow: list[dict]) -> bool:
    """At least one path from GREETING → qualification → SCHEDULING → CONFIRMED."""
    keys = [s.get("key") for s in flow]
    if "GREETING" not in keys or "CONFIRMED" not in keys:
        return False
    if "SCHEDULING" not in keys:
        return False
    # Must have at least one capture step before scheduling (or DEMO_FIRST skip)
    return True


def validate_flow(flow: Any) -> list[dict]:
    """Validate and normalize a flow list. Raises FlowError."""
    if not isinstance(flow, list):
        raise FlowError("flow must be a list of steps")
    if len(flow) < 3:
        raise FlowError("flow needs at least greeting, one question, and confirm")
    if len(flow) > FLOW_MAX_STEPS:
        raise FlowError(f"flow max {FLOW_MAX_STEPS} steps")

    cleaned: list[dict] = []
    seen_keys: set[str] = set()
    seen_ids: set[str] = set()

    for i, raw in enumerate(flow):
        if not isinstance(raw, dict):
            raise FlowError(f"flow[{i}] must be an object")
        sid = str(raw.get("id") or f"step_{i}").strip()[:64]
        key = str(raw.get("key") or "").strip().upper().replace(" ", "_")
        if not key:
            raise FlowError(f"flow[{i}].key required")
        if key in seen_keys:
            raise FlowError(f"duplicate step key {key!r}")
        if sid in seen_ids:
            raise FlowError(f"duplicate step id {sid!r}")
        seen_keys.add(key)
        seen_ids.add(sid)

        stype = str(raw.get("type") or "").strip()
        if stype not in STEP_TYPES:
            raise FlowError(f"flow[{i}].type must be one of {sorted(STEP_TYPES)}")

        q_text = str(raw.get("question_text") or "")[:1024]
        q_key = str(raw.get("question_key") or "").strip()[:64] or None
        options_key = str(raw.get("options_key") or "").strip()[:64] or None

        capture = raw.get("capture_field")
        if capture is not None and capture != "":
            capture = str(capture).strip()
            if not _CAPTURE_RE.match(capture):
                raise FlowError(
                    f"flow[{i}].capture_field {capture!r} invalid — "
                    "use business_name, locations, custom_1..5, etc."
                )
        else:
            capture = None

        reserved = bool(raw.get("reserved")) or key in RESERVED_KEYS
        system = bool(raw.get("system")) or reserved

        options = raw.get("options") or []
        if not isinstance(options, list):
            raise FlowError(f"flow[{i}].options must be a list")

        opts_clean = _validate_options(i, stype, options, options_key, key)

        cleaned.append({
            "id": sid,
            "key": key,
            "type": stype,
            "question_text": q_text,
            "question_key": q_key,
            "options_key": options_key,
            "options": opts_clean,
            "capture_field": capture,
            "required": bool(raw.get("required", True)),
            "skip_if_declined": bool(raw.get("skip_if_declined", False)),
            "reserved": reserved,
            "system": system,
        })

    # Reserved keys that exist in default must still be present if we started from default
    for rk in RESERVED_KEYS:
        if rk not in seen_keys:
            raise FlowError(f"reserved step {rk} cannot be removed")

    if not activation_path_ok(cleaned):
        raise FlowError("flow must preserve GREETING → … → SCHEDULING → CONFIRMED")

    return cleaned


def _validate_options(
    i: int,
    stype: str,
    options: list,
    options_key: Optional[str],
    key: str,
) -> list[dict]:
    if stype not in ("button_options", "list_options"):
        return []

    # SCHEDULING builds slots at runtime — allow empty
    if key == "SCHEDULING":
        return []

    # options_key alone is ok (resolved from messages.interactive)
    if not options and options_key:
        return []

    if stype == "button_options":
        max_n, max_title = BUTTONS_MAX, BUTTON_TITLE_MAX
    else:
        max_n, max_title = ROWS_MAX, 24

    if len(options) > max_n:
        raise FlowError(f"flow[{i}] options max {max_n} for {stype}")

    # Empty options without options_key only ok for reserved scheduling
    if not options and not options_key:
        raise FlowError(f"flow[{i}] needs options or options_key")

    cleaned = []
    seen_ids: set[str] = set()
    for j, opt in enumerate(options):
        if not isinstance(opt, dict):
            raise FlowError(f"flow[{i}].options[{j}] must be an object")
        oid = str(opt.get("id") or f"opt_{j}").strip()[:64]
        title = str(opt.get("title") or opt.get("label") or "").strip()
        if not title:
            raise FlowError(f"flow[{i}].options[{j}] title required")
        if len(title) > max_title:
            raise FlowError(
                f"flow[{i}].options[{j}] title max {max_title} chars (WhatsApp)"
            )
        if oid in seen_ids:
            raise FlowError(f"flow[{i}] duplicate option id {oid!r}")
        seen_ids.add(oid)
        row: dict[str, Any] = {
            "id": oid,
            "title": title[:max_title],
        }
        if opt.get("description"):
            row["description"] = str(opt["description"])[:72]
        if opt.get("value") is not None:
            row["value"] = str(opt["value"])[:64]
        if opt.get("sheet_value") is not None:
            row["sheet_value"] = str(opt["sheet_value"])[:64]
        cleaned.append(row)
    return cleaned


def step_question_text(step: dict, lang: str = "ur", tenant=None) -> str:
    """Resolve question body for a step."""
    qt = (step.get("question_text") or "").strip()
    if qt:
        return qt
    from app.lead import lead_text
    qk = step.get("question_key") or _DEFAULT_QUESTION_KEYS.get(step.get("key", ""), "")
    if qk:
        return lead_text(qk, lang, tenant)
    return ""


def resolve_step_options(step: dict, tenant=None, lang: str = "ur") -> list[dict]:
    """
    Options for button/list steps.
    Prefer step.options; else options_key → messages.interactive; else maps.
    """
    opts = step.get("options") or []
    if opts:
        return opts

    options_key = step.get("options_key")
    if not options_key:
        return []

    from app.lead import _interactive_maps
    maps = _interactive_maps(tenant, lang)
    if options_key == "business_types":
        # Convert rows (id, title, desc) to option dicts
        rows = maps["btype_rows"]
        labels = maps["btype_labels"]
        out = []
        for rid, title, desc in rows:
            out.append({
                "id": rid,
                "title": title,
                "description": desc,
                "value": labels.get(rid, title),
            })
        return out
    if options_key == "locations":
        return [
            {"id": bid, "title": title, "value": maps["loc_labels"].get(bid, title)}
            for bid, title in maps["loc_buttons"]
        ]
    if options_key == "current_system":
        return [
            {
                "id": bid,
                "title": title,
                "sheet_value": maps["sys_labels"].get(bid, title),
                "value": maps["sys_labels"].get(bid, title),
            }
            for bid, title in maps["sys_buttons"]
        ]
    return []


def option_capture_value(opt: dict) -> str:
    return str(
        opt.get("sheet_value")
        or opt.get("value")
        or opt.get("title")
        or ""
    )


def build_step_interactive(
    step: dict,
    sender: str,
    lang: str = "ur",
    meta: Optional[dict] = None,
    tenant=None,
) -> Optional[dict]:
    """Build WhatsApp interactive payload for a step (same builders as lead)."""
    stype = step.get("type")
    key = step.get("key")
    body = step_question_text(step, lang, tenant)

    if key == "SCHEDULING":
        from app.lead import DEMO_SLOT_1, DEMO_SLOT_2, _interactive_maps
        maps = _interactive_maps(tenant, lang)
        if meta:
            slot_1 = meta.get("_slot_1") or DEMO_SLOT_1
            slot_2 = meta.get("_slot_2") or DEMO_SLOT_2
        else:
            slot_1, slot_2 = DEMO_SLOT_1, DEMO_SLOT_2
        buttons = [
            ("slot_1", str(slot_1)[:20]),
            ("slot_2", str(slot_2)[:20]),
            ("slot_other", str(maps["slot_other"])[:20]),
        ]
        return build_buttons(sender, body, buttons)

    if stype == "list_options":
        opts = resolve_step_options(step, tenant, lang)
        if not opts:
            return None
        from app.lead import _interactive_maps
        maps = _interactive_maps(tenant, lang)
        rows = [
            (
                o["id"],
                o["title"][:24],
                str(o.get("description") or "")[:72],
            )
            for o in opts[:ROWS_MAX]
        ]
        return build_list(sender, body, str(maps["select_label"])[:20], rows)

    if stype == "button_options":
        opts = resolve_step_options(step, tenant, lang)
        if not opts:
            return None
        buttons = [(o["id"], o["title"][:BUTTON_TITLE_MAX]) for o in opts[:BUTTONS_MAX]]
        return build_buttons(sender, body, buttons)

    return None


def apply_flow_interactive_answer(
    meta: dict,
    reply_id: str,
    reply_title: str,
    tenant=None,
) -> tuple[bool, Optional[str]]:
    """
    Process button/list tap using the tenant flow.
    Mirrors lead.apply_interactive_answer behavior for default flow.
    """
    from app.lead import lead_text, DEMO_SLOT_1, DEMO_SLOT_2, _interactive_maps

    phase = meta.get("phase", "GREETING")
    lang = meta.get("lang", "ur")
    flow = get_tenant_flow(tenant)

    if reply_id == "menu_demo":
        meta["phase"] = "BUSINESS_NAME"
        meta.setdefault("entry_intent", "DEMO_FIRST")
        # Keep greeting text path identical
        from app.lead import _greeting_text
        return True, _greeting_text(lang, tenant)

    step = find_step(flow, phase)
    if step is None:
        return False, None

    # Scheduling special cases (reserved)
    if phase == "SCHEDULING":
        _slot_1 = meta.get("_slot_1") or DEMO_SLOT_1
        _slot_2 = meta.get("_slot_2") or DEMO_SLOT_2
        if reply_id == "slot_1":
            meta["demo_slot"] = _slot_1
            meta["phase"] = "CONFIRMED"
            return True, None
        if reply_id == "slot_2":
            meta["demo_slot"] = _slot_2
            meta["phase"] = "CONFIRMED"
            return True, None
        if reply_id == "slot_other":
            meta["awaiting_custom_slot"] = True
            return True, lead_text("q_custom_slot", lang, tenant)
        return False, None

    stype = step.get("type")
    if stype not in ("button_options", "list_options"):
        return False, None

    opts = resolve_step_options(step, tenant, lang)
    by_id = {o["id"]: o for o in opts}
    if reply_id not in by_id:
        # Legacy fallback via interactive maps for default keys
        maps = _interactive_maps(tenant, lang)
        label = None
        field = step.get("capture_field")
        if phase == "BUSINESS_TYPE" and reply_id in maps["btype_labels"]:
            label = maps["btype_labels"][reply_id]
        elif phase == "LOCATIONS" and reply_id in maps["loc_labels"]:
            label = maps["loc_labels"][reply_id]
        elif phase == "CURRENT_SYSTEM" and reply_id in maps["sys_labels"]:
            label = maps["sys_labels"][reply_id]
        if label is None:
            return False, None
        if field:
            meta[field] = label
        meta["phase"] = next_phase_key(tenant, phase)
        return True, None

    opt = by_id[reply_id]
    field = step.get("capture_field")
    if field:
        meta[field] = option_capture_value(opt)
    meta["phase"] = next_phase_key(tenant, phase)
    return True, None


def match_text_to_step_option(
    step: dict,
    text: str,
    tenant=None,
    lang: str = "ur",
) -> Optional[str]:
    """Return capture value if free text matches an option; else None."""
    opts = resolve_step_options(step, tenant, lang)
    lower = text.lower().strip()
    for o in opts:
        title = str(o.get("title") or "").lower()
        val = str(o.get("value") or "").lower()
        sid = str(o.get("id") or "").lower()
        if lower == title or lower == val or lower == sid:
            return option_capture_value(o)
        if title and title in lower:
            return option_capture_value(o)
    return None


def sheet_fields_from_meta(meta: dict) -> dict:
    """Map meta capture fields to sheet upsert keys."""
    out: dict[str, str] = {}
    for k in ("business_name", "business_type", "current_system", "city", "interest"):
        if meta.get(k):
            out[k] = str(meta[k])
    # custom_* and locations → notes appendix
    extras = []
    if meta.get("locations"):
        extras.append(f"locations={meta['locations']}")
    for i in range(1, 6):
        ck = f"custom_{i}"
        if meta.get(ck):
            extras.append(f"{ck}={meta[ck]}")
    if extras:
        prev = str(meta.get("notes") or "")
        note = "; ".join(extras)
        out["notes"] = f"{prev}; {note}".strip("; ") if prev else note
    return out


def preview_flow_messages(
    flow: list[dict],
    *,
    lang: str = "ur",
    tenant=None,
    demo_slots: Optional[list[str]] = None,
) -> list[dict]:
    """
    End-to-end WhatsApp-style preview of the flow (no Graph API).
    Same builders as runtime for interactive steps.
    """
    steps = validate_flow(copy.deepcopy(flow)) if flow else default_bahi_pos_flow()
    meta = {
        "_slot_1": (demo_slots or ["Kal 11am", "Kal 4pm"])[0],
        "_slot_2": (demo_slots or ["Kal 11am", "Kal 4pm"])[
            1 if demo_slots and len(demo_slots) > 1 else 0
        ],
    }
    out: list[dict] = []
    for step in steps:
        key = step.get("key")
        if key in ("GREETING", "CONFIRMED"):
            out.append({
                "key": key,
                "type": step["type"],
                "kind": "system",
                "body": step_question_text(step, lang, tenant) or key,
                "interactive": None,
                "reserved": True,
            })
            continue
        payload = build_step_interactive(
            step, "PREVIEW", lang, meta=meta, tenant=tenant
        )
        kind = "text"
        if step["type"] == "list_options":
            kind = "list"
        elif step["type"] == "button_options":
            kind = "buttons"
        elif step["type"] == "free_text_capture":
            kind = "text"
        out.append({
            "key": key,
            "type": step["type"],
            "kind": kind,
            "body": step_question_text(step, lang, tenant),
            "capture_field": step.get("capture_field"),
            "interactive": payload,
            "options": resolve_step_options(step, tenant, lang) if step["type"] in (
                "button_options", "list_options"
            ) and key != "SCHEDULING" else (
                [
                    {"id": "slot_1", "title": meta["_slot_1"]},
                    {"id": "slot_2", "title": meta["_slot_2"]},
                    {"id": "slot_other", "title": "Another time"},
                ]
                if key == "SCHEDULING"
                else []
            ),
            "reserved": bool(step.get("reserved")),
        })
    return out


def flows_equal_default(flow: list[dict]) -> bool:
    """True if flow keys/types/options_keys match default Bahi POS sequence."""
    default = default_bahi_pos_flow()
    if len(flow) != len(default):
        return False
    for a, b in zip(flow, default):
        if a.get("key") != b.get("key") or a.get("type") != b.get("type"):
            return False
        if a.get("capture_field") != b.get("capture_field"):
            return False
        if a.get("options_key") != b.get("options_key"):
            return False
    return True
