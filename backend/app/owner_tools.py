"""
Owner-facing helpers: business hours, greeting variants, image greeting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo


def _https_image(url: str) -> str:
    u = (url or "").strip()
    if u.lower().startswith("https://"):
        return u[:2048]
    return ""


def greeting_blocks(tenant) -> list[dict[str, str]]:
    """
    Greeting bubbles to send: [{text, image_url}, ...] in order.
    Prefers config.greeting_blocks; falls back to greeting_text / variants / image.
    """
    raw = getattr(tenant, "_raw_config", None) or {}
    blocks_in = raw.get("greeting_blocks")
    out: list[dict[str, str]] = []
    if isinstance(blocks_in, list) and blocks_in:
        for item in blocks_in:
            if isinstance(item, dict):
                text = str(item.get("text") or "").strip()
                img = _https_image(str(item.get("image_url") or ""))
                if text or img:
                    out.append({"text": text, "image_url": img})
            elif isinstance(item, str) and item.strip():
                out.append({"text": item.strip(), "image_url": ""})
        if out:
            return out

    custom = (getattr(tenant, "greeting_text", "") or "").strip()
    first_img = _https_image(str(raw.get("greeting_image_url") or ""))
    variants = raw.get("greeting_variants") or []
    extras: list[str] = []
    for v in variants:
        if isinstance(v, dict):
            t = str(v.get("text") or "").strip()
            if t:
                extras.append(t)
        elif isinstance(v, str) and v.strip():
            extras.append(v.strip())
    if custom or first_img:
        out.append({"text": custom, "image_url": first_img})
    for e in extras:
        out.append({"text": e, "image_url": ""})
    return out


def greeting_messages(tenant) -> list[str]:
    """Text-only greeting lines (compat)."""
    return [b["text"] for b in greeting_blocks(tenant) if b.get("text")]


def pick_greeting_text(tenant) -> str:
    """Joined greetings (compat). Prefer greeting_blocks() for WhatsApp sends."""
    msgs = greeting_messages(tenant)
    return "\n\n".join(msgs) if msgs else ""


def greeting_image_url(tenant) -> str:
    """First greeting image (compat)."""
    blocks = greeting_blocks(tenant)
    if blocks:
        return blocks[0].get("image_url") or ""
    raw = getattr(tenant, "_raw_config", None) or {}
    return _https_image(str(raw.get("greeting_image_url") or ""))


def business_hours_config(tenant) -> dict[str, Any]:
    raw = getattr(tenant, "_raw_config", None) or {}
    bh = raw.get("business_hours") or {}
    if not isinstance(bh, dict):
        return {"enabled": False}
    return bh


def is_within_business_hours(tenant, *, now: Optional[datetime] = None) -> bool:
    """
    Return True if bot should answer normally.
    When business_hours.enabled is false/missing → always open.
    """
    bh = business_hours_config(tenant)
    if not bh.get("enabled"):
        return True
    tz_name = str(bh.get("timezone") or "Asia/Karachi")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("Asia/Karachi")
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)

    # Python weekday Mon=0 … Sun=6
    day_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    day = day_keys[now.weekday()]
    windows = bh.get("days") or {}
    # Enabled but never configured → treat as always open (don't silently drop inbox)
    if not windows:
        return True
    slots = windows.get(day) or windows.get(day[:3]) or []
    if not slots:
        return False  # closed all day (day present/empty intentionally)
    hm = now.hour * 60 + now.minute
    for slot in slots:
        if not isinstance(slot, (list, tuple)) or len(slot) < 2:
            continue
        try:
            a = _parse_hm(str(slot[0]))
            b = _parse_hm(str(slot[1]))
        except ValueError:
            continue
        if a <= hm < b:
            return True
    return False


def away_message(tenant) -> str:
    bh = business_hours_config(tenant)
    msg = str(bh.get("away_message") or "").strip()
    if msg:
        return msg[:1024]
    return (
        "Shukriya message karne ka. Abhi hamari team available nahi — "
        "business hours mein dobara rabta karein."
    )


def _parse_hm(s: str) -> int:
    parts = s.strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return h * 60 + m


def validate_business_hours(raw: Any) -> dict:
    if raw is None:
        return {"enabled": False}
    if not isinstance(raw, dict):
        raise ValueError("business_hours must be an object")
    out: dict[str, Any] = {
        "enabled": bool(raw.get("enabled")),
        "timezone": str(raw.get("timezone") or "Asia/Karachi")[:64],
        "away_message": str(raw.get("away_message") or "")[:1024],
        "days": {},
    }
    days_in = raw.get("days") or {}
    if isinstance(days_in, dict):
        for k, v in days_in.items():
            key = str(k).lower()[:3]
            if key not in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
                continue
            slots = []
            if isinstance(v, list):
                for slot in v[:4]:
                    if isinstance(slot, (list, tuple)) and len(slot) >= 2:
                        slots.append([str(slot[0])[:5], str(slot[1])[:5]])
            out["days"][key] = slots
    return out
