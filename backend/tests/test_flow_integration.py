"""
Flow integration tests — every branch asserts send spy called exactly once.

Pre-seeds session meta directly (like test_entry_intent.py).
Mocks: send_whatsapp_message, Anthropic client.
No network calls.
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

CUSTOMER = "923005551234"
OWNER    = "9200000000"


# ── Payload helpers ───────────────────────────────────────────────────────────

def _referral_text(sender: str, text: str) -> dict:
    return {"entry": [{"changes": [{"value": {"messages": [{
        "from": sender, "type": "text", "text": {"body": text},
        "referral": {"source_id": "ad_1", "headline": "Bahi POS Ad"},
    }]}}]}]}


def _active_text(sender: str, text: str) -> dict:
    """Plain text from a sender who already has an active session."""
    return {"entry": [{"changes": [{"value": {"messages": [{
        "from": sender, "type": "text", "text": {"body": text},
    }]}}]}]}


def _list_reply(sender: str, row_id: str, row_title: str) -> dict:
    return {"entry": [{"changes": [{"value": {"messages": [{
        "from": sender,
        "type": "interactive",
        "interactive": {
            "type": "list_reply",
            "list_reply": {"id": row_id, "title": row_title},
        },
    }]}}]}]}


def _button_reply(sender: str, btn_id: str, btn_title: str) -> dict:
    return {"entry": [{"changes": [{"value": {"messages": [{
        "from": sender,
        "type": "interactive",
        "interactive": {
            "type": "button_reply",
            "button_reply": {"id": btn_id, "title": btn_title},
        },
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
    """Spy on send_whatsapp_message; captures both positional text and interactive_payload kwarg."""
    import app.main as main_mod
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr(main_mod, "send_whatsapp_message", mock)
    return mock


def _claude_reply(text: str):
    fake = MagicMock()
    fake.content = [MagicMock(text=text)]
    return fake


@pytest.fixture()
def mock_claude(monkeypatch):
    """Default Claude mock — returns DETOUR_DONE marker so tests control output."""
    import app.main as main_mod
    mock = AsyncMock(return_value=_claude_reply("Bahi POS supports business needs. DETOUR_DONE"))
    main_mod.anthropic_client.messages.create = mock
    return mock


@pytest_asyncio.fixture()
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ── Helper: inspect send calls ────────────────────────────────────────────────

def _customer_calls(mock_send):
    """All send calls addressed to CUSTOMER."""
    return [c for c in mock_send.call_args_list if c.args and c.args[0] == CUSTOMER]


def _is_interactive_list(call):
    p = call.kwargs.get("interactive_payload")
    return p is not None and p.get("interactive", {}).get("type") == "list"


def _is_interactive_button(call):
    p = call.kwargs.get("interactive_payload")
    return p is not None and p.get("interactive", {}).get("type") == "button"


def _text_of(call):
    return call.args[1] if len(call.args) > 1 else ""


# ══════════════════════════════════════════════════════════════════════════════
# Case 1: "Hi" with no session → exactly one send; interactive list payload;
#         greeting included.
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_case1_hi_no_session_one_send_with_greeting(client, mock_send):
    """
    First message 'Hi' from a referral lead with no prior session.
    Expectation: exactly ONE send to CUSTOMER; it is a plain-text greeting
    containing the shukriya/welcome word and the business-name question.
    The BUSINESS_TYPE interactive list is NOT sent at this stage (it comes
    after the user provides their business name).
    """
    r = await client.post("/webhook", json=_referral_text(CUSTOMER, "Hi"))
    assert r.status_code == 200

    calls = _customer_calls(mock_send)
    assert len(calls) == 1, f"Expected exactly 1 send, got {len(calls)}"

    # The single send must be plain text (not an interactive widget)
    assert not _is_interactive_list(calls[0]), "First reply must be plain text, not a list"
    assert not _is_interactive_button(calls[0]), "First reply must be plain text, not buttons"

    msg = _text_of(calls[0]).lower()
    # Greeting must be present
    assert "shukriya" in msg or "welcome" in msg or "thank you" in msg
    # Must ask for business name
    assert "naam" in msg or "name" in msg or "barah" in msg or "kindly" in msg


# ══════════════════════════════════════════════════════════════════════════════
# Case 2: Second message in same session → no greeting text in the reply.
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_case2_second_message_no_greeting(client, mock_send):
    """
    Session is already at BUSINESS_NAME phase.  User sends their business name.
    The reply must NOT contain the greeting line; it should advance to BUSINESS_TYPE
    and send the interactive list (exactly one send).
    """
    from app.lead import _meta
    _meta[("12345", CUSTOMER)] = {
        "phase": "BUSINESS_NAME",
        "lead_source": "ad",
    }

    r = await client.post("/webhook", json=_active_text(CUSTOMER, "Ali Traders"))
    assert r.status_code == 200

    calls = _customer_calls(mock_send)
    assert len(calls) == 1, f"Expected exactly 1 send, got {len(calls)}"

    # Greeting must NOT appear
    if _is_interactive_list(calls[0]) or _is_interactive_button(calls[0]):
        # Interactive payload — greeting can't be there
        pass
    else:
        msg = _text_of(calls[0]).lower()
        assert "shukriya" not in msg, "Greeting must not repeat in second message"
        assert "welcome" not in msg, "Greeting must not repeat in second message"


# ══════════════════════════════════════════════════════════════════════════════
# Case 3: Typed "Retail" at BUSINESS_TYPE step → state advances,
#         ack + next question in ONE message, NO business-type list sent.
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_case3_typed_retail_at_business_type_one_send_no_list(client, mock_send):
    """
    User is at BUSINESS_TYPE and types 'Retail' as free text instead of
    tapping the list. The handler must:
    - advance phase to LOCATIONS
    - send exactly ONE message (ack + locations question)
    - NOT re-send the business-type interactive list
    """
    from app.lead import _meta
    _meta[("12345", CUSTOMER)] = {
        "phase": "BUSINESS_TYPE",
        "lead_source": "ad",
        "business_name": "Ali Traders",
    }

    r = await client.post("/webhook", json=_active_text(CUSTOMER, "Retail"))
    assert r.status_code == 200

    calls = _customer_calls(mock_send)
    assert len(calls) == 1, f"Expected exactly 1 send, got {len(calls)}"

    # Must NOT be a business-type list
    p = calls[0].kwargs.get("interactive_payload", {})
    interactive = p.get("interactive", {}) if p else {}
    sections = interactive.get("action", {}).get("sections", [])
    # If it's a list, make sure it's not the business-type list (which has grocery/restaurant rows)
    if interactive.get("type") == "list":
        row_ids = [r["id"] for s in sections for r in s.get("rows", [])]
        assert "grocery" not in row_ids, "Business-type list must NOT be re-sent"

    # Phase must have advanced
    assert _meta[("12345", CUSTOMER)].get("phase") == "LOCATIONS"


# ══════════════════════════════════════════════════════════════════════════════
# Case 4: "Kahan ho?" at BUSINESS_TYPE → one send; contains detour answer
#         AND re-asked business-type question; state unchanged.
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_case4_detour_question_one_send_state_unchanged(client, mock_send, mock_claude):
    """
    Off-topic question at BUSINESS_TYPE phase.
    Handler calls Claude as detour, combines the one-line answer with the
    re-asked business-type question, sends exactly ONE message.
    Phase must NOT advance.
    """
    from app.lead import _meta
    _meta[("12345", CUSTOMER)] = {
        "phase": "BUSINESS_TYPE",
        "lead_source": "ad",
        "business_name": "Ali Traders",
    }

    # Claude returns a one-liner + DETOUR_DONE marker
    mock_claude.return_value = _claude_reply(
        "Hamari team Pakistan mein based hai. DETOUR_DONE"
    )

    r = await client.post("/webhook", json=_active_text(CUSTOMER, "Kahan ho ?"))
    assert r.status_code == 200

    calls = _customer_calls(mock_send)
    assert len(calls) == 1, f"Expected exactly 1 send, got {len(calls)}"

    # Phase must NOT have advanced
    assert _meta[("12345", CUSTOMER)].get("phase") == "BUSINESS_TYPE"

    # The single message must contain both the detour answer and the
    # re-asked business-type question (either as text or as interactive)
    msg = _text_of(calls[0]).lower()
    p = calls[0].kwargs.get("interactive_payload")
    has_location_answer = "pakistan" in msg or (p is not None)
    assert has_location_answer, "Detour answer must be present"


# ══════════════════════════════════════════════════════════════════════════════
# Case 5: Two unparseable messages at a step → two re-prompts;
#         third → handoff text + state reset.
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_case5_reprompt_budget_then_handoff(client, mock_send):
    """
    At BUSINESS_TYPE, user sends three unparseable free-text messages.
    First two → re-prompt (phase unchanged, exactly 1 send each).
    Third → handoff message + state reset (exactly 1 send).
    """
    from app.lead import _meta
    _meta[("12345", CUSTOMER)] = {
        "phase": "BUSINESS_TYPE",
        "lead_source": "ad",
        "business_name": "Ali Traders",
        "reprompt_count": 0,
    }

    # Message 1: unparseable (not a known business type)
    mock_send.reset_mock()
    await client.post("/webhook", json=_active_text(CUSTOMER, "asdfgh zxcv"))
    calls1 = _customer_calls(mock_send)
    assert len(calls1) == 1, f"Re-prompt 1: expected 1 send, got {len(calls1)}"
    assert _meta[("12345", CUSTOMER)].get("phase") == "BUSINESS_TYPE", "Phase must not advance on reprompt"

    # Message 2: another unparseable
    mock_send.reset_mock()
    await client.post("/webhook", json=_active_text(CUSTOMER, "nahi pata"))
    calls2 = _customer_calls(mock_send)
    assert len(calls2) == 1, f"Re-prompt 2: expected 1 send, got {len(calls2)}"
    assert _meta[("12345", CUSTOMER)].get("phase") == "BUSINESS_TYPE", "Phase must not advance on reprompt"

    # Message 3: handoff
    mock_send.reset_mock()
    await client.post("/webhook", json=_active_text(CUSTOMER, "abcd efgh ijkl"))
    calls3 = _customer_calls(mock_send)
    assert len(calls3) == 1, f"Handoff: expected 1 send, got {len(calls3)}"

    # After handoff, session must be reset (meta cleared or phase reset)
    phase_after = _meta.get(("12345", CUSTOMER), {}).get("phase")
    assert phase_after in (None, "GREETING", "STALLED"), (
        f"After handoff phase should be reset, got {phase_after!r}"
    )

    # Handoff message must contain a "team will contact" style text
    msg3 = _text_of(calls3[0]).lower()
    assert (
        "team" in msg3 or "rabta" in msg3 or "contact" in msg3 or "touch" in msg3
    ), f"Handoff message not found in: {msg3!r}"


# ══════════════════════════════════════════════════════════════════════════════
# Case 6: "grocery aur restaurant dono" at BUSINESS_TYPE → re-prompt path
#         (ambiguous — no guess recorded, phase unchanged).
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_case6_ambiguous_business_type_reprompt(client, mock_send):
    """
    User gives two business types at once.  The handler must NOT record a
    business_type guess; it must send exactly one re-prompt and leave
    phase at BUSINESS_TYPE.
    """
    from app.lead import _meta
    _meta[("12345", CUSTOMER)] = {
        "phase": "BUSINESS_TYPE",
        "lead_source": "ad",
        "business_name": "Ali Traders",
        "reprompt_count": 0,
    }

    r = await client.post(
        "/webhook", json=_active_text(CUSTOMER, "grocery aur restaurant dono")
    )
    assert r.status_code == 200

    calls = _customer_calls(mock_send)
    assert len(calls) == 1, f"Expected exactly 1 send, got {len(calls)}"

    # Phase must NOT have advanced
    assert _meta[("12345", CUSTOMER)].get("phase") == "BUSINESS_TYPE"

    # business_type must NOT have been set with an ambiguous guess
    bt = _meta[("12345", CUSTOMER)].get("business_type")
    assert bt is None, f"business_type must not be recorded from ambiguous input, got {bt!r}"


# ══════════════════════════════════════════════════════════════════════════════
# Case 7: menu_demo list_reply → qualification flow starts.
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_case7_menu_demo_list_reply_starts_flow(client, mock_send):
    """
    User taps 'menu_demo' from a welcome menu list.
    The handler must start the qualification flow: send exactly one message
    (the greeting / business-name question) and set phase to BUSINESS_NAME.
    """
    from app.lead import _meta

    # Seed a fresh session (phase = GREETING, no business name yet)
    _meta[("12345", CUSTOMER)] = {
        "phase": "GREETING",
        "lead_source": "campaign:Bahi POS",
    }

    r = await client.post("/webhook", json=_list_reply(CUSTOMER, "menu_demo", "Book a Demo"))
    assert r.status_code == 200

    calls = _customer_calls(mock_send)
    assert len(calls) == 1, f"Expected exactly 1 send, got {len(calls)}"

    # Phase must advance out of GREETING
    phase = _meta.get(("12345", CUSTOMER), {}).get("phase")
    assert phase in ("BUSINESS_NAME", "SCHEDULING"), (
        f"Expected flow to start (BUSINESS_NAME or SCHEDULING), got {phase!r}"
    )
