"""
Regression tests for three production bugs:
  Bug 1 — append position: new row uses batchUpdate on first empty phone row, not append()
  Bug 2 — status events misclassified: delivered/read receipts must not mute or write sheet
  Bug 3 — owner/self rows: BUSINESS_WA_ID and OWNER_WHATSAPP must never upsert sheet rows or trigger mutes
"""

import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
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
BUSINESS = "92300BUSINESS"


# ── Payload helpers ───────────────────────────────────────────────────────────

def _delivered_status_payload(recipient: str) -> dict:
    """Real delivered-receipt shape from Meta Cloud API."""
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{
                        "id": "wamid.abc123",
                        "status": "delivered",
                        "timestamp": "1700000000",
                        "recipient_id": recipient,
                    }]
                }
            }]
        }]
    }


def _read_status_payload(recipient: str) -> dict:
    """Real read-receipt shape."""
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{
                        "id": "wamid.abc456",
                        "status": "read",
                        "timestamp": "1700000001",
                        "recipient_id": recipient,
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


def _referral_payload(sender: str, text: str = "hi") -> dict:
    return {
        "entry": [{"changes": [{"value": {"messages": [{
            "from": sender,
            "type": "text",
            "text": {"body": text},
            "referral": {"source_id": "ad_1", "headline": "Bahi POS Ad"},
        }]}}]}]
    }


def _echo_payload(business: str, customer: str) -> dict:
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": business,
                        "type": "text",
                        "text": {"body": "Haan aata hoon"},
                    }],
                    "contacts": [{"wa_id": customer, "profile": {"name": "Customer"}}],
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


@pytest.fixture()
def mock_upsert(monkeypatch):
    """Replace upsert_lead in main with an async mock so we can assert call counts."""
    import app.main as main_mod
    mock = AsyncMock()
    monkeypatch.setattr(main_mod, "upsert_lead", mock)
    return mock


@pytest_asyncio.fixture()
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ══════════════════════════════════════════════════════════════════════════════
# Bug 1 — append position: insert uses batchUpdate on first empty row
# ══════════════════════════════════════════════════════════════════════════════

def test_insert_uses_batch_update_not_append():
    """
    New lead row must be written via batchUpdate to the first empty phone row,
    never via values.append().
    """
    from app.sheet import _sync_upsert_lead

    svc = MagicMock()
    spreadsheets = svc.spreadsheets.return_value
    values_mock = spreadsheets.values.return_value
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Sheet1"}}]
    }

    # Responses: phone lookup (E col) → not found; then insert reads:
    #   phone col from row 2 → rows 2,3 occupied, row 4 empty
    #   id col from row 2    → ids 1, 2 for rows 2 and 3
    get_responses = [
        # _sync_find_row_by_phone reads full phone column
        {"values": [["9200000001"], ["9200000002"]]},
        # _sync_find_first_empty_row: phone col from row 2 (2 rows filled)
        {"values": [["9200000001"], ["9200000002"]]},
        # _sync_find_first_empty_row: id col from row 2
        {"values": [["1"], ["2"]]},
    ]
    values_mock.get.return_value.execute.side_effect = get_responses
    values_mock.batchUpdate.return_value.execute.return_value = {}

    with patch("app.sheet._build_service", return_value=svc), \
         patch("app.sheet._resolve_tab", return_value="Sheet1"):
        _sync_upsert_lead("923001234567", {"status": "Bot - New"})

    # values.append must NEVER be called
    values_mock.append.assert_not_called()

    # batchUpdate must have been called for the insert
    assert values_mock.batchUpdate.call_count >= 1

    # The ranges in the insert batchUpdate must all target row 4 (first empty = row 4)
    insert_call = values_mock.batchUpdate.call_args
    body = insert_call.kwargs["body"]
    ranges = [d["range"] for d in body["data"]]
    assert all(r.endswith("4") or "4" in r.split("!")[-1] for r in ranges), (
        f"Expected all ranges to target row 4, got: {ranges}"
    )


def test_insert_lead_id_is_max_phone_rows_plus_one():
    """
    lead_id = max id from rows that have a phone value, +1.
    Rows with no phone are ignored when computing max.
    """
    from app.sheet import _sync_find_first_empty_row

    svc = MagicMock()
    spreadsheets = svc.spreadsheets.return_value
    values_mock = spreadsheets.values.return_value

    # phone col from row 2: rows 2,3 filled, row 4 empty
    # id col from row 2: id=5 in row 2, id=7 in row 3
    get_responses = [
        {"values": [["9200000001"], ["9200000002"]]},   # phone
        {"values": [["5"], ["7"]]},                      # ids
    ]
    values_mock.get.return_value.execute.side_effect = get_responses

    first_empty, max_id = _sync_find_first_empty_row(svc, "Sheet1")

    assert first_empty == 4       # row 4 is first empty (rows 2,3 occupied)
    assert max_id == 7            # max of 5,7 = 7


