"""
Bahi POS lead qualification flow.

State machine phases (stored in session metadata):
  GREETING -> BUSINESS_NAME -> BUSINESS_TYPE -> LOCATIONS ->
  CURRENT_SYSTEM -> SCHEDULING -> CONFIRMED | STALLED

Session structure (stored alongside Claude history in sessions._sessions):
  The session list holds conversation history (role/content dicts).
  Lead metadata lives in sessions._meta[sender] — a plain dict.

Lead card is forwarded to OWNER_WHATSAPP on CONFIRMED or STALLED
(partial lead is still a lead).

Interactive phases:
  BUSINESS_TYPE  → list   (6 business-type options)
  LOCATIONS      → buttons (1 / 2-5 / 5+)
  CURRENT_SYSTEM → buttons (manual / POS software / nothing)
  SCHEDULING     → buttons (slot 1 / slot 2 / other time)
  slot_other tap → free-text follow-up stored as demo_slot

Entry intent (first message only):
  GENERIC_INFO  → ad-context greeting + value line + business name question
  PRICE_FIRST   → pricing deflection + business name question
  DEMO_FIRST    → skip straight to SCHEDULING (buttons sent immediately)
  OTHER         → same as GENERIC_INFO
"""

import asyncio
import json
import logging
import os
from typing import Optional

log = logging.getLogger("orderbot.lead")

# ── Config ───────────────────────────────────────────────────────────────────
DEMO_SLOT_1: str = os.environ.get("DEMO_SLOT_1", "Kal 11am")
DEMO_SLOT_2: str = os.environ.get("DEMO_SLOT_2", "Kal 4pm")

# ── Phases ───────────────────────────────────────────────────────────────────
PHASES = [
    "GREETING",
    "BUSINESS_NAME",
    "BUSINESS_TYPE",
    "LOCATIONS",
    "CURRENT_SYSTEM",
    "SCHEDULING",
    "CONFIRMED",
]
STALLED = "STALLED"

# ── Retry config (reuse same pattern as orders.py) ───────────────────────────
_RETRY_DELAYS = (1, 2, 4)

# ── In-memory lead metadata store  {sender: dict} ────────────────────────────
# Kept separate from conversation history so get_session stays clean.
_meta: dict = {}


def get_lead_meta(sender: str) -> dict:
    return _meta.setdefault(sender, {"phase": "GREETING"})


def clear_lead_meta(sender: str) -> None:
    _meta.pop(sender, None)


def has_active_lead(sender: str) -> bool:
    """True if sender has a lead session that is still in progress."""
    m = _meta.get(sender)
    if not m:
        return False
    return m.get("phase") not in (None, "CONFIRMED", "STALLED")


# ── Entry intent detection ────────────────────────────────────────────────────
# Deterministic keyword pre-check — runs BEFORE any LLM call on the first
# message from a newly-activated lead.

_GENERIC_INFO_SIGNALS = (
    "more information", "info chahiye", "info", "details", "tell me more",
    "interested", "hi", "hello", "aoa", "salam", "assalam", "hey",
    "haan", "okay", "ok", "ha", "جی", "kya hai", "batao", "bata",
    "more info", "janana hai", "janna hai",
)

_PRICE_FIRST_SIGNALS = (
    "price", "cost", "kitne ki", "kitna", "rate", "fee", "charges",
    "paisa", "paisay", "payment", "subscription", "plan", "package",
    "mehnga", "sasta", "affordable", "budget", "pricing", "charge karte",
    "kitne mein", "kya cost",
)

_DEMO_FIRST_SIGNALS = (
    "demo", "meeting", "dikhao", "dikhayen", "dekhhna", "dekhna",
    "show me", "schedule", "book", "appointment", "milna", "milte",
    "call karo", "call karein", "live", "walkthrough",
)

# Intent literals
INTENT_GENERIC_INFO = "GENERIC_INFO"
INTENT_PRICE_FIRST  = "PRICE_FIRST"
INTENT_DEMO_FIRST   = "DEMO_FIRST"
INTENT_OTHER        = "OTHER"


