"""
Option-list editors: custom interactive sets round-trip to payload builders.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "testtoken")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "faketoken")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "12345")
os.environ.setdefault("OWNER_WHATSAPP", "9200000000")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fake")
os.environ.setdefault("FLOW_MODE", "lead")


def test_custom_business_types_payload_order_and_sheet_values():
    from app.messages import default_messages, validate_messages_patch
    from app.tenants import Tenant
    from app.lead import get_phase_interactive, apply_interactive_answer

    msgs = default_messages("roman_urdu")
    msgs["interactive"]["business_types"] = [
        {"id": "cafe", "title": "Cafe", "description": "Coffee", "value": "Cafe Shop"},
        {"id": "bakery", "title": "Bakery", "description": "Bread", "value": "Bakery Unit"},
    ]
    msgs["interactive"]["locations"] = [
        {"id": "loc_a", "title": "One", "value": "1 branch"},
        {"id": "loc_b", "title": "Many", "value": "5+"},
    ]
    msgs["interactive"]["current_system"] = [
        {"id": "sys_x", "title": "Excel", "sheet_value": "Spreadsheet"},
        {"id": "sys_y", "title": "None", "sheet_value": "No System"},
    ]
    cleaned = validate_messages_patch(msgs)
    t = Tenant(
        phone_number_id="opt1",
        name="Opt",
        flow_mode="lead",
        messages=cleaned,
        demo_slots=["Mon 10am", "Tue 2pm"],
    )

    payload = get_phase_interactive("BUSINESS_TYPE", "92300", lang="ur", tenant=t)
    assert payload is not None
    rows = payload["interactive"]["action"]["sections"][0]["rows"]
    assert [r["id"] for r in rows] == ["cafe", "bakery"]
    assert [r["title"] for r in rows] == ["Cafe", "Bakery"]

    meta = {"phase": "BUSINESS_TYPE", "lang": "ur"}
    handled, _ = apply_interactive_answer(meta, "cafe", "Cafe", tenant=t)
    assert handled
    assert meta["business_type"] == "Cafe Shop"  # sheet value, not title
    assert meta["phase"] == "LOCATIONS"

    loc_payload = get_phase_interactive("LOCATIONS", "92300", lang="ur", tenant=t)
    btns = loc_payload["interactive"]["action"]["buttons"]
    assert [b["reply"]["id"] for b in btns] == ["loc_a", "loc_b"]

    meta["phase"] = "LOCATIONS"
    handled, _ = apply_interactive_answer(meta, "loc_b", "Many", tenant=t)
    assert handled
    assert meta["locations"] == "5+"

    meta["phase"] = "CURRENT_SYSTEM"
    handled, _ = apply_interactive_answer(meta, "sys_x", "Excel", tenant=t)
    assert handled
    assert meta["current_system"] == "Spreadsheet"


def test_empty_rows_stripped_and_limits_enforced():
    from app.messages import MessagesError, default_messages, validate_messages_patch

    msgs = default_messages("roman_urdu")
    msgs["interactive"]["business_types"] = [
        {"id": "a", "title": "Alpha", "description": "", "value": "A"},
        {"id": "empty", "title": "   ", "description": ""},
        {"id": "b", "title": "Beta", "description": "", "value": "B"},
    ]
    cleaned = validate_messages_patch(msgs)
    assert [r["id"] for r in cleaned["interactive"]["business_types"]] == ["a", "b"]

    msgs["interactive"]["locations"] = [
        {"id": f"l{i}", "title": str(i), "value": str(i)} for i in range(4)
    ]
    with pytest.raises(MessagesError, match="max 3"):
        validate_messages_patch(msgs)

    msgs = default_messages("roman_urdu")
    msgs["interactive"]["business_types"] = [
        {"id": f"x{i}", "title": f"T{i}", "description": "", "value": f"V{i}"}
        for i in range(11)
    ]
    with pytest.raises(MessagesError, match="max 10"):
        validate_messages_patch(msgs)


def test_duplicate_labels_rejected():
    from app.messages import MessagesError, default_messages, validate_messages_patch
    from app.dashboard.config_validate import validate_config_patch
    from fastapi import HTTPException

    msgs = default_messages("roman_urdu")
    msgs["interactive"]["locations"] = [
        {"id": "a", "title": "Same", "value": "1"},
        {"id": "b", "title": "same", "value": "2"},
    ]
    with pytest.raises(MessagesError, match="duplicate"):
        validate_messages_patch(msgs)

    with pytest.raises(HTTPException) as ei:
        validate_config_patch("lead", {
            "faq": [
                {"question": "Price?", "answer": "Ask sales"},
                {"question": "price?", "answer": "Different"},
            ]
        })
    assert ei.value.status_code == 400
    assert "duplicate" in str(ei.value.detail).lower()


def test_reorder_persists_in_payload():
    from app.messages import default_messages, validate_messages_patch
    from app.tenants import Tenant
    from app.lead import get_phase_interactive

    msgs = default_messages("roman_urdu")
    msgs["interactive"]["current_system"] = [
        {"id": "sys_none", "title": "Kuch nahi", "sheet_value": "No System"},
        {"id": "sys_manual", "title": "Manual register", "sheet_value": "Manual Register"},
        {"id": "sys_pos", "title": "POS software", "sheet_value": "Existing POS"},
    ]
    cleaned = validate_messages_patch(msgs)
    t = Tenant(phone_number_id="r1", name="R", flow_mode="lead", messages=cleaned)
    payload = get_phase_interactive("CURRENT_SYSTEM", "1", tenant=t)
    ids = [b["reply"]["id"] for b in payload["interactive"]["action"]["buttons"]]
    assert ids == ["sys_none", "sys_manual", "sys_pos"]


def test_overlong_label_rejected():
    from app.messages import MessagesError, default_messages, validate_messages_patch

    msgs = default_messages("roman_urdu")
    msgs["interactive"]["locations"] = [
        {"id": "a", "title": "X" * 21, "value": "1"},
    ]
    with pytest.raises(MessagesError, match="max 20"):
        validate_messages_patch(msgs)
