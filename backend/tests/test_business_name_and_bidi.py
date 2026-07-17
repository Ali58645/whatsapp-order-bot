"""
Tests for Bug 1 (BUSINESS_NAME deterministic capture) and
Bug 2 (no Arabic-script bidi characters in any template string).
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

CUSTOMER = "923004441234"


# ── Payload helpers ───────────────────────────────────────────────────────────

def _active_text(sender: str, text: str) -> dict:
    return {"entry": [{"changes": [{"value": {"messages": [{
        "from": sender, "type": "text", "text": {"body": text},
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


@pytest.fixture()
def mock_claude(monkeypatch):
    import app.main as main_mod
    fake = MagicMock()
    fake.content = [MagicMock(text="OK DETOUR_DONE")]
    mock = AsyncMock(return_value=fake)
    main_mod.anthropic_client.messages.create = mock
    return mock


@pytest_asyncio.fixture()
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _at_business_name(sender: str) -> dict:
    """Pre-seed meta at BUSINESS_NAME phase."""
    from app.lead import _meta
    _meta[("12345", sender)] = {"phase": "BUSINESS_NAME", "lead_source": "ad"}
    return _meta[("12345", sender)]


def _customer_sends(mock_send):
    return [c for c in mock_send.call_args_list if c.args and c.args[0] == CUSTOMER]


# ══════════════════════════════════════════════════════════════════════════════
# Bug 1 — BUSINESS_NAME deterministic capture
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_chargebyte_accepted_no_llm(client, mock_send, mock_claude):
    """
    'ChargeByte' at BUSINESS_NAME → name recorded, phase → BUSINESS_TYPE,
    exactly one send, Anthropic mock called ZERO times.
    """
    from app.lead import _meta
    _at_business_name(CUSTOMER)

    r = await client.post("/webhook", json=_active_text(CUSTOMER, "ChargeByte"))
    assert r.status_code == 200

    # LLM must NOT have been called
    mock_claude.assert_not_called()

    # Exactly one send to customer
    calls = _customer_sends(mock_send)
    assert len(calls) == 1, f"Expected 1 send, got {len(calls)}"

    # Name recorded
    assert _meta[("12345", CUSTOMER)]["business_name"] == "ChargeByte"

    # Phase advanced
    assert _meta[("12345", CUSTOMER)]["phase"] == "BUSINESS_TYPE"


@pytest.mark.asyncio
async def test_clinics_accepted_no_llm(client, mock_send, mock_claude):
    """
    'Clinics' at BUSINESS_NAME → name recorded, phase advances, no LLM call.
    """
    from app.lead import _meta
    _at_business_name(CUSTOMER)

    r = await client.post("/webhook", json=_active_text(CUSTOMER, "Clinics"))
    assert r.status_code == 200

    mock_claude.assert_not_called()

    calls = _customer_sends(mock_send)
    assert len(calls) == 1

    assert _meta[("12345", CUSTOMER)]["business_name"] == "Clinics"
    assert _meta[("12345", CUSTOMER)]["phase"] == "BUSINESS_TYPE"


@pytest.mark.asyncio
async def test_al_madina_kiryana_accepted_no_llm(client, mock_send, mock_claude):
    """
    'Al-Madina Kiryana Store' (4 words) → accepted verbatim, no LLM call.
    """
    from app.lead import _meta
    _at_business_name(CUSTOMER)

    r = await client.post(
        "/webhook", json=_active_text(CUSTOMER, "Al-Madina Kiryana Store")
    )
    assert r.status_code == 200

    mock_claude.assert_not_called()

    calls = _customer_sends(mock_send)
    assert len(calls) == 1

    assert _meta[("12345", CUSTOMER)]["business_name"] == "Al-Madina Kiryana Store"
    assert _meta[("12345", CUSTOMER)]["phase"] == "BUSINESS_TYPE"


@pytest.mark.asyncio
async def test_business_name_too_long_reprompts(client, mock_send, mock_claude):
    """
    A 7-word input at BUSINESS_NAME → re-prompt, phase unchanged, no LLM.
    """
    from app.lead import _meta
    _at_business_name(CUSTOMER)

    r = await client.post(
        "/webhook",
        json=_active_text(CUSTOMER, "I am not sure what my business name is"),
    )
    assert r.status_code == 200

    mock_claude.assert_not_called()

    calls = _customer_sends(mock_send)
    assert len(calls) == 1

    # Phase must NOT have advanced
    assert _meta[("12345", CUSTOMER)]["phase"] == "BUSINESS_NAME"
    # business_name must NOT have been set
    assert "business_name" not in _meta[("12345", CUSTOMER)]


@pytest.mark.asyncio
async def test_business_name_accepts_up_to_six_words(client, mock_send, mock_claude):
    """Exactly 6 words → accepted (boundary)."""
    from app.lead import _meta
    _at_business_name(CUSTOMER)

    r = await client.post(
        "/webhook",
        json=_active_text(CUSTOMER, "Karachi Super Mart And Trading Co"),
    )
    assert r.status_code == 200

    mock_claude.assert_not_called()
    assert _meta[("12345", CUSTOMER)]["business_name"] == "Karachi Super Mart And Trading Co"
    assert _meta[("12345", CUSTOMER)]["phase"] == "BUSINESS_TYPE"


@pytest.mark.asyncio
async def test_business_name_next_step_is_business_type_list(client, mock_send, mock_claude):
    """
    After accepting a business name, the single send must be the
    BUSINESS_TYPE interactive list widget (not a plain text ack).
    """
    _at_business_name(CUSTOMER)

    await client.post("/webhook", json=_active_text(CUSTOMER, "FastMart"))

    calls = _customer_sends(mock_send)
    assert len(calls) == 1

    # The send must be an interactive list
    p = calls[0].kwargs.get("interactive_payload")
    assert p is not None, "Expected interactive list payload"
    assert p["interactive"]["type"] == "list"
    # Must be the business-type list
    rows = p["interactive"]["action"]["sections"][0]["rows"]
    row_ids = [r["id"] for r in rows]
    assert "grocery" in row_ids


# ══════════════════════════════════════════════════════════════════════════════
# Bug 2 — No Arabic-script (U+0600–U+06FF) in any template string
# ══════════════════════════════════════════════════════════════════════════════

def _has_arabic_script(s: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in s)


def test_no_arabic_script_in_greeting_line():
    from app.lead import _GREETING_LINE
    for lang, text in _GREETING_LINE.items():
        assert not _has_arabic_script(text), (
            f"_GREETING_LINE[{lang!r}] contains Arabic-script characters: {text!r}"
        )


def test_no_arabic_script_in_all_templates():
    """
    Scan every string-valued template dict in lead.py for Arabic-script chars.
    """
    import app.lead as lead_mod

    template_dicts = [
        ("_GREETING_LINE",    lead_mod._GREETING_LINE),
        ("_VALUE_LINE",       lead_mod._VALUE_LINE),
        ("_Q_BUSINESS_NAME",  lead_mod._Q_BUSINESS_NAME),
        ("_Q_BUSINESS_TYPE",  lead_mod._Q_BUSINESS_TYPE),
        ("_Q_LOCATIONS",      lead_mod._Q_LOCATIONS),
        ("_Q_CURRENT_SYSTEM", lead_mod._Q_CURRENT_SYSTEM),
        ("_Q_SCHEDULING",     lead_mod._Q_SCHEDULING),
        ("_Q_CUSTOM_SLOT",    lead_mod._Q_CUSTOM_SLOT),
        ("_CONFIRM_SLOT",     lead_mod._CONFIRM_SLOT),
        ("_PRICING_TEXT",     lead_mod._PRICING_TEXT),
        ("_INFO_TEXT",        lead_mod._INFO_TEXT),
        ("_PRICE_DEFLECT_MID",lead_mod._PRICE_DEFLECT_MID),
        ("_MEDIA_REDIRECT",   lead_mod._MEDIA_REDIRECT),
        ("_HANDOFF",          lead_mod._HANDOFF),
        ("_REPROMPT",         lead_mod._REPROMPT),
        ("_ERROR_FALLBACK",   lead_mod._ERROR_FALLBACK),
        ("_ACK_BUSINESS_NAME",lead_mod._ACK_BUSINESS_NAME),
    ]

    violations = []
    for name, d in template_dicts:
        for lang, text in d.items():
            if _has_arabic_script(text):
                violations.append(f"{name}[{lang!r}]: {text!r}")

    assert not violations, (
        "Arabic-script characters found in templates:\n" + "\n".join(violations)
    )


def test_no_arabic_script_in_signal_lists():
    """_GENERIC_INFO_SIGNALS must not contain Arabic-script strings."""
    from app.lead import _GENERIC_INFO_SIGNALS
    for sig in _GENERIC_INFO_SIGNALS:
        assert not _has_arabic_script(sig), (
            f"_GENERIC_INFO_SIGNALS contains Arabic-script: {sig!r}"
        )