def classify_entry_intent(text: str) -> str:
    """
    Classify the first message from a newly-activated lead.

    Evaluated in priority order: DEMO_FIRST > PRICE_FIRST > GENERIC_INFO > OTHER.
    Case-insensitive substring matching; handles Roman Urdu + English.
    Returns one of the INTENT_* constants.
    """
    if not text:
        return INTENT_GENERIC_INFO

    lower = text.lower().strip()

    # Priority 1: demo/meeting intent — most actionable, handle first
    if any(sig in lower for sig in _DEMO_FIRST_SIGNALS):
        return INTENT_DEMO_FIRST

    # Priority 2: price question — deflect immediately
    if any(sig in lower for sig in _PRICE_FIRST_SIGNALS):
        return INTENT_PRICE_FIRST

    # Priority 3: generic/low-intent opener — exact match or starts-with for short tokens
    # Use word-boundary logic: the signal must be a standalone word or the full message
    words = set(lower.split())
    if any(sig in words or lower == sig for sig in _GENERIC_INFO_SIGNALS):
        return INTENT_GENERIC_INFO

    # Priority 3b: very short messages (≤ 4 chars) are almost always greetings
    if len(lower) <= 4:
        return INTENT_GENERIC_INFO

    return INTENT_OTHER


# Standard greeting components (used by build_entry_response and non-text fallback)
_GREETING_THANKS  = "Assalam o Alaikum! Bahi POS mein interest ka shukriya 🙏"
_GREETING_VALUE   = ("Bahi POS aap ke business ka har hisaab ek jagah manage karta hai "
                     "— sales, stock, khata, FBR invoicing.")
_GREETING_NAME_Q  = "Aap ke business/shop ka naam kya hai?"

GREETING_TEXT = f"{_GREETING_THANKS}\n{_GREETING_VALUE}\n{_GREETING_NAME_Q}"

_PRICE_DEFLECT = (
    "Pricing aap ke business size aur requirements par depend karti hai "
    "— isi liye 15-minute demo mein aap ko exact quote milta hai. "
    "Taake main aap ko sahi guide kar sakoon, aap ke business ka naam kya hai?"
)

_DEMO_FIRST_TEXT = (
    f"{_GREETING_THANKS}\n"
    "Bilkul — demo ke liye aap ko direct slot choose karein:"
)

_MEDIA_FIRST_TEXT = (
    f"{_GREETING_THANKS}\n"
    f"{_GREETING_VALUE}\n"
    f"{_GREETING_NAME_Q}\n"
    "(Text mein reply karein please 🙏)"
)


def build_entry_response(intent: str) -> tuple[str, str]:
    """
    Return (reply_text, next_phase) for a first-message entry intent.

    For DEMO_FIRST, reply_text is a short ack; the caller must follow up
    with the SCHEDULING interactive widget immediately after.
    """
    if intent == INTENT_PRICE_FIRST:
        return _PRICE_DEFLECT, "BUSINESS_NAME"
    if intent == INTENT_DEMO_FIRST:
        return _DEMO_FIRST_TEXT, "SCHEDULING"
    # GENERIC_INFO, OTHER, anything else
    return GREETING_TEXT, "BUSINESS_NAME"


# ── System prompt builder ─────────────────────────────────────────────────────

_FACTS = """
FACTS (the ONLY claims you may make about Bahi POS — never invent beyond these):

PRODUCT: Bahi POS — "Har hisaab, ek jagah." Complete POS aur shop management software Pakistani businesses ke liye. Desktop app (Windows/macOS), offline-first — internet ke baghair bhi chalta hai, sara data shop ke apne computer par.

KEY_FEATURES (mention only what's relevant to the lead's business type):
- Fast checkout POS: walk-in aur udhaar (credit) sales, cash/bank/EasyPaisa/JazzCash payments, discounts, partial payments
- Customer khata: complete ledger, printable statements, receivables tracking — kis ne kitna dena hai, ek click par
- Inventory: stock tracking, low-stock alerts, variants (size/color), barcode, bulk import
- FBR e-invoicing: built-in integration, POS se direct e-invoice submission (sandbox + production ready)
- Reports: sales, profit, receivables/payables, inventory
- Invoices: A4 aur thermal (80mm) print, PDF, WhatsApp share
- Vendors, purchases, returns, manufacturing (BOM) bhi covered
- Backup: full data backup/restore, JWT-secured admin login

PRICING_RULE: NEVER state any price, package, number, ya range — even if asked repeatedly. Pricing business size aur needs par depend karti hai. Standard response: "Pricing aap ke business size aur requirements par depend karti hai — isi liye 15-minute demo mein aap ko exact quote milta hai." Then continue the flow. If lead insists a second time, acknowledge politely and offer the demo slot again — do not negotiate, do not hint.

FBR_CLAIM (exact scope — do not exceed): "Bahi POS mein FBR e-invoicing ki built-in integration hai — POS se direct e-invoice submit hota hai." You may add that FBR digital invoicing requirements Pakistan mein aa rahi hain aur Bahi POS is ke liye ready hai. NEVER claim the lead's specific business is legally required to comply, never give legal/tax advice, never promise automatic compliance — agar detailed FBR sawal aaye, say the demo will cover their exact FBR setup.
"""

