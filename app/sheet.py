"""
Google Sheets lead tracker — polite guest writer.

The sheet is human-managed.  This module ONLY writes columns that are
explicitly listed in COLUMN_MAP.  It never touches any other column.

Missing config (GOOGLE_SA_JSON_B64 / GSHEET_ID) → all functions are no-ops.
Sheets errors → logged at ERROR, never raised to the caller.
All I/O runs in a thread via asyncio.to_thread with a 10 s timeout.

Append strategy: instead of values.append() (which lands below formula rows),
we read column B (phone) from row 2 down and write to the first empty row via
an explicit batchUpdate.  A module-level asyncio.Lock serialises concurrent
writes so two activations arriving simultaneously can't pick the same row.

Usage (fire-and-forget from async code):
    asyncio.create_task(upsert_lead(phone, fields))
"""

import asyncio
import base64
import json
import logging
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

log = logging.getLogger("orderbot.sheet")

# ── Status constants — edit here to match sheet dropdown values ───────────────
STATUS_NEW            = "New"
STATUS_IN_PROGRESS    = "Bot - In Progress"
STATUS_DEMO_BOOKED    = "Demo Scheduled"
STATUS_NOT_RESPONDING = "Not Responding"

# ── Column map — A=1, B=2, … edit to match your sheet layout ─────────────────
# Values are 1-based column indices.
COLUMN_MAP: dict[str, int] = {
    "lead_id":        1,   # A
    "date":           2,   # B
    "time":           3,   # C
    "name":           4,   # D
    "phone":          5,   # E
    "business_name":  6,   # F
    "business_type":  7,   # G
    "city":           8,   # H
    "source":         9,   # I
    "interest":       10,  # J
    "current_system": 11,  # K
    "status":         12,  # L
    # M intentionally skipped (column 13)
    "notes":          14,  # N
    "next_followup":  15,  # O
    # P intentionally skipped (column 16)
    "demo_date":      17,  # Q
    "demo_time":      18,  # R
}

_COL_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

TZ_KHI = ZoneInfo("Asia/Karachi")

# ── Config ────────────────────────────────────────────────────────────────────
_SA_JSON_B64 = os.environ.get("GOOGLE_SA_JSON_B64", "")
_GSHEET_ID   = os.environ.get("GSHEET_ID", "")
_GSHEET_TAB  = os.environ.get("GSHEET_TAB", "")   # empty → first tab

_ENABLED = bool(_SA_JSON_B64 and _GSHEET_ID)

# Serialises concurrent find+write operations to prevent two tasks picking
# the same empty row when two leads activate at the same moment.
_write_lock: asyncio.Lock | None = None

if not _ENABLED:
    log.warning(
        "sheet: GOOGLE_SA_JSON_B64 or GSHEET_ID not set — "
        "Google Sheets integration disabled"
    )


def _get_write_lock() -> asyncio.Lock:
    """Lazily create the write lock inside the running event loop."""
    global _write_lock
    if _write_lock is None:
        _write_lock = asyncio.Lock()
    return _write_lock


# ── Helpers ───────────────────────────────────────────────────────────────────

def _col_letter(col_idx: int) -> str:
    """Convert 1-based column index to letter(s). Supports up to ZZ (702)."""
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = _COL_LETTERS[remainder] + result
    return result


def _a1(tab: str, row: int, col_idx: int) -> str:
    """Return A1-notation range string, e.g. 'Sheet1!F7'."""
    return f"{tab}!{_col_letter(col_idx)}{row}"


def _normalize_phone(phone: str) -> str:
    """
    Normalize to last 10 digits for comparison.
    Strips +, spaces, leading 92, leading 0.
    '923001234567' → '3001234567'
    '03001234567'  → '3001234567'
    '+92 300 1234567' → '3001234567'
    """
    digits = re.sub(r"\D", "", phone)
    # Strip leading country code 92
    if digits.startswith("92") and len(digits) > 10:
        digits = digits[2:]
    # Strip leading 0
    if digits.startswith("0") and len(digits) > 10:
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits


def _build_service():
    """Build and return the Google Sheets service object (sync)."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_json = json.loads(base64.b64decode(_SA_JSON_B64).decode())
    creds = service_account.Credentials.from_service_account_info(
        sa_json,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _resolve_tab(service) -> str:
    """Return the sheet tab name to use. Falls back to first tab if not configured."""
    if _GSHEET_TAB:
        return _GSHEET_TAB
    meta = service.spreadsheets().get(spreadsheetId=_GSHEET_ID).execute()
    return meta["sheets"][0]["properties"]["title"]


def _karachi_now() -> datetime:
    return datetime.now(TZ_KHI)


def _parse_slot_datetime(slot: str) -> tuple[str | None, str | None]:
    """
    Parse a demo slot string like 'Kal 11am' or 'Kal 4pm' or 'Parso 3pm'
    into (date_str 'YYYY-MM-DD', time_str 'h:MM AM/PM').

    'Kal' = tomorrow Asia/Karachi.
    Falls back to (None, None) if unparseable.
    """
    slot_lower = slot.strip().lower()
    now = _karachi_now()

    # Determine date offset
    date_offset = None
    if slot_lower.startswith("kal"):
        date_offset = 1
    elif slot_lower.startswith("parso"):
        date_offset = 2
    elif slot_lower.startswith("aaj"):
        date_offset = 0

    # Extract time portion — look for digits followed by am/pm
    time_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", slot_lower)
    if not time_match:
        return None, None

    hour = int(time_match.group(1))
    minute = int(time_match.group(2) or 0)
    meridiem = time_match.group(3).upper()

    # Build a datetime for formatting
    if date_offset is not None:
        target_date = (now + timedelta(days=date_offset)).date()
    else:
        target_date = now.date()

    date_str = target_date.strftime("%Y-%m-%d")
    # Format time as "h:MM AM/PM"
    time_str = f"{hour}:{minute:02d} {meridiem}"
    return date_str, time_str


# ── Sync sheet operations (run inside asyncio.to_thread) ─────────────────────

def _sync_find_row_by_phone(service, tab: str, phone: str) -> int | None:
    """
    Read column E (phone), normalize, compare on last 10 digits.
    Returns 1-based row number or None if not found.
    """
    phone_col = COLUMN_MAP["phone"]
    col_letter = _col_letter(phone_col)
    range_str = f"{tab}!{col_letter}:{col_letter}"
    result = service.spreadsheets().values().get(
        spreadsheetId=_GSHEET_ID,
        range=range_str,
        valueRenderOption="FORMATTED_VALUE",
    ).execute()
    values = result.get("values", [])
    target = _normalize_phone(phone)
    for row_idx, row in enumerate(values, start=1):
        if row and _normalize_phone(str(row[0])) == target:
            return row_idx
    return None


def _sync_find_first_empty_row(service, tab: str) -> tuple[int, int]:
    """
    Read column E (phone) from row 2 downwards.
    Returns (first_empty_row, max_lead_id) where:
      - first_empty_row: 1-based row index of first row with empty phone cell
      - max_lead_id: max numeric value found in column A for rows that have a phone
    Skips row 1 (header).
    """
    # Read phone column to find first empty slot
    phone_col_letter = _col_letter(COLUMN_MAP["phone"])
    phone_range = f"{tab}!{phone_col_letter}2:{phone_col_letter}"
    phone_result = service.spreadsheets().values().get(
        spreadsheetId=_GSHEET_ID,
        range=phone_range,
        valueRenderOption="FORMATTED_VALUE",
    ).execute()
    phone_rows = phone_result.get("values", [])

    # Find first empty phone cell; row index starts at 2
    first_empty = None
    for offset, row in enumerate(phone_rows):
        has_value = bool(row and str(row[0]).strip())
        if not has_value:
            first_empty = 2 + offset
            break
    if first_empty is None:
        # All scanned rows are occupied; append after the last one
        first_empty = 2 + len(phone_rows)

    # Read lead_id column only for rows that have a phone (to compute max id)
    id_col_letter = _col_letter(COLUMN_MAP["lead_id"])
    id_range = f"{tab}!{id_col_letter}2:{id_col_letter}"
    id_result = service.spreadsheets().values().get(
        spreadsheetId=_GSHEET_ID,
        range=id_range,
        valueRenderOption="FORMATTED_VALUE",
    ).execute()
    id_rows = id_result.get("values", [])

    max_id = 0
    for offset, id_row in enumerate(id_rows):
        phone_row = phone_rows[offset] if offset < len(phone_rows) else []
        has_phone = bool(phone_row and str(phone_row[0]).strip())
        if has_phone and id_row:
            try:
                val = int(str(id_row[0]).strip())
                if val > max_id:
                    max_id = val
            except (ValueError, TypeError):
                pass

    return first_empty, max_id


def _sync_upsert_lead(phone: str, fields: dict) -> None:
    """
    Core sync implementation.  Called via asyncio.to_thread.
    """
    service = _build_service()
    tab = _resolve_tab(service)

    row = _sync_find_row_by_phone(service, tab, phone)

    if row is not None:
        # ── UPDATE: batch-update only the provided mapped columns ─────────
        _sync_update_row(service, tab, row, fields)
    else:
        # ── INSERT: write to first empty phone row ────────────────────────
        _sync_insert_row(service, tab, phone, fields)


def _sync_update_row(service, tab: str, row: int, fields: dict) -> None:
    """Batch-update specific cells in an existing row."""
    data = []
    for field, value in fields.items():
        col_idx = COLUMN_MAP.get(field)
        if col_idx is None:
            log.warning(f"sheet: ignored unmapped field '{field}'")
            continue
        data.append({
            "range": _a1(tab, row, col_idx),
            "values": [[value]],
        })
    if not data:
        return
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=_GSHEET_ID,
        body={"valueInputOption": "USER_ENTERED", "data": data},
    ).execute()
    log.info(f"sheet: updated row {row} — {list(fields.keys())}")


def _sync_insert_row(service, tab: str, phone: str, fields: dict) -> None:
    """
    Write a new lead to the first empty row in column E (phone).
    Uses an explicit batchUpdate on the target row (not append) so
    formula/validation rows below the data are never disturbed.
    """
    target_row, max_id = _sync_find_first_empty_row(service, tab)
    new_id = max_id + 1
    now = _karachi_now()

    # Build cell-level data list for batchUpdate
    data = []

    def _add(field: str, value) -> None:
        col_idx = COLUMN_MAP.get(field)
        if col_idx:
            data.append({
                "range": _a1(tab, target_row, col_idx),
                "values": [[value]],
            })

    # Fixed fields for every new row
    _add("lead_id", new_id)
    _add("date", now.strftime("%Y-%m-%d"))
    _add("time", now.strftime("%-I:%M %p"))
    _add("phone", phone)
    _add("source", "Meta Ads")

    # Caller-provided fields (only mapped ones)
    for field, value in fields.items():
        if field in COLUMN_MAP:
            _add(field, value)
        else:
            log.warning(f"sheet: ignored unmapped field '{field}' on insert")

    service.spreadsheets().values().batchUpdate(
        spreadsheetId=_GSHEET_ID,
        body={"valueInputOption": "USER_ENTERED", "data": data},
    ).execute()
    log.info(f"sheet: inserted new row {target_row} — lead_id={new_id}, phone={phone}")


# ── Public async API ──────────────────────────────────────────────────────────

async def find_row_by_phone(phone: str) -> int | None:
    """
    Async wrapper around _sync_find_row_by_phone.
    Returns 1-based row number or None.  Never raises.
    """
    if not _ENABLED:
        return None
    try:
        service = await asyncio.wait_for(
            asyncio.to_thread(_build_service), timeout=10
        )
        tab = await asyncio.wait_for(
            asyncio.to_thread(_resolve_tab, service), timeout=10
        )
        return await asyncio.wait_for(
            asyncio.to_thread(_sync_find_row_by_phone, service, tab, phone),
            timeout=10,
        )
    except Exception as exc:
        log.error(f"sheet: find_row_by_phone failed — {exc}")
        return None


async def upsert_lead(phone: str, fields: dict) -> None:
    """
    Async, fire-and-forget safe.  Runs sync I/O in a thread, 10 s timeout.
    Logs errors; never raises.  Only writes columns in COLUMN_MAP.
    The write lock serialises concurrent inserts to prevent row collisions.
    """
    if not _ENABLED:
        return
    # Filter to mapped fields only before even entering the thread
    safe_fields = {k: v for k, v in fields.items() if k in COLUMN_MAP}
    try:
        async with _get_write_lock():
            await asyncio.wait_for(
                asyncio.to_thread(_sync_upsert_lead, phone, safe_fields),
                timeout=10,
            )
    except asyncio.TimeoutError:
        log.error(f"sheet: upsert_lead timed out for {phone} — fields: {safe_fields}")
    except Exception as exc:
        log.error(f"sheet: upsert_lead failed for {phone} — {exc} — fields: {safe_fields}")


def parse_slot_datetime(slot: str) -> tuple[str | None, str | None]:
    """Public re-export of _parse_slot_datetime for use in wiring code."""
    return _parse_slot_datetime(slot)

