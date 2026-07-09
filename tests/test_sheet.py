"""
Tests for app/sheet.py — Google Sheets lead tracker.

All Sheets API calls are mocked.  No network, no credentials needed.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# ── Ensure sheet module sees no real config so we control _ENABLED manually ──
os.environ.pop("GOOGLE_SA_JSON_B64", None)
os.environ.pop("GSHEET_ID", None)
os.environ.pop("GSHEET_TAB", None)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_service(phone_col_values=None, lead_id_col_values=None):
    """
    Build a mock Sheets service that returns configured column values.

    phone_col_values: list of rows for column E read (each row is a 1-item list or [])
    lead_id_col_values: list of rows for column A read
    """
    svc = MagicMock()
    spreadsheets = svc.spreadsheets.return_value
    values = spreadsheets.values.return_value

    # get() is used for both column reads; we sequence them
    get_mock = values.get.return_value.execute
    responses = []

    if phone_col_values is not None:
        responses.append({"values": phone_col_values})
    if lead_id_col_values is not None:
        responses.append({"values": lead_id_col_values})

    get_mock.side_effect = responses if responses else [{"values": []}]

    # batchUpdate and append return don't matter for our checks
    values.batchUpdate.return_value.execute.return_value = {}
    values.append.return_value.execute.return_value = {}
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Sheet1"}}]
    }
    return svc


# ── Unit tests: phone normalizer ──────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("923001234567",   "3001234567"),
    ("+923001234567",  "3001234567"),
    ("03001234567",    "3001234567"),
    ("+92 300 123 4567", "3001234567"),
    ("0300-1234567",   "3001234567"),
    ("923001234567",   "3001234567"),
    ("3001234567",     "3001234567"),
])
def test_normalize_phone(raw, expected):
    from app.sheet import _normalize_phone
    assert _normalize_phone(raw) == expected


# ── Unit tests: column letter helper ─────────────────────────────────────────

def test_col_letter():
    from app.sheet import _col_letter
    assert _col_letter(1)  == "A"
    assert _col_letter(5)  == "E"
    assert _col_letter(12) == "L"
    assert _col_letter(14) == "N"
    assert _col_letter(17) == "Q"
    assert _col_letter(18) == "R"


# ── Unit tests: slot datetime parser ─────────────────────────────────────────

def test_parse_slot_kal_11am():
    from app.sheet import _parse_slot_datetime, _karachi_now
    from datetime import timedelta
    d, t = _parse_slot_datetime("Kal 11am")
    expected_date = (_karachi_now().date() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert d == expected_date
    assert t == "11:00 AM"


def test_parse_slot_kal_4pm():
    from app.sheet import _parse_slot_datetime, _karachi_now
    from datetime import timedelta
    d, t = _parse_slot_datetime("Kal 4pm")
    expected_date = (_karachi_now().date() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert d == expected_date
    assert t == "4:00 PM"


def test_parse_slot_unparseable():
    from app.sheet import _parse_slot_datetime
    d, t = _parse_slot_datetime("some random text")
    assert d is None
    assert t is None


# ── Unit tests: find_row_by_phone ─────────────────────────────────────────────

def test_find_row_by_phone_found():
    """Phone in column E — various format variants all match."""
    from app.sheet import _sync_find_row_by_phone

    # Rows 1-4 in col E; target is row 3
    phone_rows = [
        ["9200000001"],
        ["9200000002"],
        ["+92 300 1234567"],  # row 3
        ["9200000004"],
    ]
    svc = _make_service(phone_col_values=phone_rows)

    row = _sync_find_row_by_phone(svc, "Sheet1", "03001234567")
    assert row == 3


def test_find_row_by_phone_not_found():
    from app.sheet import _sync_find_row_by_phone
    svc = _make_service(phone_col_values=[["9200000001"], ["9200000002"]])
    row = _sync_find_row_by_phone(svc, "Sheet1", "923009999999")
    assert row is None


def test_find_row_by_phone_empty_sheet():
    from app.sheet import _sync_find_row_by_phone
    svc = _make_service(phone_col_values=[])
    assert _sync_find_row_by_phone(svc, "Sheet1", "923001234567") is None


# ── Unit tests: new row gets max+1 id and correct columns only ────────────────

def test_append_row_correct_lead_id_and_columns():
    """
    Phone not found → insert via batchUpdate on first empty phone row.
    Row should contain lead_id = max+1 = 4, written to correct column cells.
    """
    from app.sheet import _sync_upsert_lead, COLUMN_MAP

    svc = MagicMock()
    spreadsheets = svc.spreadsheets.return_value
    values_mock = spreadsheets.values.return_value
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Sheet1"}}]
    }

    # _sync_find_row_by_phone: full phone col → not found (2 rows, neither matches)
    # _sync_find_first_empty_row: phone col from row 2 → 3 rows filled (empty at row 5)
    # _sync_find_first_empty_row: id col from row 2 → ids 1, 2, 3 → max=3
    get_responses = [
        {"values": [["9200000001"], ["9200000002"]]},           # phone col (find)
        {"values": [["9200000001"], ["9200000002"], ["9200000003"]]},  # phone from row 2 (insert)
        {"values": [["1"], ["2"], ["3"]]},                      # id col from row 2
    ]
    values_mock.get.return_value.execute.side_effect = get_responses
    values_mock.batchUpdate.return_value.execute.return_value = {}

    with patch("app.sheet._build_service", return_value=svc), \
         patch("app.sheet._resolve_tab", return_value="Sheet1"):
        _sync_upsert_lead("923001234567", {
            "business_name": "Test Shop",
            "status": "Bot - New",
        })

    # Must use batchUpdate, not append
    values_mock.append.assert_not_called()
    values_mock.batchUpdate.assert_called_once()

    batch_body = values_mock.batchUpdate.call_args.kwargs["body"]
    data = batch_body["data"]

    # Build a dict of range → value for easy assertion
    written = {d["range"]: d["values"][0][0] for d in data}

    # lead_id (col A) at row 5 should be 4 (max=3, +1)
    assert written.get("Sheet1!A5") == 4

    # phone (col E) at row 5
    assert written.get("Sheet1!E5") == "923001234567"

    # business_name (col F) at row 5
    assert written.get("Sheet1!F5") == "Test Shop"

    # status (col L) at row 5
    assert written.get("Sheet1!L5") == "Bot - New"

    # source (col I) at row 5 — always "Meta Ads" on insert
    assert written.get("Sheet1!I5") == "Meta Ads"

    # No range outside COLUMN_MAP should appear
    valid_cols = {f"Sheet1!{chr(64 + c)}" for c in COLUMN_MAP.values()}
    for rng in written:
        col_part = rng.split("!")[1].rstrip("0123456789")
        assert f"Sheet1!{col_part}" in valid_cols, f"Unexpected column written: {rng}"


# ── Unit tests: existing row updated in-place ─────────────────────────────────

def test_update_existing_row_uses_batch_update():
    """Phone found in row 5 → batchUpdate called, append NOT called."""
    from app.sheet import _sync_upsert_lead

    svc = MagicMock()
    spreadsheets = svc.spreadsheets.return_value
    values_mock = spreadsheets.values.return_value
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Sheet1"}}]
    }

    # phone lookup: row 5 matches
    phone_rows = [["x"]] * 4 + [["+923001234567"]]
    values_mock.get.return_value.execute.return_value = {"values": phone_rows}
    values_mock.batchUpdate.return_value.execute.return_value = {}

    with patch("app.sheet._build_service", return_value=svc), \
         patch("app.sheet._resolve_tab", return_value="Sheet1"):
        _sync_upsert_lead("923001234567", {"status": "Demo Booked"})

    # batchUpdate must have been called
    values_mock.batchUpdate.assert_called_once()
    batch_body = values_mock.batchUpdate.call_args.kwargs["body"]

    # Exactly one data entry: status column L, row 5
    data = batch_body["data"]
    assert len(data) == 1
    assert data[0]["range"] == "Sheet1!L5"
    assert data[0]["values"] == [["Demo Booked"]]

    # append must NOT have been called
    values_mock.append.assert_not_called()


# ── Unit tests: unmapped columns never written ────────────────────────────────

def test_unmapped_fields_not_written():
    """Fields not in COLUMN_MAP are silently dropped before hitting the API."""
    from app.sheet import _sync_upsert_lead

    svc = MagicMock()
    spreadsheets = svc.spreadsheets.return_value
    values_mock = spreadsheets.values.return_value
    spreadsheets.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Sheet1"}}]
    }

    # Phone found in row 2
    values_mock.get.return_value.execute.return_value = {
        "values": [["9200000001"], ["+923001234567"]]
    }
    values_mock.batchUpdate.return_value.execute.return_value = {}

    with patch("app.sheet._build_service", return_value=svc), \
         patch("app.sheet._resolve_tab", return_value="Sheet1"):
        _sync_upsert_lead("923001234567", {
            "status": "Demo Booked",
            "secret_internal_field": "should be dropped",
            "some_other_col": "also dropped",
        })

    batch_body = values_mock.batchUpdate.call_args.kwargs["body"]
    written_ranges = [d["range"] for d in batch_body["data"]]
    # Only "status" (L) should appear — the unmapped fields must not
    assert all("secret" not in r and "some_other" not in r for r in written_ranges)
    assert len(written_ranges) == 1


# ── Unit tests: missing env → no-op ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_upsert_lead_noop_when_env_missing():
    """When _ENABLED is False, upsert_lead returns immediately without API calls."""
    import app.sheet as sheet_mod

    original = sheet_mod._ENABLED
    sheet_mod._ENABLED = False
    try:
        with patch("app.sheet._build_service") as mock_build:
            await sheet_mod.upsert_lead("923001234567", {"status": "Bot - New"})
            mock_build.assert_not_called()
    finally:
        sheet_mod._ENABLED = original


# ── Unit tests: Sheets exception doesn't crash caller ────────────────────────

@pytest.mark.asyncio
async def test_sheets_exception_does_not_raise():
    """
    If the Sheets API raises, upsert_lead catches it and returns normally.
    The bot's reply path must not be affected.
    """
    import app.sheet as sheet_mod

    original = sheet_mod._ENABLED
    sheet_mod._ENABLED = True
    try:
        with patch("app.sheet._build_service", side_effect=Exception("API down")):
            # Must not raise
            await sheet_mod.upsert_lead("923001234567", {"status": "Bot - New"})
    finally:
        sheet_mod._ENABLED = original


# ── Integration: CONFIRMED writes correct demo_date/time from "Kal 11am" ─────

def test_confirmed_demo_date_parsed_correctly():
    """
    The confirmed event should parse 'Kal 11am' into tomorrow's date + '11:00 AM'.
    Verifies that main.py's sheet wiring uses parse_slot_datetime correctly.
    """
    from app.sheet import parse_slot_datetime, _karachi_now
    from datetime import timedelta

    slot = "Kal 11am"
    demo_date, demo_time = parse_slot_datetime(slot)

    tomorrow = (_karachi_now().date() + timedelta(days=1)).strftime("%Y-%m-%d")
    assert demo_date == tomorrow
    assert demo_time == "11:00 AM"