_SCRIPT = f"""
CONVERSATION SCRIPT (follow phases in order):

GREETING phase:
  "Assalam o Alaikum! Bahi POS mein interest ka shukriya 🙏 Aap ke business/shop ka naam kya hai?"

BUSINESS_TYPE phase (after getting name):
  "[Name] kis type ka business hai — retail store, restaurant, pharmacy, ya kuch aur?"

LOCATIONS phase:
  "Kitni branches/locations hain?"

CURRENT_SYSTEM phase:
  "Abhi billing kaise karte hain — manual register ya koi POS software?"

SCHEDULING phase:
  Weave in FBR hook naturally, then:
  "FBR ke naye digital invoicing rules ke liye compliant invoicing zaroori ho rahi hai — Bahi POS mein built-in hai ✅
  Demo ke liye {DEMO_SLOT_1} ya {DEMO_SLOT_2} — kaunsa time theek rahega?"

CONFIRMED phase (after slot selected):
  Repeat day/time back clearly. Tell them the team will contact on this number.
  Then output on its own line: LEAD_CONFIRMED

ESCAPE HATCHES (handle via intent, never break the phase flow):
- Price question at any phase:
  "Pricing business size par depend karti hai, demo mein exact quote milta hai 👍" + repeat current phase question.
- Hot-lead signal ("demo chahiye", "meeting", "schedule", "book") at any phase:
  Jump directly to SCHEDULING phase question.
- "sirf info" or "just info":
  Give 3-line Bahi POS summary, then re-offer demo once.
- Gibberish / off-topic:
  First time: one polite redirect back to the question.
  Second time in a row: stay silent and output: LEAD_STALLED
"""

SYSTEM_PROMPT_LEAD = f"""You are a friendly WhatsApp sales assistant for Bahi POS, a Pakistani POS software company.

Rules:
- Mirror the lead's language (Roman Urdu + English mix by default; pure English if they write English).
- ONE question per message. Keep messages WhatsApp-short (max 3 lines).
- Never invent pricing, features, or FBR claims beyond the FACTS block below.
- When you output LEAD_CONFIRMED or LEAD_STALLED, put it on its own final line with nothing after it.

{_FACTS}
{_SCRIPT}
"""


# ── LEAD_CONFIRMED / LEAD_STALLED marker detection ───────────────────────────

def extract_lead_marker(reply: str):
    """
    Returns ('CONFIRMED'|'STALLED'|None, cleaned_reply).
    Strips the marker line from the reply sent to the customer.
    """
    for marker, state in (("LEAD_CONFIRMED", "CONFIRMED"), ("LEAD_STALLED", "STALLED")):
        if marker in reply:
            idx = reply.index(marker)
            clean = reply[:idx].strip()
            return state, clean
    return None, reply


# ── Lead card forwarding ──────────────────────────────────────────────────────

async def forward_lead_card(
    sender: str,
    meta: dict,
    owner_number: str,
    send_fn,
) -> None:
    """
    Send a lead card to the owner. Retries 3× with exponential backoff.
    On total failure logs CRITICAL with full meta payload.
    Reuses the same retry pattern as orders.forward_order_to_owner.
    """
    if not owner_number:
        log.warning("OWNER_WHATSAPP not set — lead card not forwarded")
        return

    phase = meta.get("phase", "?")
    slot = meta.get("demo_slot") or f"not booked — stalled at {phase}"
    source = meta.get("lead_source", "unknown")
    referral_headline = meta.get("referral_headline", "")

    card_lines = [
        "🔔 *NEW LEAD — Bahi POS*",
        "",
        f"Business: {meta.get('business_name', '?')} ({meta.get('business_type', '?')})",
        f"Locations: {meta.get('locations', '?')}",
        f"Current system: {meta.get('current_system', '?')}",
        f"Demo: {slot}",
        f"Source: {source}",
    ]
    if referral_headline:
        card_lines.append(f"Ad: {referral_headline}")
    card_lines.append(f"Number: wa.me/{sender}")
    card = "\n".join(card_lines)

    for attempt, delay in enumerate(_RETRY_DELAYS, start=1):
        sent = await send_fn(owner_number, card)
        if sent:
            log.info(f"Lead card sent to owner (attempt {attempt}) for {sender}")
            return
        if attempt < len(_RETRY_DELAYS):
            log.warning(f"Lead card send attempt {attempt} failed — retrying in {delay}s")
            await asyncio.sleep(delay)

    log.critical(
        f"UNDELIVERED LEAD CARD — all 3 attempts failed. "
        f"Sender: {sender}. Meta: {json.dumps(meta)}"
    )