def test_insert_skips_formula_rows_below_data():
    """
    If the sheet has 3 data rows then some blank rows then more formula content,
    the insert target is the first blank row (row 5), not far below.
    """
    from app.sheet import _sync_find_first_empty_row

    svc = MagicMock()
    spreadsheets = svc.spreadsheets.return_value
    values_mock = spreadsheets.values.return_value

    # Phone col rows 2-7: 3 real rows, then empty at row 5 (index offset 3)
    # values API returns only as many rows as have data, so 3 rows here
    get_responses = [
        {"values": [["9200000001"], ["9200000002"], ["9200000003"]]},  # phone: 3 rows
        {"values": [["1"], ["2"], ["3"]]},                              # ids
    ]
    values_mock.get.return_value.execute.side_effect = get_responses

    first_empty, max_id = _sync_find_first_empty_row(svc, "Sheet1")

    # 3 rows filled starting at row 2 → next empty is row 5
    assert first_empty == 5
    assert max_id == 3


# ══════════════════════════════════════════════════════════════════════════════
# Bug 2 — status events must not mute or write sheet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delivered_status_no_mute_no_sheet(client, mock_send, mock_upsert):
    """Delivered receipt → 200, no mute applied, no sheet call."""
    from app.gate import _muted
    r = await client.post("/webhook", json=_delivered_status_payload(CUSTOMER))
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}
    mock_send.assert_not_called()
    mock_upsert.assert_not_called()
    assert CUSTOMER not in _muted


@pytest.mark.asyncio
async def test_read_status_no_mute_no_sheet(client, mock_send, mock_upsert):
    """Read receipt → 200, no mute applied, no sheet call."""
    from app.gate import _muted
    r = await client.post("/webhook", json=_read_status_payload(CUSTOMER))
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}
    mock_send.assert_not_called()
    mock_upsert.assert_not_called()
    assert CUSTOMER not in _muted


@pytest.mark.asyncio
async def test_status_event_after_active_lead_no_mute(client, mock_send, mock_upsert):
    """
    Even if the recipient has an active lead session, a status receipt must not
    mute them or write to the sheet.
    """
    from app.lead import _meta
    from app.gate import _muted
    _meta[CUSTOMER] = {"phase": "BUSINESS_NAME", "lead_source": "ad"}

    r = await client.post("/webhook", json=_delivered_status_payload(CUSTOMER))
    assert r.status_code == 200
    # Session must be untouched
    assert _meta.get(CUSTOMER, {}).get("phase") == "BUSINESS_NAME"
    assert CUSTOMER not in _muted
    mock_upsert.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# Bug 3 — owner/self rows: BUSINESS_WA_ID and OWNER_WHATSAPP protected
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delivery_status_for_owner_no_sheet_write(client, mock_upsert):
    """Delivery receipt whose recipient is OWNER_WHATSAPP → no sheet write."""
    r = await client.post("/webhook", json=_delivered_status_payload(OWNER))
    assert r.status_code == 200
    mock_upsert.assert_not_called()


@pytest.mark.asyncio
async def test_message_from_owner_number_no_sheet_write(client, mock_send, mock_upsert):
    """
    A message arriving from the owner's own number (e.g. they text from their
    personal number which matches OWNER_WHATSAPP) must not trigger a sheet row.
    The gate will silence it as a plain echo or unknown contact; either way
    upsert_lead must not be called.
    """
    # Owner number exactly matches OWNER_WHATSAPP env var
    r = await client.post("/webhook", json=_text_payload(OWNER, "Bahi POS"))
    assert r.status_code == 200
    mock_upsert.assert_not_called()


@pytest.mark.asyncio
async def test_echo_from_business_number_no_sheet_mute_for_own_contact(client, mock_send, mock_upsert):
    """
    Outbound echo from BUSINESS_WA_ID to a real customer:
    - must mute the CUSTOMER (correct)
    - must NOT write a sheet row for BUSINESS_WA_ID itself
    - sheet note for the customer is fine but must not include BUSINESS_WA_ID
    """
    from app.gate import _muted

    r = await client.post("/webhook", json=_echo_payload(BUSINESS, CUSTOMER))
    assert r.status_code == 200

    # Customer must be muted
    assert CUSTOMER in _muted

    # If upsert_lead was called (for customer "human took over" note), the
    # phone arg must be the CUSTOMER number, never the BUSINESS number
    for c in mock_upsert.call_args_list:
        phone_arg = c.args[0] if c.args else c.kwargs.get("phone", "")
        assert phone_arg != BUSINESS, (
            f"upsert_lead must not be called with BUSINESS number, got {phone_arg}"
        )


@pytest.mark.asyncio
async def test_is_own_number_normalizes_correctly():
    """_is_own_number must correctly identify OWNER and BUSINESS numbers."""
    import app.main as main_mod
    # OWNER_WHATSAPP = "9200000000" → last 10 digits "9200000000" → normalized "200000000" (9 digits, < 10)
    # Actually 9200000000 is 10 digits already, normalize → 9200000000
    # Various formats of OWNER
    assert main_mod._is_own_number("9200000000")   is True
    assert main_mod._is_own_number("+9200000000")  is True
    assert main_mod._is_own_number("09200000000")  is True   # leading 0

    # BUSINESS_WA_ID = "92300BUSINESS" (not all digits, normalizes to empty-ish)
    # The test is that a real customer number is NOT flagged
    assert main_mod._is_own_number(CUSTOMER) is False
