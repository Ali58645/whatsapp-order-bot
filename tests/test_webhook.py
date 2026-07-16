"""
Smoke tests for the WhatsApp webhook — ORDER flow.

No network calls: Graph API (httpx) and Anthropic client are fully mocked.
Run with: pytest tests/test_webhook.py -v
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

# ---------------------------------------------------------------------------
# Environment stubs — must be set before app.main is imported
# ---------------------------------------------------------------------------
import os
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "testtoken")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "faketoken")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "12345")
os.environ.setdefault("OWNER_WHATSAPP", "9200000000")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fake")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text_payload(sender: str, text: str) -> dict:
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "from": sender,
                        "type": "text",
                        "text": {"body": text},
                    }]
                }
            }]
        }]
    }


def _status_payload() -> dict:
    """Delivered/read receipt — has no 'messages' key under value."""
    return {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{"status": "delivered", "id": "wamid.abc"}]
                }
            }]
        }]
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_sessions():
    """Wipe in-memory sessions between tests."""
    from app import sessions
    sessions._sessions.clear()
    sessions._locks.clear()
    yield
    sessions._sessions.clear()
    sessions._locks.clear()


@pytest.fixture()
def mock_send(monkeypatch):
    """Replace send_whatsapp_message with an async mock that records calls."""
    import app.main as main_mod
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr(main_mod, "send_whatsapp_message", mock)
    return mock


@pytest.fixture()
def order_mode(monkeypatch):
    """Force the single fallback tenant into order mode for these smoke tests."""
    import app.tenants as tenants_mod
    from app.tenants import Tenant

    # Build an order-mode tenant from the env stubs (menu.json must exist)
    order_tenant = Tenant.model_validate({
        "phone_number_id": "12345",
        "name": "Test Order Shop",
        "flow_mode": "order",
        "owner_whatsapp": "9200000000",
        "menu": {
            "shop_name": "Test Shop",
            "categories": [{"name": "Burgers", "items": [{"name": "Burger", "price": 300}]}],
        },
    })
    monkeypatch.setattr(tenants_mod, "_registry", {"12345": order_tenant})


@pytest.fixture()
def mock_claude_ok(monkeypatch):
    """Make AsyncAnthropic.messages.create return a simple reply."""
    import app.main as main_mod
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="Aapka order kya hoga?")]
    main_mod.anthropic_client.messages.create = AsyncMock(return_value=fake_response)


@pytest.fixture()
def mock_claude_error(monkeypatch):
    """Make AsyncAnthropic.messages.create raise an exception."""
    import app.main as main_mod
    main_mod.anthropic_client.messages.create = AsyncMock(
        side_effect=Exception("Anthropic timeout")
    )


@pytest_asyncio.fixture()
async def client():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_webhook_wrong_token(client):
    """GET /webhook with wrong verify_token → 403."""
    r = await client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "WRONG", "hub.challenge": "abc"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_webhook_correct_token(client):
    """GET /webhook with correct token → 200, challenge echoed as text/plain."""
    r = await client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "testtoken", "hub.challenge": "abc123"},
    )
    assert r.status_code == 200
    assert r.text == "abc123"
    assert "text/plain" in r.headers["content-type"]


@pytest.mark.asyncio
async def test_post_status_update_ignored(client, mock_send):
    """POST status-update payload (no 'messages' key) → 200, not treated as user message."""
    r = await client.post("/webhook", json=_status_payload())
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_post_empty_body_ignored(client, mock_send):
    """POST empty body {} → 200, ignored gracefully."""
    r = await client.post("/webhook", json={})
    assert r.status_code == 200
    assert r.json() == {"status": "ignored"}
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_post_text_message_sends_reply(client, mock_send, mock_claude_ok, order_mode):
    """POST text message → 200, send_whatsapp_message called with correct recipient."""
    sender = "923001234567"
    r = await client.post("/webhook", json=_text_payload(sender, "hi"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    # At least one send call must target the original sender
    recipients = [call.args[0] for call in mock_send.call_args_list]
    assert sender in recipients


@pytest.mark.asyncio
async def test_post_text_message_claude_error_returns_fallback(client, mock_send, mock_claude_error, order_mode):
    """POST text message when Claude raises → 200, fallback reply sent to sender."""
    sender = "923009999999"
    r = await client.post("/webhook", json=_text_payload(sender, "hello"))
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    # send must have been called (fallback message)
    mock_send.assert_called()
    # The fallback text should mention the sender
    call_args = mock_send.call_args_list
    assert any(call.args[0] == sender for call in call_args)
    # Fallback contains the expected sorry phrase
    fallback_texts = [call.args[1] for call in call_args if call.args[0] == sender]
    assert any("issue" in t or "dobara" in t for t in fallback_texts)
