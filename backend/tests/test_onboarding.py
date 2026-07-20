"""
Admin onboarding wizard — templates, Graph verify+subscribe, draft/activate, checklist.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "testtoken")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "faketoken")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "12345")
os.environ.setdefault("OWNER_WHATSAPP", "9200000000")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fake")
os.environ.setdefault("FLOW_MODE", "lead")

ADMIN_USER = "obadmin"
ADMIN_PASS = "obpass"
OWNER_USER = "obowner"
OWNER_PASS = "ownerpass"
JWT_SECRET = "ob-jwt-secret-key-32chars-long!!"
PID_SEED = "PID_OB_SEED"


@pytest.fixture
def ob_env(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", ADMIN_USER)
    monkeypatch.setenv("DASHBOARD_PASSWORD", ADMIN_PASS)
    monkeypatch.setenv("DASHBOARD_JWT_SECRET", JWT_SECRET)
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "faketoken")


@pytest_asyncio.fixture
async def ob_db(tmp_path, monkeypatch, ob_env):
    url = f"sqlite+aiosqlite:///{tmp_path}/ob.db"
    monkeypatch.setenv("DATABASE_URL", url)

    import app.db.engine as eng
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.dashboard.users import hash_password
    from app.db.models import Base, DBTenant
    from app.db.repo import create_user, sync_tenants_to_db
    from app.tenant_resolver import invalidate_all
    from app.tenants import Tenant

    if eng.engine is not None:
        await eng.engine.dispose()

    engine = create_async_engine(url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(eng, "DATABASE_URL", url)
    monkeypatch.setattr(eng, "DB_ENABLED", True)
    monkeypatch.setattr(eng, "engine", engine)
    monkeypatch.setattr(eng, "AsyncSessionLocal", factory)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    seed = Tenant(
        phone_number_id=PID_SEED,
        name="Seed Biz",
        flow_mode="lead",
        campaign_phrase="Bahi POS",
        demo_slots=["Kal 11am", "Kal 4pm"],
        status="live",
    )
    async with eng.get_db() as db:
        await sync_tenants_to_db(db, [seed])
        await create_user(
            db,
            username=ADMIN_USER,
            password_hash=hash_password(ADMIN_PASS),
            role="admin",
            tenant_id=None,
        )
        row = (
            await db.execute(select(DBTenant).where(DBTenant.phone_number_id == PID_SEED))
        ).scalar_one()
        await create_user(
            db,
            username=OWNER_USER,
            password_hash=hash_password(OWNER_PASS),
            role="owner",
            tenant_id=row.id,
        )

    invalidate_all()
    yield {"seed_id": row.id}
    await engine.dispose()
    monkeypatch.setattr(eng, "DB_ENABLED", False)
    monkeypatch.setattr(eng, "engine", None)
    monkeypatch.setattr(eng, "AsyncSessionLocal", None)
    monkeypatch.setattr(eng, "DATABASE_URL", "")
    invalidate_all()


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client: AsyncClient, user=ADMIN_USER, password=ADMIN_PASS) -> str:
    r = await client.post("/api/auth/login", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ── Templates ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_templates(client, ob_db):
    token = await _login(client)
    r = await client.get(
        "/api/dashboard/onboarding/templates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    ids = {i["id"] for i in r.json()["items"]}
    assert {"pos_lead", "restaurant", "salon_booking", "generic_lead"} <= ids


@pytest.mark.asyncio
async def test_template_seeds_apply():
    from app.onboarding import apply_template_to_config, get_template

    assert get_template("pos_lead") is not None
    cfg = apply_template_to_config(
        {},
        template_id="pos_lead",
        flow_mode="lead",
        greeting_language="roman_urdu",
        business_name="Test POS",
    )
    assert "POS" in cfg.get("campaign_phrase", "") or cfg.get("messages")
    assert cfg["messages"]["lead"]["greeting_line"]
    assert cfg["onboarding"]["template_id"] == "pos_lead"
    assert cfg["onboarding"]["content_set"] is True

    rest = apply_template_to_config(
        {},
        template_id="restaurant",
        flow_mode="order",
        greeting_language="roman_urdu",
        business_name="Cafe",
    )
    assert rest["menu_v2"]["items"]
    assert any(i["name"] == "Chicken Biryani" for i in rest["menu_v2"]["items"])


# ── Graph verify + subscribed_apps ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connection_test_hits_graph_and_autosubscribes(client, ob_db):
    token = await _login(client)

    class FakeResp:
        def __init__(self, status_code, data):
            self.status_code = status_code
            self._data = data
            self.content = b"{}"
            self.text = str(data)

        def json(self):
            return self._data

    calls = []

    class FakeClient:
        async def get(self, url, params=None, headers=None):
            calls.append(("GET", url))
            if "subscribed_apps" in url:
                return FakeResp(200, {"data": []})  # empty → needs subscribe
            return FakeResp(
                200,
                {
                    "display_phone_number": "+92 300 1112233",
                    "verified_name": "Test Biz WA",
                    "quality_rating": "GREEN",
                },
            )

        async def post(self, url, headers=None, json=None):
            calls.append(("POST", url))
            return FakeResp(200, {"success": True})

        async def aclose(self):
            return None

    import app.onboarding as ob_mod

    result = await ob_mod.verify_and_subscribe(
        phone_number_id="PID_NEW_1",
        waba_id="WABA_99",
        http_client=FakeClient(),
    )
    assert result["ok"] is True
    assert result["verified_name"] == "Test Biz WA"
    assert result["subscribed_apps"] is True
    assert result["subscribed_apps_fixed"] is True
    assert any(c[0] == "GET" and "PID_NEW_1" in c[1] for c in calls)
    assert any(c[0] == "GET" and "WABA_99/subscribed_apps" in c[1] for c in calls)
    assert any(c[0] == "POST" and "WABA_99/subscribed_apps" in c[1] for c in calls)

    with patch("app.onboarding.verify_and_subscribe", new_callable=AsyncMock) as mock_v:
        mock_v.return_value = {
            "ok": True,
            "phone_number_id": "PID_X",
            "verified_name": "X",
            "display_phone_number": "+1",
            "subscribed_apps": True,
            "subscribed_apps_fixed": False,
        }
        r = await client.post(
            "/api/dashboard/whatsapp/verify",
            headers={"Authorization": f"Bearer {token}"},
            json={"phone_number_id": "PID_X", "waba_id": "WABA_X"},
        )
        assert r.status_code == 200, r.text
        mock_v.assert_awaited()
        assert mock_v.await_args.kwargs["waba_id"] == "WABA_X"


# ── Draft / activate lifecycle ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wizard_creates_routable_tenant(client, ob_db):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/dashboard/onboarding/draft",
        headers=headers,
        json={
            "name": "Onboard Cafe",
            "flow_mode": "order",
            "phone_number_id": "PID_OB_LIVE_1",
            "business_wa_id": "92300111",
            "owner_whatsapp": "923009998877",
            "greeting_language": "roman_urdu",
            "template_id": "restaurant",
            "waba_id": "WABA_1",
            "connection_verified": True,
            "subscribed_apps": True,
            "sheet_tested": False,
            "verified_name": "Onboard Cafe",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "draft"
    tid = body["id"]
    assert body["checklist"]["items"]

    with patch("app.main.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        act = await client.post(
            f"/api/dashboard/onboarding/{tid}/activate",
            headers=headers,
            json={"send_test": True},
        )
        assert act.status_code == 200, act.text
        assert act.json()["status"] == "live"
        assert act.json()["test_message_sent"] is True
        mock_send.assert_awaited()
        assert mock_send.await_args.args[0] == "923009998877"
        tenant_arg = mock_send.await_args.kwargs.get("tenant")
        assert tenant_arg is not None
        assert tenant_arg.phone_number_id == "PID_OB_LIVE_1"

    # Routable immediately via resolver
    from app.tenant_resolver import resolve_tenant

    t = await resolve_tenant("PID_OB_LIVE_1")
    assert t is not None
    assert t.name == "Onboard Cafe"
    assert t.is_live
    assert t.menu_v2 and t.menu_v2.get("items")


@pytest.mark.asyncio
async def test_draft_then_update_and_checklist(client, ob_db):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/dashboard/onboarding/draft",
        headers=headers,
        json={
            "name": "Draft Salon",
            "flow_mode": "lead",
            "phone_number_id": "PID_OB_DRAFT",
            "owner_whatsapp": "923001112233",
            "template_id": "salon_booking",
            "connection_verified": True,
            "subscribed_apps": True,
        },
    )
    assert r.status_code == 200
    tid = r.json()["id"]

    r2 = await client.post(
        "/api/dashboard/onboarding/draft",
        headers=headers,
        json={
            "tenant_id": tid,
            "name": "Draft Salon Updated",
            "flow_mode": "lead",
            "phone_number_id": "PID_OB_DRAFT",
            "owner_whatsapp": "923001112233",
            "template_id": "salon_booking",
            "connection_verified": True,
            "subscribed_apps": True,
        },
    )
    assert r2.status_code == 200
    assert r2.json()["name"] == "Draft Salon Updated"

    cl = await client.get(
        f"/api/dashboard/tenants/{tid}/checklist",
        headers=headers,
    )
    assert cl.status_code == 200
    items = {i["id"]: i["done"] for i in cl.json()["items"]}
    assert items["number_connected"] is True
    assert items["webhooks_subscribed"] is True
    assert items["content_set"] is True
    assert items["test_message_delivered"] is False


@pytest.mark.asyncio
async def test_owner_cannot_access_onboarding(client, ob_db):
    token = await _login(client, OWNER_USER, OWNER_PASS)
    r = await client.get(
        "/api/dashboard/onboarding/templates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_parse_sheet_id():
    from app.onboarding import parse_sheet_id

    assert (
        parse_sheet_id("https://docs.google.com/spreadsheets/d/abcXYZ1234567890abcd/edit")
        == "abcXYZ1234567890abcd"
    )
    assert parse_sheet_id("abcXYZ1234567890abcd") == "abcXYZ1234567890abcd"
    assert parse_sheet_id("not-a-sheet") == ""
