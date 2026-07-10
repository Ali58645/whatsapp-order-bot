"""
Tests for interactive message builders, inbound reply parsing,
and the lead flow's interactive phase handling.

No network calls — everything mocked.
"""

import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
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


# ── Payload helpers ───────────────────────────────────────────────────────────

def _interactive_button_payload(sender: str, button_id: str, button_title: str) -> dict:
    """Simulates an inbound button_reply webhook event."""
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": sender,
                        "type": "interactive",
                        "interactive": {
                            "type": "button_reply",
                            "button_reply": {"id": button_id, "title": button_title},
                        },
                    }]
                }
            }]
        }]
    }


def _interactive_list_payload(sender: str, row_id: str, row_title: str) -> dict:
    """Simulates an inbound list_reply webhook event."""
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": sender,
                        "type": "interactive",
                        "interactive": {
                            "type": "list_reply",
                            "list_reply": {"id": row_id, "title": row_title},
                        },
                    }]
                }
            }]
        }]
    }


def _text_payload(sender: str, text: str) -> dict:
    return {
        "entry": [{"changes": [{"value": {"messages": [
            {"from": sender, "type": "text", "text": {"body": text}}
        ]}}]}]
    }


def _malformed_interactive_payload(sender: str) -> dict:
    """Interactive message with missing inner structure."""
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": sender,
                        "type": "interactive",
                        "interactive": {},    # no type, no button_reply/list_reply
                    }]
                }
            }]
        }]
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


def _make_claude_reply(text: str):
    fake = MagicMock()
    fake.content = [MagicMock(text=text)]
    return fake


@pytest.fixture()
def mock_claude(monkeypatch):
    import app.main as main_mod
    mock = AsyncMock(return_value=_make_claude_reply("OK"))
    main_mod.anthropic_client.messages.create = mock
    return mock


@pytest_asyncio.fixture()
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Unit tests: builders ──────────────────────────────────────────────────────

def test_build_buttons_structure():
    """build_buttons returns correct Cloud API payload shape."""
    from app.interactive import build_buttons
    p = build_buttons("9230011", "Choose one:", [("id1", "Option A"), ("id2", "Option B")])
    assert p["type"] == "interactive"
    assert p["interactive"]["type"] == "button"
    assert p["interactive"]["body"]["text"] == "Choose one:"
    btns = p["interactive"]["action"]["buttons"]
    assert len(btns) == 2
    assert btns[0]["type"] == "reply"
    assert btns[0]["reply"]["id"] == "id1"
    assert btns[1]["reply"]["title"] == "Option B"


def test_build_buttons_title_truncated():
    """Titles longer than 20 chars are silently truncated."""
    from app.interactive import build_buttons
    long_title = "A" * 30
    p = build_buttons("9230011", "body", [("id1", long_title)])
    assert len(p["interactive"]["action"]["buttons"][0]["reply"]["title"]) == 20


def test_build_buttons_max_exceeded_raises():
    from app.interactive import build_buttons
    with pytest.raises(ValueError, match="max 3"):
        build_buttons("123", "body", [("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")])


def test_build_list_structure():
    """build_list returns correct Cloud API payload shape."""
    from app.interactive import build_list
    rows = [("r1", "Retail", "Dukaan"), ("r2", "Restaurant", "Food")]
    p = build_list("9230011", "Choose type:", "Options dekhein", rows)
    assert p["type"] == "interactive"
    assert p["interactive"]["type"] == "list"
    assert p["interactive"]["action"]["button"] == "Options dekhein"
    sections = p["interactive"]["action"]["sections"]
    assert len(sections) == 1
    assert sections[0]["rows"][0]["id"] == "r1"
    assert sections[0]["rows"][1]["title"] == "Restaurant"


def test_build_list_max_exceeded_raises():
    from app.interactive import build_list
    with pytest.raises(ValueError, match="max 10"):
        build_list("123", "b", "btn", [("x", "t", "d")] * 11)


def test_parse_interactive_reply_button():
    from app.interactive import parse_interactive_reply
    msg = {"interactive": {"type": "button_reply", "button_reply": {"id": "loc_1", "title": "1"}}}
    rid, rtitle = parse_interactive_reply(msg)
    assert rid == "loc_1"
    assert rtitle == "1"


def test_parse_interactive_reply_list():
    from app.interactive import parse_interactive_reply
    msg = {"interactive": {"type": "list_reply", "list_reply": {"id": "grocery", "title": "Grocery / Kiryana"}}}
    rid, rtitle = parse_interactive_reply(msg)
    assert rid == "grocery"
    assert rtitle == "Grocery / Kiryana"


def test_parse_interactive_reply_malformed_returns_none():
    from app.interactive import parse_interactive_reply
    assert parse_interactive_reply({}) == (None, None)
    assert parse_interactive_reply({"interactive": {}}) == (None, None)
    assert parse_interactive_reply({"interactive": {"type": "button_reply"}}) == (None, None)


# ── Integration tests: webhook interactive flow ───────────────────────────────

