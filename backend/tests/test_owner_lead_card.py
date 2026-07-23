"""
Owner New Lead card — CONFIRMED path, credentials, exclusion direction, normalize.
"""

import os
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ["WHATSAPP_VERIFY_TOKEN"] = "testtoken"
os.environ["WHATSAPP_ACCESS_TOKEN"] = "env-token-stale"
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "12345"
os.environ["OWNER_WHATSAPP"] = "9200000000"
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-fake"
os.environ["FLOW_MODE"] = "lead"
os.environ["BUSINESS_WA_ID"] = "92300BUSINESS"
os.environ["CAMPAIGN_PHRASE"] = "Bahi POS"
os.environ["DEMO_SLOT_1"] = "Kal 11am"
os.environ["DEMO_SLOT_2"] = "Kal 4pm"

CUSTOMER = "923001111111"
OWNER = "9200000000"
PID_LIVE = "1223056090892433"
TOKEN_LIVE = "tenant-db-token-live"
TENANT_PID = "12345"


@pytest.fixture(autouse=True)
def reset_state():
    from app import gate, lead, sessions

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


def _text_payload(sender: str, text: str) -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": sender,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


def _slot_button_payload(sender: str) -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": sender,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": "slot_1",
                                            "title": "Kal 11am",
                                        },
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


def _lead_tenant(**overrides):
    from app.tenants import Tenant

    data = {
        "phone_number_id": PID_LIVE,
        "name": "AccellionX",
        "flow_mode": "lead",
        "owner_whatsapp": OWNER,
        "business_wa_id": "92300BUSINESS",
        "campaign_phrase": "Bahi POS",
        "demo_slots": ["Kal 11am", "Kal 4pm"],
    }
    data.update(overrides)
    t = Tenant.model_validate(data)
    t._raw_config = {
        "owner_whatsapp": data["owner_whatsapp"],
        "channels": {
            "whatsapp": {
                "access_token": TOKEN_LIVE,
                "account_id": PID_LIVE,
                "status": "live",
            }
        },
    }
    return t


# ── Normalize ────────────────────────────────────────────────────────────────


def test_normalize_wa_recipient_strips_plus_spaces_leading_zero():
    from app.lead import normalize_wa_recipient

    assert normalize_wa_recipient("+92 300 1234567") == "923001234567"
    assert normalize_wa_recipient("03001234567") == "3001234567"
    assert normalize_wa_recipient(" 9200000000 ") == "9200000000"
    assert normalize_wa_recipient("+92-000-0000") == "920000000"
    assert normalize_wa_recipient("") == ""
    assert normalize_wa_recipient(None) == ""


@pytest.mark.asyncio
async def test_forward_normalizes_malformed_owner():
    from app.lead import forward_lead_card
    from app.tenants import Tenant

    sent = []

    async def capture(to, text):
        sent.append((to, text))
        return True

    tenant = Tenant.model_validate(
        {
            "phone_number_id": PID_LIVE,
            "name": "T",
            "flow_mode": "lead",
            "demo_slots": ["A", "B"],
        }
    )
    await forward_lead_card(
        CUSTOMER,
        {"phase": "CONFIRMED", "business_name": "Shop", "demo_slot": "Kal 11am"},
        "+092 00000000",
        capture,
        tenant=tenant,
    )
    assert sent, "send_fn must be called"
    assert sent[0][0] == "9200000000"
    assert "Shop" in sent[0][1]


@pytest.mark.asyncio
async def test_forward_normalizes_owner_with_spaces():
    from app.lead import forward_lead_card
    from app.tenants import Tenant

    sent = []

    async def capture(to, text):
        sent.append(to)
        return True

    tenant = Tenant.model_validate(
        {
            "phone_number_id": PID_LIVE,
            "name": "T",
            "flow_mode": "lead",
            "demo_slots": ["A", "B"],
        }
    )
    await forward_lead_card(
        CUSTOMER,
        {"phase": "CONFIRMED", "business_name": "X", "demo_slot": "Tomorrow"},
        "+92 312 4195250",
        capture,
        tenant=tenant,
    )
    assert sent == ["923124195250"]


# ── CONFIRMED → owner card ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirmed_triggers_card_correct_recipient(client, mock_send, mock_claude):
    from app.lead import _meta

    _meta[(TENANT_PID, CUSTOMER)] = {
        "phase": "SCHEDULING",
        "lead_source": "ad",
        "business_name": "Karachi Mart",
        "business_type": "Retail",
        "locations": "1",
        "current_system": "Manual",
        "demo_slot": "Kal 11am",
    }
    mock_claude.return_value = _make_claude_reply(
        "Booked.\nLEAD_CONFIRMED"
    )
    r = await client.post("/webhook", json=_text_payload(CUSTOMER, "haan"))
    assert r.status_code == 200
    owner_calls = [c for c in mock_send.call_args_list if c.args and c.args[0] == OWNER]
    assert owner_calls, "Lead card must go to OWNER_WHATSAPP"
    assert "Karachi Mart" in owner_calls[0].args[1]