# ── Phase metadata extraction from Claude reply ───────────────────────────────

def _advance_phase(meta: dict, reply_lower: str, user_text_lower: str) -> None:
    """
    Heuristically advance the phase based on what Claude just said or
    what the user said.  The LLM owns the conversation; we track phase
    as a side-channel for lead card completeness.
    """
    phase = meta.get("phase", "GREETING")

    # Hot-lead jump
    hot_signals = ("demo chahiye", "meeting", "schedule", "book karo", "book karna")
    if any(s in user_text_lower for s in hot_signals) and phase not in ("SCHEDULING", "CONFIRMED"):
        meta["phase"] = "SCHEDULING"
        return

    # Normal linear advance
    phase_order = {p: i for i, p in enumerate(PHASES)}
    current_idx = phase_order.get(phase, 0)

    # Detect phase transitions by keywords Claude used in its reply
    transitions = {
        "GREETING":       ("kis type", "business hai", "kya karte"),
        "BUSINESS_NAME":  ("branches", "locations", "kitni"),
        "BUSINESS_TYPE":  ("billing", "manual", "software", "kaise karte"),
        "LOCATIONS":      ("fbr", "digital invoicing", "demo ke liye", "11am", "4pm"),
        "CURRENT_SYSTEM": ("confirm", "team contact", "hum milenge", "slot"),
        "SCHEDULING":     ("lead_confirmed",),
    }
    next_phase_triggers = transitions.get(phase, ())
    if any(kw in reply_lower for kw in next_phase_triggers):
        next_idx = current_idx + 1
        if next_idx < len(PHASES):
            meta["phase"] = PHASES[next_idx]


def extract_meta_from_turn(meta: dict, user_text: str, reply: str) -> None:
    """
    Pull structured fields out of the conversation for the lead card.
    Best-effort: we capture what we can without asking Claude to output JSON.
    The fields are filled as the conversation progresses.
    """
    phase = meta.get("phase", "GREETING")
    user_lower = user_text.lower()
    reply_lower = reply.lower()

    # Capture user answers by current phase
    if phase == "BUSINESS_NAME" and user_text:
        meta.setdefault("business_name", user_text.strip())
    elif phase == "BUSINESS_TYPE" and user_text:
        meta.setdefault("business_type", user_text.strip())
    elif phase == "LOCATIONS" and user_text:
        meta.setdefault("locations", user_text.strip())
    elif phase == "CURRENT_SYSTEM" and user_text:
        meta.setdefault("current_system", user_text.strip())
    elif phase == "SCHEDULING" and user_text:
        # Capture whichever slot the user chose
        if DEMO_SLOT_1.lower() in user_lower or "11" in user_lower:
            meta["demo_slot"] = DEMO_SLOT_1
        elif DEMO_SLOT_2.lower() in user_lower or "4pm" in user_lower or "4 pm" in user_lower:
            meta["demo_slot"] = DEMO_SLOT_2
        else:
            meta["demo_slot"] = user_text.strip()

    _advance_phase(meta, reply_lower, user_lower)


# ── Interactive phase definitions ─────────────────────────────────────────────
# Each entry maps phase -> (type, question_text, options)
# type "buttons": list of (id, title)  — up to 3
# type "list":   list of (id, title, description) — up to 10

_BUSINESS_TYPE_ROWS = [
    ("retail",       "Retail Store",    "General retail / dukaan"),
    ("restaurant",   "Restaurant",      "Food & beverage"),
    ("pharmacy",     "Pharmacy",        "Medical store"),
    ("grocery",      "Grocery Store",   "Kiryana / superstore"),
    ("electronics",  "Electronics",     "Mobile / gadgets / home appliances"),
    ("other",        "Kuch aur",        "Doosra business type"),
]

# Human-readable labels for structured meta storage (id → display label)
_BUSINESS_TYPE_LABELS: dict[str, str] = {r[0]: r[1] for r in _BUSINESS_TYPE_ROWS}

_LOCATIONS_BUTTONS = [
    ("loc_1",    "1"),
    ("loc_2_5",  "2-5"),
    ("loc_5plus", "5+"),
]

_CURRENT_SYSTEM_BUTTONS = [
    ("sys_manual", "Manual register"),
    ("sys_pos",    "POS software"),
    ("sys_none",   "Kuch nahi"),
]

