"""menu_v2 limits, cart math, draft/publish, shared payload builders."""

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

from app.menu_v2 import (
    BUTTONS_MAX,
    ITEM_NAME_MAX,
    MORE_ROW_TITLE,
    ROWS_MAX,
    MenuV2Error,
    build_greeting_and_entry,
    build_item_list_payload,
    build_modifier_buttons_payload,
    cart_grand_total,
    empty_menu_v2,
    format_cart_summary,
    line_total,
    preview_flow_steps,
    validate_menu_v2,
)


def _sample_menu(n_items: int = 3, with_mod: bool = False) -> dict:
    m = empty_menu_v2()
    m["categories"] = [{"id": "cat1", "name": "Burgers", "sort": 0, "visible": True}]
    items = []
    for i in range(n_items):
        it = {
            "id": f"item{i}",
            "category_id": "cat1",
            "name": f"Item {i}",
            "description": f"Desc {i}",
            "price": 100 + i,
            "available": True,
            "sort": i,
            "modifiers": [],
        }
        if with_mod and i == 0:
            it["modifiers"] = [{
                "id": "mod1",
                "name": "Size",
                "options": [
                    {"id": "o1", "label": "Regular", "price_delta": 0},
                    {"id": "o2", "label": "Large", "price_delta": 100},
                ],
            }]
        items.append(it)
    m["items"] = items
    return validate_menu_v2(m)


def test_rejects_name_over_24_chars():
    m = empty_menu_v2()
    m["categories"] = [{"id": "c1", "name": "A" * 25, "sort": 0, "visible": True}]
    with pytest.raises(MenuV2Error, match="max 24"):
        validate_menu_v2(m)


def test_rejects_item_name_over_24():
    m = empty_menu_v2()
    m["categories"] = [{"id": "c1", "name": "Cat", "sort": 0, "visible": True}]
    m["items"] = [{
        "id": "i1", "category_id": "c1", "name": "X" * (ITEM_NAME_MAX + 1),
        "description": "", "price": 10, "available": True, "sort": 0, "modifiers": [],
    }]
    with pytest.raises(MenuV2Error, match="max 24"):
        validate_menu_v2(m)


def test_rejects_fourth_modifier_option():
    m = empty_menu_v2()
    m["categories"] = [{"id": "c1", "name": "Cat", "sort": 0, "visible": True}]
    m["items"] = [{
        "id": "i1", "category_id": "c1", "name": "Burger", "description": "",
        "price": 100, "available": True, "sort": 0,
        "modifiers": [{
            "id": "m1", "name": "Size",
            "options": [
                {"id": f"o{i}", "label": f"Opt{i}", "price_delta": 0}
                for i in range(4)
            ],
        }],
    }]
    with pytest.raises(MenuV2Error, match="max 3"):
        validate_menu_v2(m)


def test_pagination_11th_row_uses_more():
    menu = _sample_menu(n_items=11)
    payload = build_item_list_payload("92300", menu, category_id="cat1", page=0)
    rows = payload["interactive"]["action"]["sections"][0]["rows"]
    assert len(rows) == ROWS_MAX
    assert rows[-1]["title"] == MORE_ROW_TITLE
    assert rows[-1]["id"].startswith("menu:more")
    # page 1 should have remaining 2 items (11 - 9)
    payload2 = build_item_list_payload("92300", menu, category_id="cat1", page=1)
    rows2 = payload2["interactive"]["action"]["sections"][0]["rows"]
    assert len(rows2) == 2
    assert not rows2[-1]["id"].startswith("menu:more")


def test_exactly_10_items_no_more_row():
    menu = _sample_menu(n_items=10)
    payload = build_item_list_payload("92300", menu, category_id="cat1", page=0)
    rows = payload["interactive"]["action"]["sections"][0]["rows"]
    assert len(rows) == 10
    assert rows[-1]["title"] != MORE_ROW_TITLE


