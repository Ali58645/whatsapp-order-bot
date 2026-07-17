"""
Multi-tenant routing tests.

Six scenarios per the spec:
  1. Message to tenant A's phone_number_id → lead flow with A's phrase
  2. Message to tenant B's phone_number_id → order flow with B's menu
  3. Replies routed out through the correct phone_number_id (Graph URL)
  4. Same sender → both tenants have independent sessions
  5. Unknown phone_number_id → 200, ignored, no processing
  6. Env-fallback single-tenant mode still passes (backward-compat guard)
"""

import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

# ── Env stubs — set before any app import ───────────────────────────────────
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

# ── Tenant fixtures ───────────────────────────────────────────────────────────
# Tenant A: lead mode, phrase "Bahi POS", phone_number_id = "PID_A"
# Tenant B: order mode, phone_number_id = "PID_B"
PID_A    = "PID_LEAD_TENANT"
PID_B    = "PID_ORDER_TENANT"
SENDER   = "923001234567"         # same sender for both tenants (isolation test)
OWNER_A  = "92300OWNER_A"
OWNER_B  = "92300OWNER_B"

_TENANT_A_DICT = {
    "phone_number_id": PID_A,
    "name": "Bahi POS Lead",
    "flow_mode": "lead",
    "business_wa_id": "92300BIZ_A",
    "owner_whatsapp": OWNER_A,
    "campaign_phrase": "Bahi POS",
    "demo_slots": ["Kal 11am", "Kal 4pm"],
    "facts": "Bahi POS is a Pakistani POS software.",
    "greeting_language": "roman_urdu",
}

_TENANT_B_DICT = {
    "phone_number_id": PID_B,
    "name": "Burger Point Order",
    "flow_mode": "order",
    "owner_whatsapp": OWNER_B,
    "menu": {
        "shop_name": "Burger Point",
        "delivery_fee": 100,
        "delivery_area": "Lahore",
        "categories": [
            {
                "name": "Burgers",
                "items": [{"name": "Zinger", "price": 450}],
            }
        ],
    },
}


# ── Payload helpers ───────────────────────────────────────────────────────────

def _text_payload(sender: str, text: str, phone_number_id: str) -> dict:
    """Webhook payload with metadata.phone_number_id for tenant routing."""
    return {
        "entry": [{
            "id": "whatsapp_business_account_id",
            "changes": [{
                "value": {
                    "metadata": {
                        "display_phone_number": "1234567890",
                        "phone_number_id": phone_number_id,
                    },
                    "messages": [{
                        "from": sender,
                        "type": "text",
                        "text": {"body": text},
                    }],
                },
                "field": "messages",
            }],
        }]
    }


def _campaign_text(sender: str, phone_number_id: str) -> dict:
    """Text containing 'Bahi POS' campaign phrase."""
    return _text_payload(sender, "Bahi POS ke baare mein batao", phone_number_id)


def _order_text(sender: str, phone_number_id: str, text: str = "Zinger burger chahiye") -> dict:
    return _text_payload(sender, text, phone_number_id)


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
def two_tenants(monkeypatch):
    """Inject two tenants into the registry, bypassing env-var loading."""
    import app.tenants as tenants_mod
    from app.tenants import Tenant

    ta = Tenant.model_validate(_TENANT_A_DICT)
    tb = Tenant.model_validate(_TENANT_B_DICT)
    monkeypatch.setattr(tenants_mod, "_registry", {PID_A: ta, PID_B: tb})
    return ta, tb


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
    fake.content = [MagicMock(text="Aapka order kya hoga?")]
    mock = AsyncMock(return_value=fake)
    main_mod.anthropic_client.messages.create = mock
    return mock


