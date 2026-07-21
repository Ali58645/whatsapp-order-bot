"""Lead conversation transcript — persisted in session history for dashboard inbox."""

from __future__ import annotations

from app.sessions import get_session, save_session


def _interactive_as_text(payload: dict) -> str:
    inter = payload.get("interactive") or {}
    parts: list[str] = []
    body = (inter.get("body") or {}).get("text")
    if body:
        parts.append(str(body))
    itype = inter.get("type")
    action = inter.get("action") or {}
    if itype == "button":
        for btn in action.get("buttons") or []:
            title = (btn.get("reply") or {}).get("title")
            if title:
                parts.append(f"▢ {title}")
    elif itype == "list":
        label = action.get("button")
        if label:
            parts.append(f"📋 {label}")
        for section in action.get("sections") or []:
            for row in section.get("rows") or []:
                title = row.get("title")
                if title:
                    parts.append(f"• {title}")
    return "\n".join(parts).strip()


def record_user(sender: str, tenant_id: str, text: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    history = get_session(sender, tenant_id=tenant_id)
    history.append({"role": "user", "content": text})
    save_session(sender, history, tenant_id=tenant_id)


def record_bot(
    sender: str,
    tenant_id: str,
    text: str = "",
    interactive_payload: dict | None = None,
) -> None:
    content = (text or "").strip()
    if not content and interactive_payload:
        content = _interactive_as_text(interactive_payload)
    if not content:
        return
    history = get_session(sender, tenant_id=tenant_id)
    history.append({"role": "assistant", "content": content})
    save_session(sender, history, tenant_id=tenant_id)
