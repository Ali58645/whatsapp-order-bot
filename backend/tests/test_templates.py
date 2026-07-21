"""
Vertical starter templates — schema validation + apply-template draft semantics.
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

ADMIN_USER = "tpladmin"
ADMIN_PASS = "tplpass"
JWT_SECRET = "tpl-jwt-secret-key-32chars-long!"
PID_SEED = "PID_TPL_SEED"


@pytest.fixture
def tpl_env(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", ADMIN_USER)
    monkeypatch.setenv("DASHBOARD_PASSWORD", ADMIN_PASS)
    monkeypatch.setenv("DASHBOARD_JWT_SECRET", JWT_SECRET)


@pytest_asyncio.fixture
async def tpl_db(tmp_path, monkeypatch, tpl_env):
    url = f"sqlite+aiosqlite:///{tmp_path}/tpl.db"
    monkeypatch.setenv("DATABASE_URL", url)

    import app.db.engine as eng
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.dashboard.users import hash_password
    from app.db.models import Base
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
        name="Seed Cafe",
        flow_mode="order",
        campaign_phrase="Hello",
        demo_slots=["Kal 11am", "Kal 4pm"],
        status="live",
        menu={
            "shop_name": "Seed Cafe",
            "delivery_fee": 100,
            "delivery_area": "",
            "categories": [{"name": "Items", "items": [{"name": "Old Item", "price": 99}]}],
        },
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
        from sqlalchemy import select
        from app.db.models import DBTenant

        row = (
            await db.execute(select(DBTenant).where(DBTenant.phone_number_id == PID_SEED))
        ).scalar_one()
        # Published messages distinct from draft
        cfg = dict(row.config or {})
        cfg["messages"] = {
            "lead": {"greeting_line": "PUBLISHED GREETING"},
            "order": {"greeting": "PUBLISHED ORDER GREETING"},
            "interactive": (cfg.get("messages") or {}).get("interactive") or {},
        }
        cfg["messages_draft"] = {
            "lead": {"greeting_line": "DRAFT GREETING"},
            "order": {"greeting": "DRAFT ORDER GREETING"},
            "interactive": cfg["messages"].get("interactive") or {},
        }
        cfg["menu_v2"] = {
            "categories": [{"id": "c_old", "name": "Old Cat", "sort": 0, "visible": True}],
            "items": [
                {
                    "id": "i_old",
                    "category_id": "c_old",
                    "name": "Old Item",
                    "description": "",
                    "price": 99,
                    "available": True,
                    "sort": 0,
                    "modifiers": [],
                }
            ],
            "settings": {
                "greeting_text": "PUBLISHED MENU",
                "menu_button_label": "Menu",
                "delivery": {"enabled": True, "charge": 1, "free_above": 0, "area_note": ""},
                "order_confirm_note": "OK?",
                "currency": "PKR",
            },
        }
        cfg["menu_v2_draft"] = None
        row.config = cfg

    invalidate_all()
    yield {"tenant_id": row.id, "phone": PID_SEED}
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


async def _token(client: AsyncClient) -> str:
    r = await client.post(
        "/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_every_template_validates():
    from app.templates import list_templates, validate_all_templates

    items = list_templates()
    assert len(items) >= 22
    ids = {i["id"] for i in items}
    for required in (
        "restaurant",
        "grocery_kiryana",
        "water_supplier",
        "pharmacy",
        "bakery",
        "clothing_retail",
        "salon_booking",
        "pos_lead",
        "generic_order",
        "generic_lead",
        "hardware_store",
        "mobile_accessories",
        "electronics_appliances",
        "meat_poultry",
        "fruits_vegetables",
        "dairy_milk",
        "gym_fitness",
        "clinic_doctor",
        "auto_workshop",
        "education_tuition",
        "real_estate",
        "beauty_cosmetics",
        "flower_gifts",
    ):
        assert required in ids, required

    results = validate_all_templates()
    bad = {k: v for k, v in results.items() if v}
    assert not bad, bad


@pytest.mark.asyncio
async def test_list_templates_api(client, tpl_db):
    token = await _token(client)
    r = await client.get(
        "/api/dashboard/templates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 22
    r2 = await client.get(
        "/api/dashboard/templates?flow_mode=order",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert all(i["flow_mode"] == "order" for i in r2.json()["items"])


@pytest.mark.asyncio
async def test_apply_template_requires_confirm(client, tpl_db):
    token = await _token(client)
    tid = tpl_db["tenant_id"]
    r = await client.post(
        f"/api/dashboard/tenants/{tid}/apply-template",
        headers={"Authorization": f"Bearer {token}"},
        json={"template_id": "restaurant", "confirm": False},
    )
    assert r.status_code == 400
    assert "confirm" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_apply_template_populates_draft_not_published(client, tpl_db):
    token = await _token(client)
    tid = tpl_db["tenant_id"]
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        f"/api/dashboard/tenants/{tid}/apply-template",
        headers=headers,
        json={"template_id": "restaurant", "confirm": True, "go_live": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["go_live"] is False

    cfg = await client.get(f"/api/dashboard/tenants/{tid}/config", headers=headers)
    assert cfg.status_code == 200
    body = cfg.json()["config"]
    # Published untouched when go_live=false
    assert body["messages"]["order"]["greeting"] == "PUBLISHED ORDER GREETING"
    assert body["menu_v2"]["settings"]["greeting_text"] == "PUBLISHED MENU"
    # Draft populated from restaurant template
    assert "menu_v2_draft" in body and body["menu_v2_draft"]["items"]
    assert any(i["name"] == "Chicken Biryani" for i in body["menu_v2_draft"]["items"])
    draft_greet = (body.get("messages_draft") or {}).get("order", {}).get("greeting", "")
    assert "khush aamdeed" in draft_greet.lower() or "Assalam" in draft_greet


@pytest.mark.asyncio
async def test_wizard_template_produces_routable_tenant(client, tpl_db):
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post(
        "/api/dashboard/onboarding/draft",
        headers=headers,
        json={
            "name": "Karachi BBQ",
            "flow_mode": "order",
            "phone_number_id": "PID_TPL_BBQ",
            "owner_whatsapp": "923001112233",
            "template_id": "restaurant",
            "connection_verified": True,
            "subscribed_apps": True,
        },
    )
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    with patch("app.main.send_whatsapp_message", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        act = await client.post(
            f"/api/dashboard/onboarding/{tid}/activate",
            headers=headers,
            json={"send_test": True},
        )
        assert act.status_code == 200, act.text

    from app.tenant_resolver import resolve_tenant

    t = await resolve_tenant("PID_TPL_BBQ")
    assert t is not None
    assert t.is_live
    assert t.menu_v2 and len(t.menu_v2.get("items") or []) >= 5