# Scheduling buttons built at call-time so DEMO_SLOT_1/2 are resolved after env load
def _scheduling_buttons() -> list[tuple[str, str]]:
    return [
        ("slot_1",     DEMO_SLOT_1[:20]),
        ("slot_2",     DEMO_SLOT_2[:20]),
        ("slot_other", "Koi aur time"),
    ]


# Id → human label for loc / system (used by apply_interactive_answer)
_LOC_LABELS: dict[str, str]  = {r[0]: r[1] for r in _LOCATIONS_BUTTONS}
_SYS_LABELS: dict[str, str]  = {r[0]: r[1] for r in _CURRENT_SYSTEM_BUTTONS}


def get_phase_interactive(phase: str, sender: str) -> Optional[dict]:
    """
    Return the interactive payload dict for *phase*, or None if this phase
    uses free-text (handled by Claude as normal).

    The returned dict is the full message payload (ready for the Graph API).
    Import build_buttons / build_list here to avoid a circular import at
    module level (interactive imports nothing from lead).
    """
    from app.interactive import build_buttons, build_list  # local import — no circular dep

    if phase == "BUSINESS_TYPE":
        return build_list(
            sender,
            "Aap ka business kaunsa type ka hai? Neeche se choose karein:",
            "Options dekhein",
            _BUSINESS_TYPE_ROWS,
        )

    if phase == "LOCATIONS":
        return build_buttons(
            sender,
            "Aap ki kitni branches/locations hain?",
            _LOCATIONS_BUTTONS,
        )

    if phase == "CURRENT_SYSTEM":
        return build_buttons(
            sender,
            "Abhi billing kaise karte hain?",
            _CURRENT_SYSTEM_BUTTONS,
        )

    if phase == "SCHEDULING":
        return build_buttons(
            sender,
            (
                "FBR ke naye digital invoicing rules ke liye compliant POS zaroori hai — "
                "Bahi POS mein built-in hai ✅\n\n"
                "Demo ke liye kaunsa time theek rahega?"
            ),
            _scheduling_buttons(),
        )

    return None  # GREETING, BUSINESS_NAME, CONFIRMED, STALLED → plain text / LLM


def apply_interactive_answer(
    meta: dict,
    reply_id: str,
    reply_title: str,
) -> tuple[bool, Optional[str]]:
    """
    Process a button/list tap deterministically — no LLM call needed.

    Returns (handled: bool, follow_up_text: Optional[str]).
      handled=True  → caller must NOT call Claude; advance is done here.
      follow_up_text → if not None, send this plain-text message to the user.

    slot_other is a special case: we mark the meta and return a follow-up
    question; the *next* free-text message will be captured as demo_slot.
    """
    phase = meta.get("phase", "GREETING")

    if phase == "BUSINESS_TYPE" and reply_id in _BUSINESS_TYPE_LABELS:
        meta["business_type"] = _BUSINESS_TYPE_LABELS[reply_id]
        meta["phase"] = "LOCATIONS"
        log.info(f"lead: interactive BUSINESS_TYPE → {meta['business_type']}")
        return True, None

    if phase == "LOCATIONS" and reply_id in _LOC_LABELS:
        meta["locations"] = _LOC_LABELS[reply_id]
        meta["phase"] = "CURRENT_SYSTEM"
        log.info(f"lead: interactive LOCATIONS → {meta['locations']}")
        return True, None

    if phase == "CURRENT_SYSTEM" and reply_id in _SYS_LABELS:
        meta["current_system"] = _SYS_LABELS[reply_id]
        meta["phase"] = "SCHEDULING"
        log.info(f"lead: interactive CURRENT_SYSTEM → {meta['current_system']}")
        return True, None

    if phase == "SCHEDULING":
        if reply_id == "slot_1":
            meta["demo_slot"] = DEMO_SLOT_1
            meta["phase"] = "CONFIRMED"
            log.info(f"lead: interactive SCHEDULING → {DEMO_SLOT_1}")
            return True, None
        if reply_id == "slot_2":
            meta["demo_slot"] = DEMO_SLOT_2
            meta["phase"] = "CONFIRMED"
            log.info(f"lead: interactive SCHEDULING → {DEMO_SLOT_2}")
            return True, None
        if reply_id == "slot_other":
            # Mark that next free-text = custom slot; don't advance phase yet
            meta["awaiting_custom_slot"] = True
            log.info("lead: interactive SCHEDULING → slot_other, awaiting free text")
            return True, "Kaunsa din/time aap ke liye theek hai? Likh dein 📅"

    # Unknown id for this phase — fall through to LLM
    log.warning(f"lead: interactive reply_id={reply_id!r} unhandled at phase={phase}")
    return False, None