def test_modifier_price_math():
    menu = _sample_menu(n_items=1, with_mod=True)
    lines = [{
        "item_id": "item0",
        "name": "Item 0",
        "qty": 2,
        "unit_price": 100,
        "price_delta": 100,
        "modifier_label": "Large",
    }]
    assert line_total(lines[0]) == 400  # (100+100)*2
    menu["settings"]["delivery"] = {"enabled": True, "charge": 50, "free_above": 0, "area_note": ""}
    assert cart_grand_total(menu, lines) == 450
    menu["settings"]["delivery"]["free_above"] = 400
    assert cart_grand_total(menu, lines) == 400  # free delivery
    summary = format_cart_summary(menu, lines)
    assert "Large" in summary
    assert "Total" in summary


def test_modifier_buttons_max_3():
    menu = _sample_menu(n_items=1, with_mod=True)
    item = menu["items"][0]
    payload = build_modifier_buttons_payload("92300", item)
    assert payload is not None
    btns = payload["interactive"]["action"]["buttons"]
    assert len(btns) <= BUTTONS_MAX


def test_preview_payload_equals_runtime_entry():
    menu = _sample_menu(n_items=3, with_mod=True)
    runtime = build_greeting_and_entry("preview", menu)
    steps = preview_flow_steps(menu, to="preview")
    # First two steps match entry payloads
    assert steps[0]["payload"] == runtime[0]
    assert steps[1]["payload"] == runtime[1]


# ── API draft vs publish ──────────────────────────────────────────────────────

PID = "PID_MENU_V2"
ADMIN_USER = "menuadmin"
ADMIN_PASS = "menupass"
JWT_SECRET = "menu-jwt-secret-key"