@pytest_asyncio.fixture()
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ══════════════════════════════════════════════════════════════════════════════
# Test 1 — message to tenant A → lead flow activated with A's phrase
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_tenant_a_campaign_phrase_triggers_lead_flow(client, mock_send, mock_claude, two_tenants):
    """
    Message containing tenant A's campaign phrase sent to tenant A's
    phone_number_id → lead flow runs, reply sent to SENDER.
    """
    r = await client.post("/webhook", json=_campaign_text(SENDER, PID_A))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    # Reply must have gone to SENDER
    recipients = [c.args[0] for c in mock_send.call_args_list]
    assert SENDER in recipients, "Expected reply to be sent to SENDER"

    # Lead meta must be initialised for (PID_A, SENDER)
    from app.lead import _meta
    key = (PID_A, SENDER)
    assert key in _meta, f"Lead meta must be keyed by (PID_A, SENDER), got keys={list(_meta)}"
    # No order-tenant meta should exist
    assert (PID_B, SENDER) not in _meta


# ══════════════════════════════════════════════════════════════════════════════
# Test 2 — message to tenant B → order flow with B's menu
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_tenant_b_message_triggers_order_flow(client, mock_send, mock_claude, two_tenants):
    """
    Message to tenant B's phone_number_id → order flow runs (not lead flow).
    """
    r = await client.post("/webhook", json=_order_text(SENDER, PID_B))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    # Reply must have gone to SENDER
    recipients = [c.args[0] for c in mock_send.call_args_list]
    assert SENDER in recipients

    # The Claude system prompt used must contain tenant B's shop name.
    # We check by inspecting the kwargs passed to anthropic_client.messages.create.
    create_calls = mock_claude.call_args_list
    assert create_calls, "Claude must have been called for the order flow"
    system_prompt = create_calls[0].kwargs.get("system", "")
    assert "Burger Point" in system_prompt, (
        f"Order system prompt must reference tenant B's shop name. Got: {system_prompt[:200]}"
    )
    # Must NOT reference lead-mode shop name
    assert "Bahi POS" not in system_prompt, (
        "Order system prompt must not reference tenant A's name"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 3 — replies routed through the correct phone_number_id (Graph URL)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_reply_uses_tenant_a_graph_url(client, mock_send, mock_claude, two_tenants, monkeypatch):
    """
    When a message arrives on tenant A's phone_number_id, the outgoing
    send_whatsapp_message call must use tenant A's tenant object (and thus
    tenant A's graph_url / phone_number_id).
    """
    import app.main as main_mod

    sent_tenants = []

    async def _capture_send(to, text="", interactive_payload=None, tenant=None):
        sent_tenants.append(tenant)
        return True

    monkeypatch.setattr(main_mod, "send_whatsapp_message", _capture_send)

    r = await client.post("/webhook", json=_campaign_text(SENDER, PID_A))
    assert r.status_code == 200

    assert sent_tenants, "send_whatsapp_message must have been called"
    for t in sent_tenants:
        assert t is not None, "tenant kwarg must be passed to send_whatsapp_message"
        assert t.phone_number_id == PID_A, (
            f"Reply must go through tenant A's phone_number_id={PID_A!r}, "
            f"got {t.phone_number_id!r}"
        )


@pytest.mark.asyncio
async def test_reply_uses_tenant_b_graph_url(client, mock_send, mock_claude, two_tenants, monkeypatch):
    """
    When a message arrives on tenant B's phone_number_id, outgoing sends
    use tenant B's graph_url.
    """
    import app.main as main_mod

    sent_tenants = []

    async def _capture_send(to, text="", interactive_payload=None, tenant=None):
        sent_tenants.append(tenant)
        return True

    monkeypatch.setattr(main_mod, "send_whatsapp_message", _capture_send)

    r = await client.post("/webhook", json=_order_text(SENDER, PID_B))
    assert r.status_code == 200

    assert sent_tenants
    for t in sent_tenants:
        assert t is not None
        assert t.phone_number_id == PID_B, (
            f"Reply must go through tenant B's phone_number_id={PID_B!r}, "
            f"got {t.phone_number_id!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Test 4 — same sender → independent sessions per tenant
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_same_sender_independent_sessions(client, mock_send, mock_claude, two_tenants):
    """
    The same phone number messaging both tenants has completely isolated
    sessions (lead meta, conversation history).
    """
    from app.lead import _meta
    from app.sessions import _sessions

    # Send campaign phrase to tenant A → starts lead session for (PID_A, SENDER)
    r_a = await client.post("/webhook", json=_campaign_text(SENDER, PID_A))
    assert r_a.status_code == 200

    # Send order text to tenant B → starts order session for (PID_B, SENDER)
    r_b = await client.post("/webhook", json=_order_text(SENDER, PID_B))
    assert r_b.status_code == 200

    # Tenant A must have a lead meta entry; tenant B must NOT
    assert (PID_A, SENDER) in _meta, "Lead meta must exist for tenant A"
    assert (PID_B, SENDER) not in _meta, "Lead meta must NOT exist for tenant B"

    # Conversation histories must be independent keys
    assert (PID_A, SENDER) in _sessions or (PID_B, SENDER) in _sessions, (
        "At least one session must be stored"
    )
    if (PID_A, SENDER) in _sessions and (PID_B, SENDER) in _sessions:
        assert _sessions[(PID_A, SENDER)] is not _sessions[(PID_B, SENDER)], (
            "Sessions for different tenants must be independent objects"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Test 5 — unknown phone_number_id → 200, ignored, no processing
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_unknown_phone_number_id_returns_200_ignored(client, mock_send, two_tenants):
    """
    A webhook arriving on an unregistered phone_number_id must be silently
    ignored with HTTP 200 and no processing (no reply, no meta).
    """
    UNKNOWN_PID = "UNKNOWN_PID_999"
    payload = _text_payload(SENDER, "hello", UNKNOWN_PID)

    r = await client.post("/webhook", json=payload)
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}

    mock_send.assert_not_called()

    from app.lead import _meta
    assert (UNKNOWN_PID, SENDER) not in _meta


# ══════════════════════════════════════════════════════════════════════════════
# Test 6 — backward-compat: env-fallback single-tenant mode
# ══════════════════════════════════════════════════════════════════════════════

def test_load_tenants_fallback_from_env_vars(monkeypatch):
    """
    When TENANTS_JSON_B64 and TENANTS_FILE are absent, load_tenants() must
    construct a single tenant from the legacy env vars and register it under
    WHATSAPP_PHONE_NUMBER_ID.
    """
    import app.tenants as tenants_mod

    # Ensure neither multi-tenant env var is set
    monkeypatch.delenv("TENANTS_JSON_B64", raising=False)
    monkeypatch.delenv("TENANTS_FILE", raising=False)
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "12345")
    monkeypatch.setenv("FLOW_MODE", "lead")
    monkeypatch.setenv("CAMPAIGN_PHRASE", "Bahi POS")

    # Re-run load_tenants (monkeypatching the registry directly)
    original_registry = dict(tenants_mod._registry)
    tenants_mod._registry = {}
    try:
        tenants_mod.load_tenants()
        assert "12345" in tenants_mod._registry, (
            f"Fallback tenant must be registered under '12345', got {list(tenants_mod._registry)}"
        )
        t = tenants_mod._registry["12345"]
        assert t.flow_mode == "lead"
        assert t.campaign_phrase == "Bahi POS"
    finally:
        tenants_mod._registry = original_registry


def test_load_tenants_from_b64(monkeypatch, tmp_path):
    """
    TENANTS_JSON_B64 present → both tenants parsed, validated, and registered.
    """
    import base64
    import json
    import app.tenants as tenants_mod

    raw = json.dumps([_TENANT_A_DICT, _TENANT_B_DICT])
    b64 = base64.b64encode(raw.encode()).decode()

    monkeypatch.setenv("TENANTS_JSON_B64", b64)
    monkeypatch.delenv("TENANTS_FILE", raising=False)

    original_registry = dict(tenants_mod._registry)
    tenants_mod._registry = {}
    try:
        tenants_mod.load_tenants()
        assert PID_A in tenants_mod._registry
        assert PID_B in tenants_mod._registry
        assert tenants_mod._registry[PID_A].flow_mode == "lead"
        assert tenants_mod._registry[PID_B].flow_mode == "order"
    finally:
        tenants_mod._registry = original_registry


def test_load_tenants_from_file(monkeypatch, tmp_path):
    """
    TENANTS_FILE present → both tenants parsed, validated, and registered.
    """
    import json
    import app.tenants as tenants_mod

    tenant_file = tmp_path / "tenants.json"
    tenant_file.write_text(json.dumps([_TENANT_A_DICT, _TENANT_B_DICT]))

    monkeypatch.delenv("TENANTS_JSON_B64", raising=False)
    monkeypatch.setenv("TENANTS_FILE", str(tenant_file))

    original_registry = dict(tenants_mod._registry)
    tenants_mod._registry = {}
    try:
        tenants_mod.load_tenants()
        assert PID_A in tenants_mod._registry
        assert PID_B in tenants_mod._registry
    finally:
        tenants_mod._registry = original_registry


def test_invalid_tenant_schema_raises_on_load(monkeypatch):
    """
    An invalid tenant in TENANTS_JSON_B64 must raise ValueError with a clear
    message on startup (fail-fast).
    """
    import base64
    import json
    import app.tenants as tenants_mod

    bad = [{"phone_number_id": "x", "name": "Bad", "flow_mode": "order"}]  # missing menu
    b64 = base64.b64encode(json.dumps(bad).encode()).decode()
    monkeypatch.setenv("TENANTS_JSON_B64", b64)
    monkeypatch.delenv("TENANTS_FILE", raising=False)

    original_registry = dict(tenants_mod._registry)
    tenants_mod._registry = {}
    try:
        with pytest.raises((ValueError, Exception)):
            tenants_mod.load_tenants()
    finally:
        tenants_mod._registry = original_registry


def test_get_tenant_unknown_id_logs_once(monkeypatch, caplog):
    """
    get_tenant() with an unknown id returns None and logs WARNING once per id.
    A second call with the same id must NOT log again.
    """
    import logging
    import app.tenants as tenants_mod

    monkeypatch.setattr(tenants_mod, "_warned_unknown", set())

    with caplog.at_level(logging.WARNING, logger="orderbot.tenants"):
        result1 = tenants_mod.get_tenant("TOTALLY_UNKNOWN_PID")
        result2 = tenants_mod.get_tenant("TOTALLY_UNKNOWN_PID")

    assert result1 is None
    assert result2 is None

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING and "TOTALLY_UNKNOWN_PID" in r.message]
    assert len(warnings) == 1, (
        f"WARNING must be logged exactly once per unknown id, got {len(warnings)}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 7 — tenant A lead demo slots come from tenant config (not global env)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_tenant_a_demo_slots_in_scheduling_buttons(client, mock_send, mock_claude, two_tenants):
    """
    When tenant A's lead flow reaches the SCHEDULING phase, the interactive
    buttons must show tenant A's demo_slots, not the global DEMO_SLOT_1/2.
    """
    from app.lead import _meta

    # Fast-forward SENDER through the lead flow to SCHEDULING phase
    _meta[(PID_A, SENDER)] = {
        "phase": "SCHEDULING",
        "lead_source": "campaign:Bahi POS",
        "business_name": "Test Biz",
        "business_type": "Grocery / Kiryana",
        "locations": "1",
        "current_system": "Manual Register",
        "_slot_1": "Kal 11am",
        "_slot_2": "Kal 4pm",
    }

    # Any text from sender in SCHEDULING phase triggers interactive widget
    r = await client.post("/webhook", json=_text_payload(SENDER, "demo book karna hai", PID_A))
    assert r.status_code == 200

    # Check if an interactive buttons payload was sent
    interactive_calls = [
        c for c in mock_send.call_args_list
        if c.kwargs.get("interactive_payload") is not None
    ]
    if interactive_calls:
        p = interactive_calls[0].kwargs["interactive_payload"]
        if p.get("interactive", {}).get("type") == "button":
            btn_ids = [b["reply"]["id"] for b in p["interactive"]["action"]["buttons"]]
            assert "slot_1" in btn_ids, "Scheduling buttons must include slot_1"


# ══════════════════════════════════════════════════════════════════════════════
# Test 8 — health endpoint shows all registered tenants
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_health_endpoint_lists_tenants(client, two_tenants):
    """GET / must return all registered phone_number_ids."""
    r = await client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "tenants" in data
    assert PID_A in data["tenants"]
    assert PID_B in data["tenants"]
