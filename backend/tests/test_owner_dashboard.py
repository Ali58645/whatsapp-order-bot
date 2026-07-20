"""
Owner dashboard — tenant scoping, wiring reject, admin-only endpoints, view-as.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "testtoken")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "faketoken")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "12345")
os.environ.setdefault("OWNER_WHATSAPP", "9200000000")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fake")
os.environ.setdefault("FLOW_MODE", "lead")

PID_A = "PID_OWN_A"
PID_B = "PID_OWN_B"
ADMIN_USER = "ownadmin"
ADMIN_PASS = "ownpass"
JWT_SECRET = "owner-dash-jwt-secret-32chars!!"


@pytest.fixture
def own_env(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", ADMIN_USER)
    monkeypatch.setenv("DASHBOARD_PASSWORD", ADMIN_PASS)
    monkeypatch.setenv("DASHBOARD_JWT_SECRET", JWT_SECRET)


@pytest_asyncio.fixture
async def own_db(tmp_path, monkeypatch, own_env):
    url = f"sqlite+aiosqlite:///{tmp_path}/own.db"
    monkeypatch.setenv("DATABASE_URL", url)

    import app.db.engine as eng
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.db.models import Base
    from app.db.repo import sync_tenants_to_db, create_user, get_user_by_username
    from app.dashboard.users import hash_password
    from app.tenants import Tenant

    engine = create_async_engine(url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(eng, "DATABASE_URL", url)
    monkeypatch.setattr(eng, "DB_ENABLED", True)
    monkeypatch.setattr(eng, "engine", engine)
    monkeypatch.setattr(eng, "AsyncSessionLocal", factory)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    t_a = Tenant(
        phone_number_id=PID_A,
        name="Owner Biz A",
        flow_mode="lead",
        campaign_phrase="Alpha",
        demo_slots=["Mon 10am"],
        greeting_text="Custom hello from A",
    )
    t_b = Tenant(
        phone_number_id=PID_B,
        name="Owner Biz B",
        flow_mode="lead",
        campaign_phrase="Beta",
        demo_slots=["Tue 11am"],
    )

    async with eng.get_db() as db:
        await sync_tenants_to_db(db, [t_a, t_b])
        from sqlalchemy import select
        from app.db.models import DBTenant

        if not await get_user_by_username(db, ADMIN_USER):
            await create_user(
                db,
                username=ADMIN_USER,
                password_hash=hash_password(ADMIN_PASS),
                role="admin",
                tenant_id=None,
            )
        row_a = (
            await db.execute(select(DBTenant).where(DBTenant.phone_number_id == PID_A))
        ).scalar_one()
        row_b = (
            await db.execute(select(DBTenant).where(DBTenant.phone_number_id == PID_B))
        ).scalar_one()
        if not await get_user_by_username(db, "bizowner"):
            await create_user(
                db,
                username="bizowner",
                password_hash=hash_password("ownerpass"),
                role="owner",
                tenant_id=row_a.id,
            )

    yield {"tenant_a_id": row_a.id, "tenant_b_id": row_b.id, "pid_a": PID_A, "pid_b": PID_B}

    await engine.dispose()
    monkeypatch.setattr(eng, "DB_ENABLED", False)


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client, user, password):
    r = await client.post("/api/auth/login", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_owner_login_and_me(client, own_db):
    data = await _login(client, "bizowner", "ownerpass")
    assert data["role"] == "owner"
    assert data["tenant_id"] == own_db["tenant_a_id"]
    assert not data.get("readonly")

    r = await client.get("/api/dashboard/me", headers=_auth(data["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "owner"
    assert body["tenant"]["phone_number_id"] == PID_A
    assert body["tenant"]["name"] == "Owner Biz A"


@pytest.mark.asyncio
async def test_owner_sees_only_own_tenant_list(client, own_db):
    data = await _login(client, "bizowner", "ownerpass")
    r = await client.get("/api/dashboard/tenants", headers=_auth(data["access_token"]))
    assert r.status_code == 200
    body = r.json()
    items = body["items"] if isinstance(body, dict) else body
    assert len(items) == 1
    assert items[0]["id"] == own_db["tenant_a_id"]
    if isinstance(body, dict):
        assert body["counts"]["all"] == 1


@pytest.mark.asyncio
async def test_owner_cross_tenant_overview_403(client, own_db):
    data = await _login(client, "bizowner", "ownerpass")
    r = await client.get(
        f"/api/dashboard/overview?tenant_id={PID_B}",
        headers=_auth(data["access_token"]),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_owner_cross_tenant_config_403(client, own_db):
    data = await _login(client, "bizowner", "ownerpass")
    r = await client.get(
        f"/api/dashboard/tenants/{own_db['tenant_b_id']}/config",
        headers=_auth(data["access_token"]),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_owner_cannot_edit_wiring_fields(client, own_db):
    data = await _login(client, "bizowner", "ownerpass")
    tid = own_db["tenant_a_id"]
    r = await client.post(
        f"/api/dashboard/tenants/{tid}/config",
        headers=_auth(data["access_token"]),
        json={"business_wa_id": "9999999999", "greeting_text": "ok"},
    )
    assert r.status_code == 403
    assert "wiring" in r.json()["detail"].lower() or "business_wa_id" in r.json()["detail"]

    r2 = await client.post(
        f"/api/dashboard/tenants/{tid}/config",
        headers=_auth(data["access_token"]),
        json={"phone_number_id": "HACKED", "flow_mode": "order"},
    )
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_save_content(client, own_db):
    data = await _login(client, "bizowner", "ownerpass")
    tid = own_db["tenant_a_id"]
    r = await client.post(
        f"/api/dashboard/tenants/{tid}/config",
        headers=_auth(data["access_token"]),
        json={"greeting_text": "Assalam — naya greeting"},
    )
    assert r.status_code == 200, r.text
    assert "naya greeting" in r.json()["config"]["greeting_text"]
    assert "wiring" in r.json()
    assert r.json()["wiring"]["managed_by"] == "AccellionX"


@pytest.mark.asyncio
async def test_owner_cannot_hit_admin_endpoints(client, own_db):
    data = await _login(client, "bizowner", "ownerpass")
    h = _auth(data["access_token"])

    r = await client.get("/api/dashboard/users", headers=h)
    assert r.status_code == 403

    r = await client.post(
        "/api/dashboard/users",
        headers=h,
        json={"username": "x", "password": "y", "tenant_id": own_db["tenant_a_id"]},
    )
    assert r.status_code == 403

    r = await client.post(
        f"/api/dashboard/admin/view-as/{own_db['tenant_a_id']}",
        headers=h,
    )
    assert r.status_code == 403

    # Onboarding / tenant create typically admin-only
    r = await client.get("/api/dashboard/templates", headers=h)
    # templates may be readable — wizard create must not
    r = await client.post(
        "/api/dashboard/tenants",
        headers=h,
        json={
            "name": "Hacked",
            "phone_number_id": "PID_HACK",
            "flow_mode": "lead",
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_owner_billing_placeholder(client, own_db):
    data = await _login(client, "bizowner", "ownerpass")
    r = await client.get("/api/dashboard/billing", headers=_auth(data["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["placeholder"] is True
    assert body["tenant_id"] == own_db["tenant_a_id"]
    assert "messages_sent" in body["usage"]


@pytest.mark.asyncio
async def test_admin_create_owner_and_list(client, own_db):
    admin = await _login(client, ADMIN_USER, ADMIN_PASS)
    h = _auth(admin["access_token"])

    r = await client.post(
        "/api/dashboard/users",
        headers=h,
        json={
            "username": "newclient",
            "password": "pass12345",
            "tenant_id": own_db["tenant_b_id"],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "owner"

    r = await client.get("/api/dashboard/users", headers=h)
    assert r.status_code == 200
    names = {u["username"] for u in r.json()["items"]}
    assert "newclient" in names
    assert "bizowner" in names

    # New owner can login scoped to B
    owner = await _login(client, "newclient", "pass12345")
    assert owner["tenant_id"] == own_db["tenant_b_id"]
    r = await client.get(
        f"/api/dashboard/tenants/{own_db['tenant_a_id']}/config",
        headers=_auth(owner["access_token"]),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_view_as_support_mode_and_access_log(client, own_db):
    admin = await _login(client, ADMIN_USER, ADMIN_PASS)
    r = await client.post(
        f"/api/dashboard/admin/view-as/{own_db['tenant_a_id']}",
        headers=_auth(admin["access_token"]),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == "owner"
    assert body["readonly"] is False
    assert body.get("support_mode") is True
    assert body["impersonated_by"] == ADMIN_USER
    assert body["tenant_id"] == own_db["tenant_a_id"]

    h = _auth(body["access_token"])
    me = await client.get("/api/dashboard/me", headers=h)
    assert me.status_code == 200
    assert me.json()["impersonated_by"] == ADMIN_USER
    assert me.json()["readonly"] is False

    # Can read
    r = await client.get(
        f"/api/dashboard/tenants/{own_db['tenant_a_id']}/config",
        headers=h,
    )
    assert r.status_code == 200

    # Can mutate in support mode (audited)
    r = await client.post(
        f"/api/dashboard/tenants/{own_db['tenant_a_id']}/config",
        headers=h,
        json={"greeting_text": "support edit ok"},
    )
    assert r.status_code == 200, r.text

    # Cannot reach other tenant
    r = await client.get(
        f"/api/dashboard/tenants/{own_db['tenant_b_id']}/config",
        headers=h,
    )
    assert r.status_code == 403

    # View-as token cannot use admin endpoints
    r = await client.get("/api/dashboard/users", headers=h)
    assert r.status_code == 403
    r = await client.get("/api/dashboard/access-log", headers=h)
    assert r.status_code == 403

    log = await client.get(
        "/api/dashboard/access-log",
        headers=_auth(admin["access_token"]),
    )
    assert log.status_code == 200, log.text
    actions = [i["action"] for i in log.json()["items"]]
    assert "view_as_enter" in actions
    assert "config_save" in actions
    enter = next(i for i in log.json()["items"] if i["action"] == "view_as_enter")
    assert enter["admin_username"] == ADMIN_USER
    assert enter["tenant_id"] == own_db["tenant_a_id"]


@pytest.mark.asyncio
async def test_owner_cannot_see_access_log_or_platform_users(client, own_db):
    data = await _login(client, "bizowner", "ownerpass")
    h = _auth(data["access_token"])
    r = await client.get("/api/dashboard/access-log", headers=h)
    assert r.status_code == 403
    r = await client.get("/api/dashboard/users", headers=h)
    assert r.status_code == 403
    r = await client.get("/api/dashboard/tenants", headers=h)
    assert r.status_code == 200
    body = r.json()
    items = body["items"] if isinstance(body, dict) else body
    assert len(items) == 1
    assert items[0]["id"] == own_db["tenant_a_id"]


@pytest.mark.asyncio
async def test_owner_mute_scoped(client, own_db):
    from app.tenants import Tenant
    import app.tenants as tenants_mod

    # Register tenants for MuteStore
    tenants_mod._registry[PID_A] = Tenant(
        phone_number_id=PID_A, name="A", flow_mode="lead"
    )
    tenants_mod._registry[PID_B] = Tenant(
        phone_number_id=PID_B, name="B", flow_mode="lead"
    )

    data = await _login(client, "bizowner", "ownerpass")
    h = _auth(data["access_token"])

    r = await client.post(
        "/api/dashboard/mutes",
        headers=h,
        json={"tenant_id": PID_A, "wa_id": "923001111111", "mute": True, "duration_s": 3600},
    )
    assert r.status_code == 200, r.text

    r = await client.post(
        "/api/dashboard/mutes",
        headers=h,
        json={"tenant_id": PID_B, "wa_id": "923002222222", "mute": True, "duration_s": 3600},
    )
    assert r.status_code == 403
