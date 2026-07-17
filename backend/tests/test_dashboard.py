"""
Dashboard API tests — auth, overview, leads filter, mute, env gating.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Base env before app imports
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "testtoken")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "faketoken")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "12345")
os.environ.setdefault("OWNER_WHATSAPP", "9200000000")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fake")
os.environ.setdefault("FLOW_MODE", "lead")
os.environ.setdefault("BUSINESS_WA_ID", "92300BUSINESS")
os.environ.setdefault("CAMPAIGN_PHRASE", "Bahi POS")

PID = "PID_DASH_TEST"
USER = "dashadmin"
PASS = "dashsecret"
JWT_SECRET = "test-jwt-secret-for-dashboard-v1"


def _make_tenant():
    from app.tenants import Tenant
    return Tenant(
        phone_number_id=PID,
        name="Dash Tenant",
        flow_mode="lead",
        business_wa_id="92300BIZ",
        owner_whatsapp="9200000000",
        campaign_phrase="Bahi POS",
        demo_slots=["Kal 11am", "Kal 4pm"],
    )


@pytest.fixture
def dash_env(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", USER)
    monkeypatch.setenv("DASHBOARD_PASSWORD", PASS)
    monkeypatch.setenv("DASHBOARD_JWT_SECRET", JWT_SECRET)


@pytest_asyncio.fixture
async def db_dash(tmp_path, monkeypatch, dash_env):
    """SQLite DB + dashboard env + seeded leads/events."""
    url = f"sqlite+aiosqlite:///{tmp_path}/dash.db"
    monkeypatch.setenv("DATABASE_URL", url)

    import app.db.engine as eng
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.db.models import Base, DBContact, DBEvent, DBLead, DBSession
    from app.db.repo import sync_tenants_to_db

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

    tenant = _make_tenant()
    # Register in runtime tenant registry for MuteStore
    import app.tenants as tenants_mod
    monkeypatch.setattr(tenants_mod, "_registry", {PID: tenant})

    now = datetime.now(timezone.utc)
    async with eng.get_db() as db:
        await sync_tenants_to_db(db, [tenant])
        await db.flush()
        from sqlalchemy import select
        from app.db.models import DBTenant
        tid = (
            await db.execute(select(DBTenant.id).where(DBTenant.phone_number_id == PID))
        ).scalar_one()

        contact = DBContact(
            tenant_id=tid, wa_id="923001112233", profile_name="Ali Test",
            first_seen=now, last_seen=now,
        )
        db.add(contact)
        await db.flush()

        sess = DBSession(
            tenant_id=tid, contact_id=contact.id, flow_mode="lead",
            phase="BUSINESS_NAME", meta={"phase": "BUSINESS_NAME"},
            history=[
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "Salam!"},
            ],
            status="active", created_at=now, updated_at=now,
        )
        db.add(sess)
        await db.flush()

        db.add(DBLead(
            tenant_id=tid, contact_id=contact.id, session_id=sess.id,
            business_name="Ali Store", business_type="Retail",
            status="active", ad_source="Ad: test",
            created_at=now, updated_at=now,
        ))
        db.add(DBLead(
            tenant_id=tid, contact_id=contact.id, session_id=sess.id,
            business_name="Done Shop", business_type="Clinic",
            status="confirmed", demo_slot="Kal 11am",
            created_at=now, updated_at=now,
        ))
        db.add(DBEvent(
            tenant_id=tid, contact_id=contact.id, type="activation",
            payload={"lead_source": "test"}, created_at=now,
        ))

    yield {"tenant": tenant, "contact_wa": "923001112233"}

    await engine.dispose()
    monkeypatch.setattr(eng, "DB_ENABLED", False)
    monkeypatch.setattr(eng, "engine", None)
    monkeypatch.setattr(eng, "AsyncSessionLocal", None)
    monkeypatch.setattr(eng, "DATABASE_URL", "")


@pytest_asyncio.fixture
async def client():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _token(client: AsyncClient) -> str:
    r = await client.post(
        "/api/auth/login",
        json={"username": USER, "password": PASS},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ── Env gating ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_absent_without_env(client, monkeypatch):
    monkeypatch.delenv("DASHBOARD_USER", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    monkeypatch.delenv("DASHBOARD_JWT_SECRET", raising=False)
    r = await client.post("/api/auth/login", json={"username": "x", "password": "y"})
    assert r.status_code == 404
    r2 = await client.get("/api/dashboard/overview")
    assert r2.status_code == 404


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_wrong_password(client, dash_env):
    r = await client.post(
        "/api/auth/login",
        json={"username": USER, "password": "wrong"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_overview_no_token_401(client, dash_env, db_dash):
    r = await client.get("/api/dashboard/overview")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_overview_good_token_200(client, db_dash):
    token = await _token(client)
    r = await client.get(
        "/api/dashboard/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["leads_today"] == 2
    assert body["leads_by_status"].get("active") == 1
    assert body["leads_by_status"].get("confirmed") == 1
    assert body["demos_scheduled"] == 1
    assert len(body["recent_events"]) >= 1


# ── Leads filter ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_leads_filter_by_status(client, db_dash):
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    r = await client.get("/api/dashboard/leads?status=confirmed", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["business_name"] == "Done Shop"
    assert items[0]["status"] == "confirmed"


# ── Mute ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mute_endpoint_writes_store(client, db_dash):
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    wa = db_dash["contact_wa"]
    r = await client.post(
        "/api/dashboard/mutes",
        headers=headers,
        json={"tenant_id": PID, "wa_id": wa, "mute": True, "duration_s": 3600},
    )
    assert r.status_code == 200
    assert r.json()["muted"] is True

    from app.db.store import MuteStore
    assert await MuteStore.is_muted(wa, db_dash["tenant"]) is True

    r2 = await client.post(
        "/api/dashboard/mutes",
        headers=headers,
        json={"tenant_id": PID, "wa_id": wa, "mute": False},
    )
    assert r2.status_code == 200
    assert await MuteStore.is_muted(wa, db_dash["tenant"]) is False


# ── 503 without DB ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dashboard_503_without_db(client, dash_env, monkeypatch):
    import app.db.engine as eng
    monkeypatch.setattr(eng, "DB_ENABLED", False)
    token = await _token(client)
    r = await client.get(
        "/api/dashboard/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 503
    assert "DATABASE_URL" in r.json()["detail"]
