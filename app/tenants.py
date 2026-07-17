"""
Tenant registry — multi-tenant routing by phone_number_id.

Load order:
  1. TENANTS_JSON_B64 env var (base64-encoded JSON array) — production
  2. TENANTS_FILE env var pointing to a local JSON file — local dev
  3. Neither set → construct a single synthetic tenant from the existing
     FLOW_MODE / CAMPAIGN_PHRASE / etc. env vars (backward-compat mode).

On startup every tenant is validated with Pydantic; any schema error is a
hard failure with a clear message.

Usage:
    from app.tenants import get_tenant, Tenant
    tenant = get_tenant(phone_number_id)   # None if unknown
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

log = logging.getLogger("orderbot.tenants")


# ── Schema ─────────────────────────────────────────────────────────────────

class SheetConfig(BaseModel):
    gsheet_id: str
    tab: str = ""          # empty → first tab


class MenuCategory(BaseModel):
    name: str
    items: List[dict]      # [{name, price}, ...]


class MenuConfig(BaseModel):
    shop_name: str
    delivery_fee: Optional[int] = None
    delivery_area: Optional[str] = None
    categories: List[MenuCategory]


class FaqItem(BaseModel):
    question: str
    answer: str


class Tenant(BaseModel):
    phone_number_id: str
    name: str
    flow_mode: Literal["lead", "order"]
    business_wa_id: str = ""
    owner_whatsapp: str = ""
    campaign_phrase: str = "Bahi POS"
    demo_slots: List[str] = ["Kal 11am", "Kal 4pm"]
    facts: str = ""                        # legacy single block
    facts_features: str = ""
    facts_pricing_note: str = ""
    facts_claims_note: str = ""
    greeting_text: str = ""                 # optional custom greeting
    faq: List[FaqItem] = []
    menu: Optional[MenuConfig] = None      # order mode catalog
    sheet: Optional[SheetConfig] = None    # None → no sheet writes
    greeting_language: str = "roman_urdu"

    @field_validator("demo_slots")
    @classmethod
    def at_least_two_slots(cls, v: List[str]) -> List[str]:
        if len(v) < 1:
            raise ValueError("demo_slots must have at least one entry")
        # Pad to at least 2 for backward compat
        while len(v) < 2:
            v.append(v[0])
        return v

    @model_validator(mode="after")
    def check_mode_deps(self) -> "Tenant":
        if self.flow_mode == "order" and self.menu is None:
            raise ValueError(
                f"Tenant {self.phone_number_id!r}: flow_mode=order requires 'menu'"
            )
        return self

    @property
    def demo_slot_1(self) -> str:
        return self.demo_slots[0]

    @property
    def demo_slot_2(self) -> str:
        return self.demo_slots[1] if len(self.demo_slots) > 1 else self.demo_slots[0]

    @property
    def graph_url(self) -> str:
        return f"https://graph.facebook.com/v21.0/{self.phone_number_id}/messages"

    @property
    def faq_list(self) -> list[dict]:
        return [{"question": f.question, "answer": f.answer} for f in self.faq]

    def lang_code(self) -> str:
        """Map greeting_language to lead flow lang key."""
        if self.greeting_language in ("en", "english"):
            return "en"
        return "ur"

    @classmethod
    def from_db_row(cls, row) -> "Tenant":
        """Build Tenant from DBTenant ORM row."""
        cfg = dict(row.config or {})
        data = {
            "phone_number_id": row.phone_number_id,
            "name": row.name,
            "flow_mode": row.flow_mode,
            **cfg,
        }
        # Normalize faq list
        raw_faq = cfg.get("faq") or []
        if raw_faq and isinstance(raw_faq[0], dict):
            data["faq"] = raw_faq
        return cls.model_validate(data)


# ── Registry ────────────────────────────────────────────────────────────────

_registry: Dict[str, Tenant] = {}
_warned_unknown: set[str] = set()


def _load_from_list(raw: List[dict]) -> Dict[str, Tenant]:
    registry: Dict[str, Tenant] = {}
    for idx, item in enumerate(raw):
        try:
            t = Tenant.model_validate(item)
            registry[t.phone_number_id] = t
            log.info(f"tenants: loaded tenant {t.name!r} ({t.phone_number_id})")
        except Exception as exc:
            raise ValueError(
                f"Tenant at index {idx} failed validation: {exc}"
            ) from exc
    return registry


def _build_fallback_tenant() -> Tenant:
    """
    Construct a single tenant from legacy single-tenant env vars so that
    existing deployments continue to work unchanged.
    """
    import json as _json

    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "default")
    flow_mode = os.environ.get("FLOW_MODE", "lead")

    menu: Optional[dict] = None
    if flow_mode == "order":
        menu_path = os.environ.get("MENU_PATH", "menu.json")
        try:
            with open(menu_path, "r", encoding="utf-8") as f:
                menu = _json.load(f)
        except Exception:
            # If menu.json is missing we can't start in order mode — let validation fail
            pass

    sheet: Optional[dict] = None
    gsheet_id = os.environ.get("GSHEET_ID", "")
    if gsheet_id:
        sheet = {"gsheet_id": gsheet_id, "tab": os.environ.get("GSHEET_TAB", "")}

    data: dict = {
        "phone_number_id": phone_number_id,
        "name":            os.environ.get("TENANT_NAME", "Bahi POS"),
        "flow_mode":       flow_mode,
        "business_wa_id":  os.environ.get("BUSINESS_WA_ID", ""),
        "owner_whatsapp":  os.environ.get("OWNER_WHATSAPP", ""),
        "campaign_phrase": os.environ.get("CAMPAIGN_PHRASE", "Bahi POS"),
        "demo_slots": [
            os.environ.get("DEMO_SLOT_1", "Kal 11am"),
            os.environ.get("DEMO_SLOT_2", "Kal 4pm"),
        ],
        "facts":    "",          # no per-tenant facts in legacy mode
        "menu":     menu,
        "sheet":    sheet,
    }

    t = Tenant.model_validate(data)
    log.info(
        f"tenants: single-tenant fallback mode — "
        f"phone_number_id={phone_number_id}, flow_mode={flow_mode}"
    )
    return t


def load_tenants() -> None:
    """Load and validate all tenants into the registry. Called at startup."""
    global _registry

    b64 = os.environ.get("TENANTS_JSON_B64", "")
    file_path = os.environ.get("TENANTS_FILE", "")

    if b64:
        raw_json = base64.b64decode(b64).decode("utf-8")
        raw = json.loads(raw_json)
        log.info("tenants: loading from TENANTS_JSON_B64")
        _registry = _load_from_list(raw if isinstance(raw, list) else [raw])
    elif file_path:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        log.info(f"tenants: loading from TENANTS_FILE={file_path!r}")
        _registry = _load_from_list(raw if isinstance(raw, list) else [raw])
    else:
        log.info("tenants: no TENANTS_JSON_B64 or TENANTS_FILE — using single-tenant fallback")
        t = _build_fallback_tenant()
        _registry = {t.phone_number_id: t}

    log.info(f"tenants: {len(_registry)} tenant(s) loaded: {list(_registry.keys())}")


def get_tenant(phone_number_id: str) -> Optional[Tenant]:
    """
    Return the Tenant for *phone_number_id*, or None if unknown.
    Logs a WARNING once per unknown id.
    """
    t = _registry.get(phone_number_id)
    if t is None and phone_number_id not in _warned_unknown:
        log.warning(
            f"tenants: unknown phone_number_id={phone_number_id!r} — ignoring webhook"
        )
        _warned_unknown.add(phone_number_id)
    return t


def get_all_tenants() -> List[Tenant]:
    return list(_registry.values())


# ── Load on import ──────────────────────────────────────────────────────────
# This runs once when the module is first imported (i.e. at app startup).
# Hard errors surface immediately so the process won't start with bad config.
load_tenants()
