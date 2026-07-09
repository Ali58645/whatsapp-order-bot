"""
Tests for entry intent detection and the corresponding first-message responses.

No network calls — Graph API and Claude are fully mocked.
"""

import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport

# ── Env stubs ─────────────────────────────────────────────────────────────────
os.environ["WHATSAPP_VERIFY_TOKEN"]    = "testtoken"
os.environ["WHATSAPP_ACCESS_TOKEN"]    = "faketoken"
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "12345"
os.environ["OWNER_WHATSAPP"]           = "9200000000"
os.environ["ANTHROPIC_API_KEY"]        = "sk-ant-fake"
os.environ["FLOW_MODE"]                = "lead"
os.environ["BUSINESS_WA_ID"]           = "92300BUSINESS"
os.environ["CAMPAIGN_PHRASE"]          = "Bahi POS"
os.environ["DEMO_SLOT_1"]              = "Kal 11am"
os.environ["DEMO_SLOT_2"]              = "Kal 4pm"

CUSTOMER = "923001111111"
OWNER    = "9200000000"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _referral_text_payload(sender: str, text: str, headline: str = "Bahi POS Ad") -> dict:
    """Referral-activated first message (click-to-WhatsApp ad)."""
    return {
        "entry": [{"changes": [{"value": {"messages": [{
            "from": sender,
            "type": "text",
            "text": {"body": text},
            "referral": {
                "source_id": "ad_xyz",
                "headline": headline,
                "body": "Get your free demo today",
            },
        }]}}]}]
    }


def _referral_media_payload(sender: str, media_type: str = "audio") -> dict:
    """Referral-activated first message that is a voice note / image."""
    return {
        "entry": [{"changes": [{"value": {"messages": [{
            "from": sender,
            "type": media_type,
            media_type: {"id": "media_id_123"},
            "referral": {"source_id": "ad_xyz", "headline": "Bahi POS Ad"},
        }]}}]}]
    }


def _campaign_text_payload(sender: str, text: str) -> dict:
    """Campaign-phrase-activated first message."""
    return {
        "entry": [{"changes": [{"value": {"messages": [{
            "from": sender,
            "type": "text",
            "text": {"body": text},
        }]}}]}]
    }


# ── Fixtures ──────────────────────────────────────────────────────────────────

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
def mock_send(monkeypatch):
    import app.main as main_mod
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr(main_mod, "send_whatsapp_message", mock)
    return mock


@pytest_asyncio.fixture()
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Unit tests: classify_entry_intent ─────────────────────────────────────────

@pytest.mark.parametrize("text,expected_intent", [
    # ── GENERIC_INFO openers ──
    ("hi",                        "GENERIC_INFO"),
    ("Hello",                     "GENERIC_INFO"),
    ("AOA",                       "GENERIC_INFO"),
    ("Salam",                     "GENERIC_INFO"),
    ("interested",                "GENERIC_INFO"),
    ("info chahiye",              "GENERIC_INFO"),
    ("tell me more",              "GENERIC_INFO"),
    ("details batao",             "GENERIC_INFO"),
    # ── PRICE_FIRST openers ──
    ("price kya hai?",            "PRICE_FIRST"),
    ("kitne ki hai ye software",  "PRICE_FIRST"),
    ("cost kitna hai",            "PRICE_FIRST"),
    ("monthly charges?",          "PRICE_FIRST"),
    ("package rate batao",        "PRICE_FIRST"),
    # ── DEMO_FIRST openers ──
    ("demo chahiye",              "DEMO_FIRST"),
    ("meeting schedule karo",     "DEMO_FIRST"),
    ("dikhao please",             "DEMO_FIRST"),
    ("book a demo",               "DEMO_FIRST"),
    ("walkthrough chahiye",       "DEMO_FIRST"),
    # ── OTHER ──
    ("mujhe koi naya POS chahiye jo inventory bhi track kare", "OTHER"),
    ("hamare paas 5 branches hain", "OTHER"),
])
def test_classify_entry_intent(text, expected_intent):
    from app.lead import classify_entry_intent
    assert classify_entry_intent(text) == expected_intent


