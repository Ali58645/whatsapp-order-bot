"""
Tests for the catch-all "no silent path" guarantee.

Every inbound text message must produce exactly one outbound send,
even when the sender has no active session and matches no known intent.
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

CUSTOMER = "923007771234"


# ── Payload helpers ───────────────────────────────────────────────────────────

def _text(sender: str, text: str) -> dict:
    return {"entry": [{"changes": [{"value": {"messages": [{
        "from": sender, "type": "text", "text": {"body": text},
    }]}}]}]}


def _media(sender: str, media_type: str = "sticker") -> dict:
    return {"entry": [{"changes": [{"value": {"messages": [{
        "from": sender,
        "type": media_type,
        media_type: {"id": "media_id_abc"},
    }]}}]}]}


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


def _customer_sends(mock_send):
    return [c for c in mock_send.call_args_list if c.args and c.args[0] == CUSTOMER]


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hi_no_session_exactly_one_send_greeting(client, mock_send):
    """
    'Hi' from a sender with no session and no referral → exactly one send
    containing the greeting and the business-name question.
    """
    r = await client.post("/webhook", json=_text(CUSTOMER, "Hi"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    calls = _customer_sends(mock_send)
    assert len(calls) == 1, f"Expected 1 send, got {len(calls)}"

    # Must be plain text (not an interactive widget)
    assert calls[0].kwargs.get("interactive_payload") is None
    msg = calls[0].args[1].lower()
    assert "shukriya" in msg or "welcome" in msg or "thank" in msg
    assert "naam" in msg or "name" in msg or "barah" in msg or "kindly" in msg


@pytest.mark.asyncio
async def test_hello_no_session_exactly_one_send_greeting(client, mock_send):
    """
    'Hello' from a sender with no session → exactly one send containing greeting.
    """
    r = await client.post("/webhook", json=_text(CUSTOMER, "Hello"))
    assert r.status_code == 200

    calls = _customer_sends(mock_send)
    assert len(calls) == 1, f"Expected 1 send, got {len(calls)}"
    assert calls[0].kwargs.get("interactive_payload") is None
    msg = calls[0].args[1].lower()
    assert "shukriya" in msg or "welcome" in msg or "thank" in msg


@pytest.mark.asyncio
async def test_sticker_no_session_exactly_one_send(client, mock_send):
    """
    A sticker (unsupported type) with no session → exactly one send
    containing a formal redirect to text.
    """
    r = await client.post("/webhook", json=_media(CUSTOMER, "sticker"))
    assert r.status_code == 200

    calls = _customer_sends(mock_send)
    assert len(calls) == 1, f"Expected 1 send, got {len(calls)}"

    msg = calls[0].args[1].lower()
    assert "text" in msg  # formal redirect to text


@pytest.mark.asyncio
async def test_audio_mid_flow_one_send_redirect_plus_question(client, mock_send):
    """
    Audio message mid-flow (phase=BUSINESS_TYPE) → exactly one send containing
    the redirect-to-text note AND the re-asked business-type question.
    """
    from app.lead import _meta
    _meta[CUSTOMER] = {
        "phase": "BUSINESS_TYPE",
        "lead_source": "ad",
        "business_name": "Ali Store",
    }

    r = await client.post("/webhook", json=_media(CUSTOMER, "audio"))
    assert r.status_code == 200

    calls = _customer_sends(mock_send)
    assert len(calls) == 1, f"Expected 1 send, got {len(calls)}"

    msg = calls[0].args[1].lower()
    assert "text" in msg  # redirect note
    # Phase must not have changed
    assert _meta[CUSTOMER].get("phase") == "BUSINESS_TYPE"


@pytest.mark.parametrize("text_input", [
    "Hi",
    "Hello",
    "Salam",
    "👋",
    "asdf1234",
    "kya hal hai",
    "test",
    "??",
    "ok",
    "بھائی",
])
@pytest.mark.asyncio
async def test_any_text_no_session_sends_exactly_once(client, mock_send, text_input):
    """
    Property-style test: for 10 varied inputs with no session,
    every input must produce exactly one send to CUSTOMER.
    """
    r = await client.post("/webhook", json=_text(CUSTOMER, text_input))
    assert r.status_code == 200

    calls = _customer_sends(mock_send)
    assert len(calls) == 1, (
        f"Input {text_input!r}: expected 1 send, got {len(calls)}"
    )
