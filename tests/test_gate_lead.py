"""
Tests for the activation gate and Bahi POS lead flow.

No network calls — Graph API and Claude are fully mocked.
All tests run with FLOW_MODE=lead.
"""

import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

# ── Env stubs — must be set before any app import ────────────────────────────
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


# ── Helpers ───────────────────────────────────────────────────────────────────

CUSTOMER   = "923001111111"
BUSINESS   = "92300BUSINESS"
OWNER      = "9200000000"


def _text_payload(sender: str, text: str, referral: dict = None) -> dict:
    msg = {"from": sender, "type": "text", "text": {"body": text}}
    if referral:
        msg["referral"] = referral
    return {
        "entry": [{"changes": [{"value": {"messages": [msg]}}]}]
    }


def _echo_payload(business_number: str, customer_number: str, text: str) -> dict:
    """
    Simulates a message sent FROM the business app to a customer.
    The 'from' field is the business number; contacts list contains the customer.
    """
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": business_number,
                        "type": "text",
                        "text": {"body": text},
                    }],
                    "contacts": [{"wa_id": customer_number, "profile": {"name": "Customer"}}],
                }
            }]
        }]
    }


def _referral_payload(sender: str, text: str) -> dict:
    return _text_payload(
        sender, text,
        referral={"source_id": "ad_123", "headline": "Get Bahi POS", "body": "Free demo"},
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_state():
    """Wipe all in-memory state between tests."""
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


def _make_claude_reply(text: str):
    fake = MagicMock()
    fake.content = [MagicMock(text=text)]
    return fake


@pytest.fixture()
def mock_claude(monkeypatch):
    """Returns a factory: call mock_claude(text) to set the next reply."""
    import app.main as main_mod
    mock = AsyncMock(return_value=_make_claude_reply("Aapka business ka naam kya hai?"))
    main_mod.anthropic_client.messages.create = mock
    return mock


@pytest_asyncio.fixture()
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_echo_message_ignored(client, mock_send):
    """Message from our own business number → silently ignored, no reply."""
    r = await client.post("/webhook", json=_text_payload(BUSINESS, "Test message"))
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_contact_no_referral_gets_greeting(client, mock_send):
    """
    Random contact with no referral and no campaign phrase → bot now responds
    with the greeting (catch-all; no message may be silently dropped for text).
    Exactly one send.
    """
    r = await client.post("/webhook", json=_text_payload(CUSTOMER, "Hello there"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    calls = [c for c in mock_send.call_args_list if c.args and c.args[0] == CUSTOMER]
    assert len(calls) == 1, f"Expected 1 send, got {len(calls)}"


@pytest.mark.asyncio
async def test_referral_message_triggers_greeting(client, mock_send, mock_claude):
    """Message with referral object → bot activates, greeting sent to customer."""
    mock_claude.return_value = _make_claude_reply(
        "Assalam o Alaikum! Bahi POS mein interest ka shukriya 🙏 Aap ke business/shop ka naam kya hai?"
    )
    r = await client.post("/webhook", json=_referral_payload(CUSTOMER, "Hi"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    recipients = [c.args[0] for c in mock_send.call_args_list]
    assert CUSTOMER in recipients


@pytest.mark.asyncio
async def test_campaign_phrase_triggers_greeting(client, mock_send, mock_claude):
    """Message containing campaign phrase → bot activates."""
    mock_claude.return_value = _make_claude_reply(
        "Assalam o Alaikum! Bahi POS mein interest ka shukriya 🙏"
    )
    r = await client.post("/webhook", json=_text_payload(CUSTOMER, "Bahi POS ke baare mein batao"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    mock_send.assert_called()
    recipients = [c.args[0] for c in mock_send.call_args_list]
    assert CUSTOMER in recipients


@pytest.mark.asyncio
async def test_active_session_continues_without_referral(client, mock_send, mock_claude):
    """
    Once a lead session is active, subsequent messages without referral/phrase
    still get replies (session continuity).
    """
    from app.lead import _meta
    # Manually plant an active lead session
    _meta[CUSTOMER] = {"phase": "BUSINESS_TYPE", "lead_source": "ad", "business_name": "Ali Shop"}

    mock_claude.return_value = _make_claude_reply("Ali Shop kis type ka business hai?")
    r = await client.post("/webhook", json=_text_payload(CUSTOMER, "Retail store"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    recipients = [c.args[0] for c in mock_send.call_args_list]
    assert CUSTOMER in recipients


@pytest.mark.asyncio
async def test_manual_app_reply_mutes_contact_and_subsequent_message_ignored(client, mock_send, mock_claude):
    """
    An outbound echo (business app manual reply) mutes the contact for 24h.
    The next inbound message from that contact is then silently ignored.
    """
    # First: send an outbound echo — business replied manually to CUSTOMER
    r1 = await client.post("/webhook", json=_echo_payload(BUSINESS, CUSTOMER, "Haan bhai, kal milte hain"))
    assert r1.status_code == 200
    # No reply should be sent by bot for an echo
    mock_send.assert_not_called()

    # Now a follow-up message from CUSTOMER should be ignored (muted)
    r2 = await client.post("/webhook", json=_text_payload(CUSTOMER, "Bahi POS chahiye"))
    assert r2.status_code == 200
    assert r2.json() == {"status": "ignored"}
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_confirmed_triggers_lead_card_to_owner(client, mock_send, mock_claude):
    """
    When Claude outputs LEAD_CONFIRMED, a lead card is sent to OWNER_WHATSAPP
    with the correct fields.
    """
    from app.lead import _meta
    _meta[CUSTOMER] = {
        "phase": "SCHEDULING",
        "lead_source": "campaign:Bahi POS",
        "business_name": "Karachi Mart",
        "business_type": "Retail",
        "locations": "2",
        "current_system": "Manual Register",
        "demo_slot": "Kal 11am",
    }

    mock_claude.return_value = _make_claude_reply(
        "Perfect! Kal 11am ko hamari team aap se contact karegi. Shukriya!\nLEAD_CONFIRMED"
    )

    r = await client.post("/webhook", json=_text_payload(CUSTOMER, "11am theek hai"))
    assert r.status_code == 200

    # Find the call to OWNER
    owner_calls = [c for c in mock_send.call_args_list if c.args[0] == OWNER]
    assert owner_calls, "Lead card should have been sent to owner"

    card_text = owner_calls[0].args[1]
    assert "Karachi Mart" in card_text
    assert "Retail" in card_text
    assert "Kal 11am" in card_text
    assert CUSTOMER in card_text


@pytest.mark.asyncio
async def test_price_question_mid_flow_does_not_break_phase(client, mock_send, mock_claude):
    """
    A price question mid-flow should be deflected by Claude without advancing
    or resetting the phase.  The bot must still reply 200 and send a message.
    """
    from app.lead import _meta
    _meta[CUSTOMER] = {
        "phase": "LOCATIONS",
        "lead_source": "ad",
        "business_name": "Fast Mart",
        "business_type": "Grocery",
    }

    mock_claude.return_value = _make_claude_reply(
        "Pricing business size par depend karti hai, demo mein exact quote milta hai 👍 "
        "Aap ki kitni branches hain?"
    )

    r = await client.post("/webhook", json=_text_payload(CUSTOMER, "price kya hai?"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    # Phase should NOT have been reset or jumped forward beyond what's expected
    assert _meta[CUSTOMER]["phase"] in ("LOCATIONS", "CURRENT_SYSTEM")

    # Bot must have replied
    recipients = [c.args[0] for c in mock_send.call_args_list]
    assert CUSTOMER in recipients