@pytest.mark.asyncio
async def test_button_reply_advances_phase_deterministically(client, mock_send, mock_claude):
    """
    A button tap at LOCATIONS phase advances to CURRENT_SYSTEM without LLM call,
    then the interactive widget for CURRENT_SYSTEM is sent.
    """
    from app.lead import _meta
    _meta[CUSTOMER] = {
        "phase": "LOCATIONS",
        "lead_source": "ad",
        "business_name": "Ali Shop",
        "business_type": "Grocery / Kiryana",
    }

    r = await client.post("/webhook", json=_interactive_button_payload(CUSTOMER, "loc_1", "1"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    # LLM must NOT have been called
    mock_claude.assert_not_called()

    # Phase must have advanced
    assert _meta[CUSTOMER]["phase"] == "CURRENT_SYSTEM"
    assert _meta[CUSTOMER]["locations"] == "1"

    # An interactive payload (CURRENT_SYSTEM buttons) must have been sent
    interactive_calls = [
        c for c in mock_send.call_args_list
        if c.kwargs.get("interactive_payload") is not None
    ]
    assert interactive_calls, "Expected interactive widget to be sent for next phase"
    sent_payload = interactive_calls[0].kwargs["interactive_payload"]
    assert sent_payload["interactive"]["type"] == "button"


@pytest.mark.asyncio
async def test_list_reply_stores_business_type_correctly(client, mock_send, mock_claude):
    """
    A list_reply for business type stores the human-readable label and advances phase.
    """
    from app.lead import _meta
    _meta[CUSTOMER] = {
        "phase": "BUSINESS_TYPE",
        "lead_source": "ad",
        "business_name": "Lahore Pharmacy",
    }

    r = await client.post("/webhook", json=_interactive_list_payload(CUSTOMER, "pharmacy", "Pharmacy"))
    assert r.status_code == 200

    assert _meta[CUSTOMER]["business_type"] == "Pharmacy"
    assert _meta[CUSTOMER]["phase"] == "LOCATIONS"
    mock_claude.assert_not_called()


@pytest.mark.asyncio
async def test_free_text_at_option_phase_goes_through_llm(client, mock_send, mock_claude):
    """
    Free-text at BUSINESS_TYPE phase (instead of tapping the list) still works —
    goes through the LLM as normal.
    """
    from app.lead import _meta
    _meta[CUSTOMER] = {
        "phase": "BUSINESS_TYPE",
        "lead_source": "ad",
        "business_name": "Fast Mart",
    }

    mock_claude.return_value = _make_claude_reply("Kitni branches hain?")

    r = await client.post("/webhook", json=_text_payload(CUSTOMER, "Mera furniture ka shop hai"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    # LLM must have been called
    mock_claude.assert_called_once()

    # Bot replied to customer
    recipients = [c.args[0] for c in mock_send.call_args_list]
    assert CUSTOMER in recipients


@pytest.mark.asyncio
async def test_slot_other_captures_custom_time(client, mock_send, mock_claude):
    """
    Tapping slot_other sends a follow-up question; the next text message is
    captured as demo_slot and the session is confirmed.
    """
    from app.lead import _meta
    _meta[CUSTOMER] = {
        "phase": "SCHEDULING",
        "lead_source": "ad",
        "business_name": "Zain Store",
        "business_type": "Retail",
        "locations": "1",
        "current_system": "Manual Register",
    }

    # Step 1: tap slot_other
    r1 = await client.post("/webhook", json=_interactive_button_payload(CUSTOMER, "slot_other", "Koi aur time"))
    assert r1.status_code == 200

    # Follow-up question must have been sent
    texts_sent = [c.args[1] for c in mock_send.call_args_list if c.args]
    assert any("din" in t.lower() or "time" in t.lower() for t in texts_sent)

    # awaiting_custom_slot flag must be set
    assert _meta[CUSTOMER].get("awaiting_custom_slot") is True

    # Clear send mock before step 2
    mock_send.reset_mock()

    # Step 2: send custom time as free text
    r2 = await client.post("/webhook", json=_text_payload(CUSTOMER, "Parso 3pm"))
    assert r2.status_code == 200

    # demo_slot must be captured
    # (session cleared after CONFIRMED, so we check what was forwarded to owner)
    owner_calls = [c for c in mock_send.call_args_list if c.args and c.args[0] == OWNER]
    assert owner_calls, "Lead card should have been sent to owner"
    card = owner_calls[0].args[1]
    assert "Parso 3pm" in card


@pytest.mark.asyncio
async def test_malformed_interactive_payload_ignored_returns_200(client, mock_send):
    """
    A malformed interactive payload (missing inner fields) must not crash —
    returns 200 with status ignored.
    """
    from app.lead import _meta
    _meta[CUSTOMER] = {
        "phase": "LOCATIONS",
        "lead_source": "ad",
        "business_name": "Test Shop",
    }

    r = await client.post("/webhook", json=_malformed_interactive_payload(CUSTOMER))
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}
    mock_send.assert_not_called()