@pytest.mark.asyncio
async def test_slot_confirm_sends_owner_card(client, mock_send):
    from app.lead import _meta

    _meta[(TENANT_PID, CUSTOMER)] = {
        "phase": "SCHEDULING",
        "lead_source": "ad",
        "business_name": "Demo Co",
        "business_type": "Retail",
        "locations": "1",
        "current_system": "Manual",
    }
    r = await client.post("/webhook", json=_slot_button_payload(CUSTOMER))
    assert r.status_code == 200
    owner_calls = [c for c in mock_send.call_args_list if c.args and c.args[0] == OWNER]
    assert owner_calls
    assert "Demo Co" in owner_calls[0].args[1]


# ── Tenant phone_number_id + token (not import-time env) ─────────────────────


@pytest.mark.asyncio
async def test_lead_card_uses_tenant_phone_number_id_and_token(monkeypatch):
    """Graph POST must use tenant DB phone_number_id + channel access_token."""
    import app.main as main_mod
    from app.lead import forward_lead_card

    posts = []

    class FakeResp:
        status_code = 200
        text = '{"messages":[{"id":"wamid.x"}]}'

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            posts.append({"url": url, "headers": dict(headers or {}), "json": json})
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    # Poison import-time constant — send must NOT prefer it over tenant token
    monkeypatch.setattr(main_mod, "WHATSAPP_TOKEN", "MUST-NOT-USE")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "env-token-stale")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "env-pid-stale")

    tenant = _lead_tenant(owner_whatsapp="+92 000-00000")
    meta = {
        "phase": "CONFIRMED",
        "business_name": "Live Shop",
        "demo_slot": "Kal 11am",
        "lead_source": "ad",
    }

    await forward_lead_card(
        CUSTOMER,
        meta,
        tenant.owner_whatsapp,
        lambda to, txt: main_mod.send_whatsapp_message(to, txt, tenant=tenant),
        tenant=tenant,
    )

    assert posts, "Graph API must be called"
    post = posts[-1]
    assert PID_LIVE in post["url"], f"expected tenant pid in URL, got {post['url']}"
    assert "env-pid-stale" not in post["url"]
    assert post["headers"]["Authorization"] == f"Bearer {TOKEN_LIVE}"
    assert post["json"]["to"] == "9200000000"
    assert "Live Shop" in post["json"]["text"]["body"]


# ── Exclusion / mute must not block OUTBOUND to owner ────────────────────────


@pytest.mark.asyncio
async def test_owner_self_exclusion_does_not_block_outbound_to_owner(monkeypatch):
    import app.main as main_mod

    posts = []

    class FakeResp:
        status_code = 200
        text = "{}"

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            posts.append(json)
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    tenant = _lead_tenant()
    assert main_mod._is_own_number(OWNER, tenant) is True

    ok = await main_mod.send_whatsapp_message(
        OWNER, "New Lead\n\nShop booked", tenant=tenant
    )
    assert ok is True
    assert posts and posts[0]["to"] == OWNER


@pytest.mark.asyncio
async def test_muted_owner_does_not_block_owner_card(monkeypatch):
    """Mute store is inbound-only; outbound lead card to a muted owner still sends."""
    import app.main as main_mod
    from app.gate import mute_contact
    from app.lead import forward_lead_card

    posts = []

    class FakeResp:
        status_code = 200
        text = "{}"

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            posts.append({"url": url, "to": (json or {}).get("to")})
            return FakeResp()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    tenant = _lead_tenant()
    mute_contact(OWNER, tenant.phone_number_id)

    await forward_lead_card(
        CUSTOMER,
        {"phase": "CONFIRMED", "business_name": "MutedOwnerTest", "demo_slot": "A"},
        OWNER,
        lambda to, txt: main_mod.send_whatsapp_message(to, txt, tenant=tenant),
        tenant=tenant,
    )
    assert posts, "muted owner must still receive outbound card"
    assert posts[0]["to"] == OWNER
    assert PID_LIVE in posts[0]["url"]


@pytest.mark.asyncio
async def test_muted_customer_finalize_still_notifies_owner(monkeypatch):
    """If finalize runs while customer is muted, owner card still fires."""
    import app.main as main_mod
    from app.gate import mute_contact

    sent = []

    async def capture(to, text="", interactive_payload=None, tenant=None, **kw):
        sent.append(to)
        return True

    monkeypatch.setattr(main_mod, "send_whatsapp_message", capture)
    tenant = _lead_tenant(phone_number_id="12345", owner_whatsapp=OWNER)
    mute_contact(CUSTOMER, "12345")

    await main_mod._finalize_lead_confirmed(
        CUSTOMER,
        {
            "phase": "CONFIRMED",
            "business_name": "StillNotify",
            "demo_slot": "Kal 11am",
        },
        tenant,
        customer_text="Confirmed.",
    )
    assert OWNER in sent
    assert CUSTOMER in sent


def test_whatsapp_send_creds_prefers_tenant_over_env(monkeypatch):
    import app.main as main_mod

    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "env-only")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "env-pid")
    tenant = _lead_tenant()
    pid, token, url = main_mod._whatsapp_send_creds(tenant)
    assert pid == PID_LIVE
    assert token == TOKEN_LIVE
    assert PID_LIVE in url
    assert "env-pid" not in url
