"""Multi-channel adapter and pipeline tests."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "testtoken")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "faketoken")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "12345")
os.environ.setdefault("OWNER_WHATSAPP", "9200000000")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fake")
os.environ.setdefault("FLOW_MODE", "lead")

PID = "PID_CH_WA"
SENDER = "923001234567"


def _wa_text_payload(text: str, phone_number_id: str = PID) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "metadata": {"phone_number_id": phone_number_id},
                    "contacts": [{"wa_id": SENDER, "profile": {"name": "Test"}}],
                    "messages": [{
                        "from": SENDER,
                        "type": "text",
                        "text": {"body": text},
                    }],
                },
            }],
        }],
    }


def _ig_text_payload(text: str, ig_id: str = "IG_PAGE_1") -> dict:
    return {
        "object": "instagram",
        "entry": [{
            "id": ig_id,
            "messaging": [{
                "sender": {"id": SENDER},
                "recipient": {"id": ig_id},
                "message": {"text": text},
            }],
        }],
    }


def _messenger_text_payload(text: str, page_id: str = "PAGE_1") -> dict:
    return {
        "object": "page",
        "entry": [{
            "id": page_id,
            "messaging": [{
                "sender": {"id": SENDER},
                "recipient": {"id": page_id},
                "message": {"text": text},
            }],
        }],
    }


@pytest.fixture(autouse=True)
def reset_state():
    from app import sessions, gate, lead

    sessions._sessions.clear()
    sessions._locks.clear()
    gate._muted.clear()
    lead._meta.clear()
    yield
    sessions._sessions.clear()
    sessions._locks.clear()
    gate._muted.clear()
    lead._meta.clear()


@pytest.fixture()
def wa_tenant(monkeypatch):
    import app.tenants as tenants_mod
    from app.tenants import Tenant

    t = Tenant(
        phone_number_id=PID,
        name="Channel Test",
        flow_mode="lead",
        campaign_phrase="Bahi POS",
        demo_slots=["Kal 11am", "Kal 4pm"],
    )
    monkeypatch.setattr(tenants_mod, "_registry", {PID: t})
    return t


@pytest.fixture()
async def client():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Normalized parsing ────────────────────────────────────────────────────────


def test_whatsapp_parse_normalized():
    from app.channels.whatsapp import parse_webhook

    msgs = parse_webhook(_wa_text_payload("Bahi POS hello"))
    assert len(msgs) == 1
    nm = msgs[0]
    assert nm.channel == "whatsapp"
    assert nm.account_id == PID
    assert nm.sender_id == SENDER
    assert nm.text == "Bahi POS hello"
    assert nm.raw_entry is not None


def test_instagram_parse_normalized():
    from app.channels.instagram import parse_webhook

    msgs = parse_webhook(_ig_text_payload("Hi from IG"))
    assert len(msgs) == 1
    assert msgs[0].channel == "instagram"
    assert msgs[0].sender_id == SENDER
    assert msgs[0].text == "Hi from IG"


def test_messenger_parse_normalized():
    from app.channels.messenger import parse_webhook

    msgs = parse_webhook(_messenger_text_payload("Hi from FB"))
    assert len(msgs) == 1
    assert msgs[0].channel == "messenger"


@pytest.mark.asyncio
async def test_unknown_webhook_ignored(client):
    r = await client.post("/webhook", json={"foo": "bar"})
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"


# ── IG quick replies within limits ────────────────────────────────────────────


def test_ig_quick_reply_rendering_max_13():
    from app.channels.interactive_builder import render_outbound
    from app.channels.types import InteractiveChoice, OutboundMessage

    choices = [InteractiveChoice(id=f"opt_{i}", title=f"Option {i}") for i in range(20)]
    msg = OutboundMessage(
        channel="instagram",
        recipient_id="123",
        text="Pick one",
        choices=choices,
        choice_style="quick_replies",
    )
    body = render_outbound(msg, to="123")
    assert len(body["message"]["quick_replies"]) == 13


def test_ig_quick_reply_title_trim():
    from app.channels.interactive_builder import render_outbound
    from app.channels.types import InteractiveChoice, OutboundMessage

    long_title = "A" * 30
    msg = OutboundMessage(
        channel="instagram",
        recipient_id="123",
        text="Pick",
        choices=[InteractiveChoice(id="x", title=long_title)],
        choice_style="quick_replies",
    )
    body = render_outbound(msg, to="123")
    assert len(body["message"]["quick_replies"][0]["title"]) == 20


# ── Gate uses normalized model ────────────────────────────────────────────────


def test_gate_normalized_matches_legacy(wa_tenant):
    from app.channels.whatsapp_entry import entry_value_to_normalized
    from app.gate import check_gate, check_gate_normalized

    entry = _wa_text_payload("Bahi POS test")["entry"][0]["changes"][0]["value"]
    legacy = check_gate(entry, active_session=False, tenant=wa_tenant)
    nm = entry_value_to_normalized(entry, PID)
    norm = check_gate_normalized(nm, active_session=False, tenant=wa_tenant)
    assert legacy.allowed == norm.allowed
    assert legacy.sender == norm.sender
    assert legacy.lead_source == norm.lead_source


# ── WhatsApp webhook path unchanged ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_whatsapp_webhook_still_triggers_lead(client, wa_tenant, monkeypatch):
    from unittest.mock import AsyncMock

    import app.main as main_mod

    mock_send = AsyncMock(return_value=True)
    monkeypatch.setattr(main_mod, "send_whatsapp_message", mock_send)
    fake = type("R", (), {"content": [type("C", (), {"text": "Reply"})()]})()
    main_mod.anthropic_client.messages.create = AsyncMock(return_value=fake)

    r = await client.post("/webhook", json=_wa_text_payload("Bahi POS"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert mock_send.called


@pytest.mark.asyncio
async def test_instagram_unconfigured_tenant_ignored(client, wa_tenant):
    r = await client.post("/webhook", json=_ig_text_payload("hello"))
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"


def test_detect_channel_shapes():
    from app.channels.router import detect_channel

    assert detect_channel(_wa_text_payload("x")) == "whatsapp"
    assert detect_channel(_ig_text_payload("x")) == "instagram"
    assert detect_channel(_messenger_text_payload("x")) == "messenger"
    assert detect_channel({"random": True}) is None
