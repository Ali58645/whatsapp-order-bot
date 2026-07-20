"""
Admin onboarding — Graph connection, sheet test, checklist, template apply.

Starter templates live in app/templates/*.json (see app.templates registry).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

log = logging.getLogger("orderbot.onboarding")

_SHEET_ID_RE = re.compile(
    r"(?:https?://)?(?:docs\.google\.com/spreadsheets/d/|spreadsheets/d/)([a-zA-Z0-9-_]+)",
    re.I,
)
_SHEET_ID_BARE_RE = re.compile(r"^[a-zA-Z0-9-_]{20,}$")


def _whatsapp_token() -> str:
    return (
        os.environ.get("WHATSAPP_ACCESS_TOKEN")
        or os.environ.get("WHATSAPP_TOKEN")
        or os.environ.get("META_WHATSAPP_TOKEN")
        or ""
    )


def parse_sheet_id(url_or_id: str) -> str:
    """Extract spreadsheet ID from a Google Sheets URL or bare ID."""
    raw = (url_or_id or "").strip()
    if not raw:
        return ""
    m = _SHEET_ID_RE.search(raw)
    if m:
        return m.group(1)
    if _SHEET_ID_BARE_RE.match(raw):
        return raw
    return ""


def list_templates() -> list[dict]:
    """Return template metadata — delegates to app.templates registry."""
    from app.templates import list_templates as _list
    items = _list()
    # Normalize key for older frontend expecting "description"
    return [
        {
            **it,
            "description": it.get("blurb") or it.get("description") or "",
        }
        for it in items
    ]


def get_template(template_id: str) -> dict | None:
    from app.templates import get_template as _get
    return _get(template_id)


def apply_template_to_config(
    config: dict,
    *,
    template_id: str,
    flow_mode: str,
    greeting_language: str = "roman_urdu",
    business_name: str = "",
) -> dict:
    """
    Merge starter template onto config for onboarding (draft + published seeds).
    """
    from app.templates import apply_template_full_config

    return apply_template_full_config(
        config,
        template_id=template_id,
        flow_mode=flow_mode,
        greeting_language=greeting_language,
        business_name=business_name,
        publish_drafts=True,
    )


async def verify_and_subscribe(
    *,
    phone_number_id: str,
    waba_id: str = "",
    http_client=None,
) -> dict:
    """
    Confirm phone_number_id via Graph API, then ensure WABA subscribed_apps
    includes this app (subscribe if missing).
    """
    import httpx

    token = _whatsapp_token()
    if not token:
        raise RuntimeError("WHATSAPP_ACCESS_TOKEN not configured")

    headers = {"Authorization": f"Bearer {token}"}
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=15.0)

    try:
        phone_url = f"https://graph.facebook.com/v21.0/{phone_number_id}"
        resp = await client.get(
            phone_url,
            params={"fields": "display_phone_number,verified_name,quality_rating"},
            headers=headers,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code >= 400:
            err = (data.get("error") or {}).get("message") or resp.text
            raise ValueError(f"Verification failed: {err}")

        result: dict[str, Any] = {
            "ok": True,
            "phone_number_id": phone_number_id,
            "display_phone_number": data.get("display_phone_number"),
            "verified_name": data.get("verified_name") or data.get("name"),
            "quality_rating": data.get("quality_rating"),
            "waba_id": waba_id or None,
            "subscribed_apps": None,
            "subscribed_apps_fixed": False,
            "raw": data,
        }

        if waba_id:
            sub_url = f"https://graph.facebook.com/v21.0/{waba_id}/subscribed_apps"
            sub_resp = await client.get(sub_url, headers=headers)
            sub_data = sub_resp.json() if sub_resp.content else {}
            if sub_resp.status_code >= 400:
                err = (sub_data.get("error") or {}).get("message") or sub_resp.text
                raise ValueError(f"subscribed_apps check failed: {err}")

            apps = sub_data.get("data") or []
            already = len(apps) > 0
            result["subscribed_apps"] = already
            result["subscribed_apps_list"] = apps

            if not already:
                post = await client.post(sub_url, headers=headers)
                post_data = post.json() if post.content else {}
                if post.status_code >= 400:
                    err = (post_data.get("error") or {}).get("message") or post.text
                    raise ValueError(f"subscribed_apps subscribe failed: {err}")
                result["subscribed_apps"] = True
                result["subscribed_apps_fixed"] = True
                result["subscribe_result"] = post_data
        else:
            # Best-effort: also try phone-level subscribed_apps (some setups)
            phone_sub = f"https://graph.facebook.com/v21.0/{phone_number_id}/subscribed_apps"
            try:
                sub_resp = await client.get(phone_sub, headers=headers)
                if sub_resp.status_code < 400:
                    sub_data = sub_resp.json() if sub_resp.content else {}
                    apps = sub_data.get("data") or []
                    already = len(apps) > 0
                    result["subscribed_apps"] = already
                    if not already:
                        post = await client.post(phone_sub, headers=headers)
                        if post.status_code < 400:
                            result["subscribed_apps"] = True
                            result["subscribed_apps_fixed"] = True
            except Exception as exc:
                log.info(f"onboarding: phone-level subscribed_apps skipped — {exc}")

        return result
    finally:
        if owns_client:
            await client.aclose()


async def test_sheet_access(sheet_url_or_id: str) -> dict:
    """
    Verify the service account can open the spreadsheet (metadata get).
    Does not require a permanent write — metadata access proves sharing.
    Optionally writes+clears a probe cell when possible.
    """
    import asyncio

    sheet_id = parse_sheet_id(sheet_url_or_id)
    if not sheet_id:
        raise ValueError("Invalid Google Sheet URL or ID")

    sa_b64 = os.environ.get("GOOGLE_SA_JSON_B64", "")
    if not sa_b64:
        raise RuntimeError("GOOGLE_SA_JSON_B64 not configured")

    def _probe() -> dict:
        import base64
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        info = json.loads(base64.b64decode(sa_b64))
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        title = meta.get("properties", {}).get("title") or ""
        sheets = meta.get("sheets") or []
        tab = ""
        if sheets:
            tab = sheets[0].get("properties", {}).get("title") or ""

        # Write-access probe: update then clear a far-right cell on row 1
        write_ok = False
        try:
            probe_range = f"'{tab}'!ZZ1" if tab else "ZZ1"
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=probe_range,
                valueInputOption="RAW",
                body={"values": [["bahidesk_probe"]]},
            ).execute()
            service.spreadsheets().values().clear(
                spreadsheetId=sheet_id,
                range=probe_range,
                body={},
            ).execute()
            write_ok = True
        except Exception as write_exc:
            log.warning(f"onboarding: sheet write probe failed — {write_exc}")
            # Metadata succeeded; report read-ok but write failed
            return {
                "ok": False,
                "gsheet_id": sheet_id,
                "title": title,
                "tab": tab,
                "write_access": False,
                "detail": f"Readable but write failed: {write_exc}",
            }

        return {
            "ok": True,
            "gsheet_id": sheet_id,
            "title": title,
            "tab": tab,
            "write_access": write_ok,
        }

    return await asyncio.to_thread(_probe)


def build_checklist(row) -> dict:
    """Compute onboarding checklist for a DBTenant row."""
    cfg = dict(row.config or {})
    ob = dict(cfg.get("onboarding") or {})
    sheet = cfg.get("sheet") or {}
    msgs = cfg.get("messages") or cfg.get("messages_draft") or {}
    menu = cfg.get("menu_v2") or {}

    number_connected = bool(ob.get("connection_verified"))
    webhooks = ob.get("subscribed_apps")
    if webhooks is None:
        webhooks = False
    content_set = bool(ob.get("content_set")) or bool(msgs)
    if row.flow_mode == "order":
        content_set = content_set and (
            bool(ob.get("content_set")) or bool(menu.get("items") or menu.get("categories"))
        )
    test_sent = bool(ob.get("test_message_sent"))
    sheet_ok = bool(ob.get("sheet_tested")) if sheet.get("gsheet_id") else None  # optional

    items = [
        {"id": "number_connected", "label": "Number connected", "done": number_connected},
        {"id": "webhooks_subscribed", "label": "Webhooks subscribed", "done": bool(webhooks)},
        {"id": "content_set", "label": "Content set", "done": content_set},
        {"id": "test_message_delivered", "label": "Test message delivered", "done": test_sent},
    ]
    if sheet.get("gsheet_id"):
        items.append({
            "id": "sheet_connected",
            "label": "Sheet connected",
            "done": bool(sheet_ok),
        })

    done_count = sum(1 for i in items if i["done"])
    return {
        "tenant_id": row.id,
        "status": getattr(row, "status", None) or "draft",
        "template_id": ob.get("template_id"),
        "items": items,
        "done_count": done_count,
        "total_count": len(items),
        "complete": done_count == len(items) and (getattr(row, "status", "") == "live"),
    }


def patch_onboarding(cfg: dict, **fields: Any) -> dict:
    out = dict(cfg or {})
    ob = dict(out.get("onboarding") or {})
    for k, v in fields.items():
        if v is not None:
            ob[k] = v
    out["onboarding"] = ob
    return out
