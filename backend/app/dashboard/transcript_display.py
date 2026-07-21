"""Build display history from lead fields when session transcript was not recorded."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import DBLead


def synthetic_lead_history(lead: "DBLead", meta: dict | None = None) -> list[dict]:
    """Reconstruct a readable thread from captured lead fields (legacy chats)."""
    meta = meta or {}
    msgs: list[dict] = []

    source = lead.ad_source or meta.get("lead_source") or ""
    if source:
        msgs.append({"role": "user", "content": f"Joined via campaign: {source}"})
        msgs.append(
            {
                "role": "assistant",
                "content": "Assalam o Alaikum! Main aapki madad ke liye hoon. Chaliye shuru karte hain.",
            }
        )

    prompts = [
        ("business_name", "Aapke business ka naam kya hai?", lead.business_name),
        ("business_type", "Business type?", lead.business_type),
        ("locations", "Kitni branches / locations?", lead.locations),
        ("current_system", "Abhi kaun sa system use kar rahe hain?", lead.current_system),
        ("demo_slot", "Demo slot", lead.demo_slot),
    ]
    for _key, question, answer in prompts:
        if answer:
            msgs.append({"role": "assistant", "content": question})
            msgs.append({"role": "user", "content": str(answer)})

    intent = lead.entry_intent or meta.get("entry_intent") or ""
    if intent and not msgs:
        msgs.append({"role": "user", "content": intent})

    phase = meta.get("phase") or ""
    if phase == "CONFIRMED" and lead.demo_slot:
        msgs.append(
            {
                "role": "assistant",
                "content": f"Shukriya! Aapki demo {lead.demo_slot} ke liye schedule ho chuki hai.",
            }
        )

    return msgs
