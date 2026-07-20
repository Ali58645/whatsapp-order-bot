"""
Dashboard conversation send — agent reply, mute, window, role scoping.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "testtoken")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "faketoken")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "12345")
os.environ.setdefault("OWNER_WHATSAPP", "9200000000")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fake")
os.environ.setdefault("FLOW_MODE", "lead")

PID = "PID_SEND_TEST"
PID_OTHER = "PID_SEND_OTHER"
ADMIN_USER = "sendadmin"
ADMIN_PASS = "sendsecret"
OWNER_USER = "sendowner"
OWNER_PASS = "ownerpass"
JWT_SECRET = "test-jwt-secret-send"


def _make_tenant(phone_id: str, name: str):
    from app.tenants import Tenant

    return Tenant(
        phone_number_id=phone_id,
        name=name,
        flow_mode="lead",
        business_wa_id="92300BIZ",
        owner_whatsapp="9200000000",
        campaign_phrase="Bahi POS",
        demo_slots=["Kal 11am", "Kal 4pm"],
    )


@pytest.fixture
def send_env(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", ADMIN_USER)
    monkeypatch.setenv("DASHBOARD_PASSWORD", ADMIN_PASS)
    monkeypatch.setenv("DASHBOARD_JWT_SECRET", JWT_SECRET)


@pytest.fixture
def mock_send(monkeypatch):
    import app.main as main_mod

    calls: list[dict] = []

    async def _mock(to, text="", interactive_payload=None, tenant=None):
        calls.append(
            {
                "to": to,
                "text": text,
                "tenant": tenant,
                "graph_url": tenant.graph_url if tenant else None,
            }
        )
        return True

    monkeypatch.setattr(main_mod, "send_whatsapp_message", _mock)
    return calls


@pytest_asyncio.fixture
async def send_db(tmp_path, monkeypatch, send_env):
    url = f"sqlite+aiosqlite:///{tmp_path}/send.db"
    monkeypatch.setenv("DATABASE_URL", url)

    import app.db.engine as eng
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.dashboard.users import hash_password
    from app.db.models import Base, DBContact, DBLead, DBSession, DBTenant
    from app.db.repo import create_user, get_user_by_username, sync_tenants_to_db

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

    tenant = _make_tenant(PID, "Send Tenant")
    other = _make_tenant(PID_OTHER, "Other Tenant")
    import app.tenants as tenants_mod

    monkeypatch.setattr(tenants_mod, "_registry", {PID: tenant, PID_OTHER: other})

    now = datetime.now(timezone.utc)
    async with eng.get_db() as db:
        await sync_tenants_to_db(db, [tenant, other])
        await db.flush()

        row = (
            await db.execute(select(DBTenant).where(DBTenant.phone_number_id == PID))
        ).scalar_one()
        other_row = (
            await db.execute(select(DBTenant).where(DBTenant.phone_number_id == PID_OTHER))
        ).scalar_one()

        if not await get_user_by_username(db, OWNER_USER):
            await create_user(
                db,
                username=OWNER_USER,
                password_hash=hash_password(OWNER_PASS),
                role="owner",
                tenant_id=row.id,
            )

        contact = DBContact(
            tenant_id=row.id,
            wa_id="923001112233",
            profile_name="Ali Test",
            first_seen=now,
            last_seen=now,
        )
        db.add(contact)
        await db.flush()

        other_contact = DBContact(
            tenant_id=other_row.id,
            wa_id="923009998877",
            profile_name="Other",
            first_seen=now,
            last_seen=now,
        )
        db.add(other_contact)
        await db.flush()

        sess = DBSession(
            tenant_id=row.id,
            contact_id=contact.id,
            flow_mode="lead",
            phase="BUSINESS_NAME",
            meta={"phase": "BUSINESS_NAME"},
            history=[
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "Salam!"},
            ],
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(sess)
        await db.flush()

        lead = DBLead(
            tenant_id=row.id,
            contact_id=contact.id,
            session_id=sess.id,
            business_name="Ali Store",
            business_type="Retail",
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.add(lead)

    yield {
        "tenant": tenant,
        "contact_id": contact.id,
        "other_contact_id": other_contact.id,
        "wa": contact.wa_id,
        "lead_id": lead.id,
    }

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


async def _token(client: AsyncClient, user: str = ADMIN_USER, password: str = ADMIN_PASS) -> str:
    r = await client.post("/api/auth/login", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_send_appends_mutes_and_events(client, send_db, mock_send):
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    cid = send_db["contact_id"]

    r = await client.post(
        f"/api/dashboard/conversations/{cid}/send",
        headers=headers,
        json={"text": "Hello from agent"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window_open"] is True
    assert body["history"][-1] == {
        "role": "human_agent",
        "content": "Hello from agent",
        "sender": "human_agent",
    }

    from app.db.store import MuteStore

    assert await MuteStore.is_muted(send_db["wa"], send_db["tenant"]) is True

    ev = await client.get(
        "/api/dashboard/events?type=human_takeover",
        headers=headers,
    )
    assert ev.status_code == 200
    items = ev.json()["items"]
    assert any(i["payload"].get("source") == "dashboard_send" for i in items)


@pytest.mark.asyncio
async def test_send_posts_graph_with_tenant_phone_id(client, send_db, mock_send):
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    cid = send_db["contact_id"]

    r = await client.post(
        f"/api/dashboard/conversations/{cid}/send",
        headers=headers,
        json={"text": "Graph check"},
    )
    assert r.status_code == 200, r.text
    assert len(mock_send) == 1
    call = mock_send[0]
    assert call["to"] == send_db["wa"]
    assert call["text"] == "Graph check"
    assert call["tenant"] is not None
    assert PID in call["graph_url"]


@pytest.mark.asyncio
async def test_send_rejected_when_window_closed(client, send_db, mock_send):
    import app.db.engine as eng
    from app.db.models import DBContact
    from sqlalchemy import select

    old = datetime.now(timezone.utc) - timedelta(hours=25)
    async with eng.get_db() as db:
        contact = (
            await db.execute(select(DBContact).where(DBContact.id == send_db["contact_id"]))
        ).scalar_one()
        contact.last_seen = old

    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    cid = send_db["contact_id"]

    preview = await client.get(f"/api/dashboard/conversations/{cid}", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["window_open"] is False

    r = await client.post(
        f"/api/dashboard/conversations/{cid}/send",
        headers=headers,
        json={"text": "Too late"},
    )
    assert r.status_code == 400
    assert "Window closed" in r.json()["detail"]
    assert mock_send == []


@pytest.mark.asyncio
async def test_owner_cannot_send_to_other_tenant_contact(client, send_db, mock_send):
    owner_token = await _token(client, OWNER_USER, OWNER_PASS)
    headers = {"Authorization": f"Bearer {owner_token}"}
    other_cid = send_db["other_contact_id"]

    r = await client.post(
        f"/api/dashboard/conversations/{other_cid}/send",
        headers=headers,
        json={"text": "Cross-tenant"},
    )
    assert r.status_code == 403
    assert mock_send == []


@pytest.mark.asyncio
async def test_owner_can_send_within_own_tenant(client, send_db, mock_send):
    owner_token = await _token(client, OWNER_USER, OWNER_PASS)
    headers = {"Authorization": f"Bearer {owner_token}"}
    cid = send_db["contact_id"]

    r = await client.post(
        f"/api/dashboard/conversations/{cid}/send",
        headers=headers,
        json={"text": "Owner reply"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["history"][-1]["content"] == "Owner reply"
    assert len(mock_send) == 1