# ── Integration tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generic_info_opener_sends_greeting_with_value_line(client, mock_send):
    """
    GENERIC_INFO entry (e.g. 'hi') → greeting with shukriya + value statement
    + business name question. No LLM call. Phase advances to BUSINESS_NAME.
    """
    from app.lead import _meta
    r = await client.post("/webhook", json=_referral_text_payload(CUSTOMER, "hi"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    # One send call to customer
    texts = [c.args[1] for c in mock_send.call_args_list if c.args and c.args[0] == CUSTOMER]
    assert texts, "Expected a reply to customer"
    greeting = texts[0]
    assert "shukriya" in greeting.lower()
    assert "har hisaab" in greeting.lower()
    assert "naam" in greeting.lower()

    # Phase advanced without LLM
    assert _meta[CUSTOMER]["phase"] == "BUSINESS_NAME"
    assert _meta[CUSTOMER]["entry_intent"] == "GENERIC_INFO"


@pytest.mark.asyncio
async def test_price_first_gets_deflection_and_name_question(client, mock_send):
    """
    PRICE_FIRST opener → pricing deflection line + business name question
    in the same message. Phase set to BUSINESS_NAME.
    """
    from app.lead import _meta
    r = await client.post(
        "/webhook",
        json=_campaign_text_payload(CUSTOMER, "Bahi POS — price kya hai?"),
    )
    assert r.status_code == 200

    texts = [c.args[1] for c in mock_send.call_args_list if c.args and c.args[0] == CUSTOMER]
    assert texts
    msg = texts[0].lower()
    # Deflection keyword
    assert "15-minute" in msg or "demo mein" in msg or "exact quote" in msg
    # Still asks for name in same message
    assert "naam" in msg

    assert _meta[CUSTOMER]["phase"] == "BUSINESS_NAME"
    assert _meta[CUSTOMER]["entry_intent"] == "PRICE_FIRST"


@pytest.mark.asyncio
async def test_demo_first_jumps_to_scheduling_buttons(client, mock_send):
    """
    DEMO_FIRST opener → short greeting ack + scheduling buttons sent immediately.
    Phase set to SCHEDULING. No LLM call.
    """
    from app.lead import _meta
    r = await client.post("/webhook", json=_referral_text_payload(CUSTOMER, "demo chahiye"))
    assert r.status_code == 200

    # An interactive (scheduling) payload must have been sent
    interactive_calls = [
        c for c in mock_send.call_args_list
        if c.kwargs.get("interactive_payload") is not None
    ]
    assert interactive_calls, "Expected scheduling buttons to be sent for DEMO_FIRST"
    payload = interactive_calls[0].kwargs["interactive_payload"]
    assert payload["interactive"]["type"] == "button"
    # Verify it's the scheduling buttons by checking one of the slot ids
    btn_ids = [
        b["reply"]["id"]
        for b in payload["interactive"]["action"]["buttons"]
    ]
    assert "slot_1" in btn_ids

    assert _meta[CUSTOMER]["phase"] == "SCHEDULING"
    assert _meta[CUSTOMER]["entry_intent"] == "DEMO_FIRST"


@pytest.mark.asyncio
async def test_voice_note_first_gets_generic_greeting(client, mock_send):
    """
    First message is a voice note (audio) → GENERIC_INFO greeting with
    'text mein reply' note. Phase advances to BUSINESS_NAME.
    """
    from app.lead import _meta
    r = await client.post("/webhook", json=_referral_media_payload(CUSTOMER, "audio"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    texts = [c.args[1] for c in mock_send.call_args_list if c.args and c.args[0] == CUSTOMER]
    assert texts, "Expected a reply to customer"
    msg = texts[0].lower()
    assert "shukriya" in msg
    assert "text" in msg          # contains the 'text mein reply' note

    assert _meta[CUSTOMER]["phase"] == "BUSINESS_NAME"
    assert _meta[CUSTOMER]["entry_intent"] == "GENERIC_INFO"


@pytest.mark.asyncio
async def test_referral_headline_appears_on_lead_card_not_in_customer_message(client, mock_send):
    """
    Referral headline must appear in the lead card sent to the owner,
    but must NOT appear in any message sent to the customer.
    """
    from app.lead import _meta

    # Simulate a lead that's already at CONFIRMED with a referral headline stored
    _meta[CUSTOMER] = {
        "phase": "SCHEDULING",
        "lead_source": "Get Bahi POS",
        "referral_headline": "Summer Sale — Get Bahi POS Free Demo",
        "business_name": "Faisal Electronics",
        "business_type": "Electronics",
        "locations": "1",
        "current_system": "Manual register",
        "demo_slot": "Kal 11am",
    }

    # Trigger CONFIRMED via interactive slot_1 button tap
    r = await client.post("/webhook", json={
        "entry": [{"changes": [{"value": {"messages": [{
            "from": CUSTOMER,
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "slot_1", "title": "Kal 11am"},
            },
        }]}}]}]
    })
    assert r.status_code == 200

    owner_calls = [c for c in mock_send.call_args_list if c.args and c.args[0] == OWNER]
    customer_calls = [c for c in mock_send.call_args_list if c.args and c.args[0] == CUSTOMER]

    # Headline must be on the owner card
    assert owner_calls, "Lead card must have been sent to owner"
    card = owner_calls[0].args[1]
    assert "Summer Sale — Get Bahi POS Free Demo" in card

    # Headline must NOT appear in any customer-facing message
    for cc in customer_calls:
        msg = cc.args[1] if cc.args else ""
        assert "Summer Sale — Get Bahi POS Free Demo" not in msg, (
            f"Referral headline leaked into customer message: {msg!r}"
        )