@pytest.fixture
def menu_env(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", ADMIN_USER)
    monkeypatch.setenv("DASHBOARD_PASSWORD", ADMIN_PASS)
    monkeypatch.setenv("DASHBOARD_JWT_SECRET", JWT_SECRET)


@pytest_asyncio.fixture
async def menu_db(tmp_path, monkeypatch, menu_env):
    url = f"sqlite+aiosqlite:///{tmp_path}/menu.db"
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

    # Seed legacy menu so order tenant validates
    legacy = {
        "shop_name": "Test Shop",
        "delivery_fee": 50,
        "delivery_area": "Lahore",
        "categories": [{"name": "Burgers", "items": [{"name": "Zinger", "price": 450}]}],
    }
    t = Tenant(
        phone_number_id=PID, name="Order Shop", flow_mode="order",
        menu=legacy, owner_whatsapp="923001111111",
    )
    async with eng.get_db() as db:
        await sync_tenants_to_db(db, [t])
        if not await get_user_by_username(db, ADMIN_USER):
            await create_user(
                db, username=ADMIN_USER,
                password_hash=hash_password(ADMIN_PASS),
                role="admin", tenant_id=None,
            )
        from sqlalchemy import select
        from app.db.models import DBTenant
        row = (await db.execute(select(DBTenant).where(DBTenant.phone_number_id == PID))).scalar_one()
        tenant_db_id = row.id

    yield {"tenant_db_id": tenant_db_id, "engine": engine}

    await engine.dispose()
    monkeypatch.setattr(eng, "DB_ENABLED", False)
    monkeypatch.setattr(eng, "engine", None)
    monkeypatch.setattr(eng, "AsyncSessionLocal", None)


async def _login(client: AsyncClient) -> str:
    r = await client.post("/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_draft_vs_published_isolation(menu_db, menu_env):
    from app.main import app

    tid = menu_db["tenant_db_id"]
    draft = _sample_menu(n_items=2, with_mod=True)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}

        # Save draft only
        r = await client.post(
            f"/api/dashboard/tenants/{tid}/config",
            headers=headers,
            json={"menu_v2_draft": draft},
        )
        assert r.status_code == 200, r.text
        cfg = r.json()["config"]
        assert cfg["menu_v2_draft"]["items"][0]["name"] == "Item 0"
        assert cfg.get("menu_v2") in (None, {}) or cfg.get("menu_v2") != draft

        # Published still absent / not equal to draft until publish
        published_before = cfg.get("menu_v2")

        r = await client.post(f"/api/dashboard/tenants/{tid}/menu/publish", headers=headers)
        assert r.status_code == 200, r.text
        cfg2 = r.json()["config"]
        assert cfg2["menu_v2"]["items"][0]["name"] == "Item 0"
        assert cfg2["menu_v2_draft"]["items"][0]["name"] == "Item 0"
        assert published_before != cfg2["menu_v2"] or published_before is None

        # Reject over-limit via API
        bad = _sample_menu(1)
        bad["items"][0]["name"] = "N" * 25
        r = await client.post(
            f"/api/dashboard/tenants/{tid}/config",
            headers=headers,
            json={"menu_v2_draft": bad},
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_live_publish_after_cache_ttl(menu_db, menu_env, monkeypatch):
    from app.main import app
    from app.tenant_resolver import CACHE_TTL_S, invalidate_all, resolve_tenant

    tid = menu_db["tenant_db_id"]
    draft = _sample_menu(n_items=1)
    draft["items"][0]["name"] = "LiveBurger"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        await client.post(
            f"/api/dashboard/tenants/{tid}/config",
            headers=headers,
            json={"menu_v2_draft": draft},
        )
        await client.post(f"/api/dashboard/tenants/{tid}/menu/publish", headers=headers)

    monkeypatch.setattr("app.tenant_resolver.CACHE_TTL_S", 0)
    invalidate_all()
    t = await resolve_tenant(PID)
    assert t is not None
    assert t.menu_v2 is not None
    assert t.menu_v2["items"][0]["name"] == "LiveBurger"
    # restore
    monkeypatch.setattr("app.tenant_resolver.CACHE_TTL_S", CACHE_TTL_S)


@pytest.mark.asyncio
async def test_preview_endpoint_uses_same_builder(menu_db, menu_env):
    from app.main import app

    tid = menu_db["tenant_db_id"]
    draft = _sample_menu(n_items=2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _login(client)
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            f"/api/dashboard/tenants/{tid}/menu/preview",
            headers=headers,
            json={"menu_v2_draft": draft},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        expected = build_greeting_and_entry("preview", draft)
        assert data["steps"][0]["payload"] == expected[0]
        assert data["steps"][1]["payload"] == expected[1]


def test_parent_id_hierarchy_browse():
    from app.menu_v2 import (
        build_browse_payload,
        child_categories,
        root_categories,
        validate_menu_v2,
        MenuV2Error,
    )
    raw = {
        "categories": [
            {"id": "r1", "name": "Men", "sort": 0, "visible": True},
            {"id": "s1", "name": "Sneakers", "sort": 0, "visible": True, "parent_id": "r1"},
            {"id": "s2", "name": "Formal", "sort": 1, "visible": True, "parent_id": "r1"},
        ],
        "items": [
            {
                "id": "i1",
                "category_id": "s1",
                "name": "Shoe A",
                "description": "",
                "price": 100,
                "available": True,
                "sort": 0,
                "modifiers": [],
            },
        ],
        "settings": empty_menu_v2()["settings"],
    }
    m = validate_menu_v2(raw)
    assert len(root_categories(m)) == 1
    assert len(child_categories(m, "r1")) == 2
    rows = build_browse_payload("1", m, "r1")["interactive"]["action"]["sections"][0]["rows"]
    assert rows[0]["id"] == "cat:s1"
    rows2 = build_browse_payload("1", m, "s1")["interactive"]["action"]["sections"][0]["rows"]
    assert rows2[0]["id"].startswith("item:")
    bad = {
        **raw,
        "categories": raw["categories"]
        + [{"id": "x", "name": "TooDeep", "sort": 0, "visible": True, "parent_id": "s1"}],
    }
    with pytest.raises(MenuV2Error, match="depth"):
        validate_menu_v2(bad)


def test_order_templates_have_subcategories():
    import json
    from pathlib import Path
    from app.menu_v2 import validate_menu_v2, root_categories, child_categories
    for path in Path("app/templates").glob("*.json"):
        data = json.loads(path.read_text())
        if data.get("flow_mode") != "order":
            continue
        m = validate_menu_v2(data["config"]["menu_v2"])
        roots = root_categories(m)
        assert roots, data["id"]
        for r in roots:
            assert child_categories(m, r["id"]), f"{data['id']} root {r['name']} needs subs"
