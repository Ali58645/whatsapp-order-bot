"""
WhatsApp Cloud API interactive message builders and inbound reply parser.

Outbound:
  build_buttons(body_text, buttons)  → payload for type "button"  (max 3)
  build_list(body_text, button_label, rows)  → payload for type "list"  (max 10 rows)

Both return the full top-level message payload dict ready to POST to
/<PHONE_NUMBER_ID>/messages — same shape as the text payload in send_whatsapp_message.

Inbound (webhook):
  parse_interactive_reply(message)  → (reply_id, reply_title) or (None, None)

Cloud API interactive button outbound shape:
  {
    "messaging_product": "whatsapp",
    "to": "<number>",
    "type": "interactive",
    "interactive": {
      "type": "button",
      "body": {"text": "..."},
      "action": {
        "buttons": [
          {"type": "reply", "reply": {"id": "...", "title": "..."}}
        ]
      }
    }
  }

Cloud API interactive list outbound shape:
  {
    "messaging_product": "whatsapp",
    "to": "<number>",
    "type": "interactive",
    "interactive": {
      "type": "list",
      "body": {"text": "..."},
      "action": {
        "button": "<label>",          # the button that opens the list
        "sections": [
          {
            "rows": [
              {"id": "...", "title": "...", "description": "..."}
            ]
          }
        ]
      }
    }
  }

Inbound button_reply (webhook message.interactive):
  {"type": "button_reply", "button_reply": {"id": "...", "title": "..."}}

Inbound list_reply (webhook message.interactive):
  {"type": "list_reply", "list_reply": {"id": "...", "title": "..."}}
"""

import logging
from typing import Optional

log = logging.getLogger("orderbot.interactive")

BUTTON_TITLE_MAX = 20
BUTTONS_MAX = 3
ROWS_MAX = 10


# ── Validation helpers ────────────────────────────────────────────────────────

def _trim(s: str, max_len: int) -> str:
    """Silently truncate to max_len and warn if needed."""
    if len(s) > max_len:
        log.warning(f"interactive: title '{s}' truncated to {max_len} chars")
        return s[:max_len]
    return s


# ── Outbound builders ─────────────────────────────────────────────────────────

def build_buttons(
    to: str,
    body_text: str,
    buttons: list[tuple[str, str]],      # [(id, title), ...]  max 3
) -> dict:
    """
    Build a Cloud API interactive *button* message payload.

    buttons: list of (id, title) tuples, 1–3 items.
    Title is automatically truncated to 20 characters.

    Returns the full message payload dict (not just the interactive object).
    """
    if not buttons:
        raise ValueError("build_buttons: need at least 1 button")
    if len(buttons) > BUTTONS_MAX:
        raise ValueError(f"build_buttons: max {BUTTONS_MAX} buttons, got {len(buttons)}")

    btn_list = [
        {
            "type": "reply",
            "reply": {
                "id": btn_id,
                "title": _trim(btn_title, BUTTON_TITLE_MAX),
            },
        }
        for btn_id, btn_title in buttons
    ]

    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {"buttons": btn_list},
        },
    }


def build_list(
    to: str,
    body_text: str,
    button_label: str,
    rows: list[tuple[str, str, str]],    # [(id, title, description), ...]  max 10
) -> dict:
    """
    Build a Cloud API interactive *list* message payload.

    rows: list of (id, title, description) tuples, 1–10 items.
    All rows go into a single unnamed section.

    Returns the full message payload dict.
    """
    if not rows:
        raise ValueError("build_list: need at least 1 row")
    if len(rows) > ROWS_MAX:
        raise ValueError(f"build_list: max {ROWS_MAX} rows, got {len(rows)}")

    row_list = [
        {"id": row_id, "title": row_title, "description": row_desc}
        for row_id, row_title, row_desc in rows
    ]

    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_label,
                "sections": [{"rows": row_list}],
            },
        },
    }


# ── Inbound reply parser ──────────────────────────────────────────────────────

def parse_interactive_reply(message: dict) -> tuple[Optional[str], Optional[str]]:
    """
    Extract (reply_id, reply_title) from an inbound interactive message.

    Handles both button_reply and list_reply variants.
    Returns (None, None) on any malformed payload — never raises.
    """
    try:
        interactive = message.get("interactive", {})
        reply_type = interactive.get("type")

        if reply_type == "button_reply":
            br = interactive["button_reply"]
            return br["id"], br.get("title", "")

        if reply_type == "list_reply":
            lr = interactive["list_reply"]
            return lr["id"], lr.get("title", "")

    except (KeyError, TypeError, AttributeError) as exc:
        log.warning(f"interactive: malformed payload — {exc}")

    return None, None
