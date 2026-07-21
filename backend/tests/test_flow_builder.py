"""
DB-driven lead flow — default migration, validation, runtime walk, preview parity.
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

PID = "PID_FLOW_BLD"
ADMIN_USER = "flowadmin"
ADMIN_PASS = "flowpass"
JWT_SECRET = "flow-builder-jwt-secret-32ch!!"


def test_default_flow_keys_match_classic_phases():
    from app.flow import default_bahi_pos_flow, flows_equal_default
    from app.lead import PHASES

    flow = default_bahi_pos_flow()
    keys = [s["key"] for s in flow]
    # PHASES includes GREETING…CONFIRMED — same order
    assert keys == PHASES
    assert flows_equal_default(flow)


def test_validate_rejects_deleted_reserved_and_bad_capture():
    from app.flow import FlowError, default_bahi_pos_flow, validate_flow

    flow = default_bahi_pos_flow()
    # Remove SCHEDULING — now allowed (optional booking step)
    trimmed = [s for s in flow if s["key"] != "SCHEDULING"]
    assert validate_flow(trimmed)
    assert "SCHEDULING" not in [s["key"] for s in trimmed]

    # Cannot remove GREETING
    no_greet = [s for s in flow if s["key"] != "GREETING"]
    with pytest.raises(FlowError, match="GREETING"):
        validate_flow(no_greet)

    flow2 = default_bahi_pos_flow()
    flow2[1]["capture_field"] = "not_a_field!!"
    with pytest.raises(FlowError, match="capture_field"):
        validate_flow(flow2)


def test_whatsapp_limits_on_options():
    from app.flow import FlowError, default_bahi_pos_flow, validate_flow

    flow = default_bahi_pos_flow()
    # Inject 11 rows on locations (max 10)
    loc = next(s for s in flow if s["key"] == "LOCATIONS")
    loc["options_key"] = None
    loc["options"] = [
        {"id": f"x{i}", "title": f"Opt{i}"} for i in range(11)
    ]
    with pytest.raises(FlowError, match="max 10"):
        validate_flow(flow)

    flow = default_bahi_pos_flow()
    btype = next(s for s in flow if s["key"] == "BUSINESS_TYPE")
    btype["options_key"] = None
    btype["options"] = [
        {"id": "x", "title": "x" * 51}
    ]
    with pytest.raises(FlowError, match="max 50"):
        validate_flow(flow)


def test_preview_builder_matches_runtime_interactive():
    from app.flow import (
        build_step_interactive,
        default_bahi_pos_flow,
        find_step,
        preview_flow_messages,
    )
    from app.lead import get_phase_interactive

    flow = default_bahi_pos_flow()
    meta = {"_slot_1": "Kal 11am", "_slot_2": "Kal 4pm"}
    preview = preview_flow_messages(flow, lang="ur", demo_slots=["Kal 11am", "Kal 4pm"])

    for phase in ("BUSINESS_TYPE", "LOCATIONS", "CURRENT_SYSTEM", "SCHEDULING"):
        step = find_step(flow, phase)
        runtime = get_phase_interactive(phase, "92300111", "ur", meta=meta)
        via_flow = build_step_interactive(step, "92300111", "ur", meta=meta)
        assert runtime == via_flow
        prev = next(p for p in preview if p["key"] == phase)
        assert prev["interactive"] is not None
        # Same interactive type
        assert prev["interactive"]["interactive"]["type"] == runtime["interactive"]["type"]


def test_next_phase_after_reorder():
    from app.flow import default_bahi_pos_flow, next_phase_key
    from app.tenants import Tenant

    flow = default_bahi_pos_flow()
    # Swap LOCATIONS and CURRENT_SYSTEM
    idx_l = next(i for i, s in enumerate(flow) if s["key"] == "LOCATIONS")
    idx_c = next(i for i, s in enumerate(flow) if s["key"] == "CURRENT_SYSTEM")
    flow[idx_l], flow[idx_c] = flow[idx_c], flow[idx_l]

    t = Tenant(
        phone_number_id="x", name="T", flow_mode="lead",
        campaign_phrase="Bahi POS", demo_slots=["A", "B"],
    )
    t._raw_config = {"flow": flow}

    assert next_phase_key(t, "BUSINESS_TYPE") == "CURRENT_SYSTEM"
    assert next_phase_key(t, "CURRENT_SYSTEM") == "LOCATIONS"
    assert next_phase_key(t, "LOCATIONS") == "SCHEDULING"


def test_apply_interactive_follows_custom_flow():
    from app.flow import apply_flow_interactive_answer, default_bahi_pos_flow
    from app.tenants import Tenant

    flow = default_bahi_pos_flow()
    # Insert custom free_text between BUSINESS_NAME and BUSINESS_TYPE
    insert = {
        "id": "step_city",
        "key": "CITY_Q",
        "type": "button_options",
        "question_text": "Kaunsa city?",
        "options": [
            {"id": "c_khi", "title": "Karachi", "value": "Karachi"},
            {"id": "c_lhr", "title": "Lahore", "value": "Lahore"},
        ],
        "capture_field": "custom_1",
        "required": True,
        "skip_if_declined": False,
        "reserved": False,
        "system": False,
    }
    # After BUSINESS_NAME
    idx = next(i for i, s in enumerate(flow) if s["key"] == "BUSINESS_NAME")
    flow.insert(idx + 1, insert)
    # BUSINESS_NAME next should be CITY_Q — update isn't automatic; next_phase uses order

    t = Tenant(
        phone_number_id="x", name="T", flow_mode="lead",
        campaign_phrase="Bahi", demo_slots=["A", "B"],
    )
    t._raw_config = {"flow": flow}

    from app.flow import next_phase_key
    assert next_phase_key(t, "BUSINESS_NAME") == "CITY_Q"

    meta = {"phase": "CITY_Q", "lang": "ur"}
    ok, _ = apply_flow_interactive_answer(meta, "c_khi", "Karachi", tenant=t)
    assert ok
    assert meta["custom_1"] == "Karachi"
    assert meta["phase"] == "BUSINESS_TYPE"


def test_sheet_fields_include_custom():
    from app.flow import sheet_fields_from_meta

    fields = sheet_fields_from_meta({
        "business_name": "Shop",
        "custom_1": "Karachi",
        "locations": "2-5",
    })
    assert fields["business_name"] == "Shop"
    assert "custom_1=Karachi" in fields["notes"]
    assert "locations=2-5" in fields["notes"]


def test_handle_business_name_advances_via_flow():
    from app.lead import handle_business_name
    from app.flow import default_bahi_pos_flow
    from app.tenants import Tenant

    t = Tenant(
        phone_number_id="x", name="T", flow_mode="lead",
        campaign_phrase="Bahi", demo_slots=["A", "B"],
    )
    t._raw_config = {"flow": default_bahi_pos_flow()}
    meta = {"phase": "BUSINESS_NAME", "lang": "ur"}
    text, ok = handle_business_name(meta, "My Shop", lang="ur", tenant=t)
    assert ok
    assert meta["phase"] == "BUSINESS_TYPE"
    assert meta["business_name"] == "My Shop"
    assert "My Shop" in text or text  # ack


# ── API / persistence ────────────────────────────────────────────────────────

@pytest.fixture
def flow_env(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", ADMIN_USER)
    monkeypatch.setenv("DASHBOARD_PASSWORD", ADMIN_PASS)
    monkeypatch.setenv("DASHBOARD_JWT_SECRET", JWT_SECRET)


@pytest_asyncio.fixture
async def flow_db(tmp_path, monkeypatch, flow_env):
    url = f"sqlite+aiosqlite:///{tmp_path}/flow.db"
    monkeypatch.setenv("DATABASE_URL", url)

    import app.db.engine as eng
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.db.models import Base
    from app.db.repo import sync_tenants_to_db, create_user, get_user_by_username
    from app.dashboard.users import hash_password
    from app.tenants import Tenant
    from app.tenant_resolver import invalidate_all

    engine = create_async_engine(url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    # Direct assign — monkeypatch.setattr would restore DB_ENABLED=True after our cleanup
    prev = (eng.DATABASE_URL, eng.DB_ENABLED, eng.engine, eng.AsyncSessionLocal)
    eng.DATABASE_URL = url
    eng.DB_ENABLED = True
    eng.engine = engine
    eng.AsyncSessionLocal = factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    t = Tenant(
        phone_number_id=PID, name="Flow Biz", flow_mode="lead",
        campaign_phrase="Bahi POS", demo_slots=["Kal 11am", "Kal 4pm"],
    )
    async with eng.get_db() as db:
        await sync_tenants_to_db(db, [t])
        from sqlalchemy import select
        from app.db.models import DBTenant
        if not await get_user_by_username(db, ADMIN_USER):
            await create_user(
                db, username=ADMIN_USER, password_hash=hash_password(ADMIN_PASS),
                role="admin", tenant_id=None,
            )
        row = (
            await db.execute(select(DBTenant).where(DBTenant.phone_number_id == PID))
        ).scalar_one()

    invalidate_all()
    yield {"tenant_id": row.id}

    invalidate_all()
    await engine.dispose()
    eng.DATABASE_URL, eng.DB_ENABLED, eng.engine, eng.AsyncSessionLocal = prev
    invalidate_all()


@pytest.fixture(autouse=True)
def _flow_builder_no_db_leak():
    yield
    import app.db.engine as eng
    from app.tenant_resolver import invalidate_all
    # If a prior fixture left sqlite routing on, force registry fallback for webhook tests
    if eng.DB_ENABLED and str(eng.DATABASE_URL or "").startswith("sqlite"):
        eng.DB_ENABLED = False
        eng.engine = None
        eng.AsyncSessionLocal = None
        eng.DATABASE_URL = ""
        invalidate_all()


@pytest_asyncio.fixture
async def client():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client):
    r = await client.post(
        "/api/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_config_returns_default_flow_and_preview(client, flow_db):
    from app.flow import default_bahi_pos_flow, flows_equal_default

    token = await _login(client)
    h = {"Authorization": f"Bearer {token}"}
    tid = flow_db["tenant_id"]

    r = await client.get(f"/api/dashboard/tenants/{tid}/config", headers=h)
    assert r.status_code == 200
    flow = r.json()["config"]["flow"]
    assert flows_equal_default(flow)

    r = await client.post(
        f"/api/dashboard/tenants/{tid}/flow/preview",
        headers=h,
        json={},
    )
    assert r.status_code == 200, r.text
    keys = [s["key"] for s in r.json()["steps"]]
    assert keys == [s["key"] for s in default_bahi_pos_flow()]


@pytest.mark.asyncio
async def test_save_reordered_flow_and_delete_step(client, flow_db):
    from app.flow import default_bahi_pos_flow

    token = await _login(client)
    h = {"Authorization": f"Bearer {token}"}
    tid = flow_db["tenant_id"]

    flow = default_bahi_pos_flow()
    # Delete LOCATIONS (not reserved)
    flow = [s for s in flow if s["key"] != "LOCATIONS"]
    # Reorder: CURRENT_SYSTEM before BUSINESS_TYPE
    keys_order = ["GREETING", "BUSINESS_NAME", "CURRENT_SYSTEM", "BUSINESS_TYPE", "SCHEDULING", "CONFIRMED"]
    by_key = {s["key"]: s for s in flow}
    flow = [by_key[k] for k in keys_order]

    r = await client.post(
        f"/api/dashboard/tenants/{tid}/config",
        headers=h,
        json={"flow": flow},
    )
    assert r.status_code == 200, r.text
    saved = r.json()["config"]["flow"]
    assert [s["key"] for s in saved] == keys_order
    assert not any(s["key"] == "LOCATIONS" for s in saved)

    # Can delete SCHEDULING (optional)
    no_sched = [s for s in saved if s["key"] != "SCHEDULING"]
    r = await client.post(
        f"/api/dashboard/tenants/{tid}/config",
        headers=h,
        json={"flow": no_sched},
    )
    assert r.status_code == 200, r.text
    assert not any(s["key"] == "SCHEDULING" for s in r.json()["config"]["flow"])

    # Cannot delete GREETING
    bad = [s for s in no_sched if s["key"] != "GREETING"]
    r = await client.post(
        f"/api/dashboard/tenants/{tid}/config",
        headers=h,
        json={"flow": bad},
    )
    assert r.status_code == 400


def test_flow_step_label_preserved():
    from app.flow import default_bahi_pos_flow, validate_flow

    flow = default_bahi_pos_flow()
    bt = next(s for s in flow if s["key"] == "BUSINESS_TYPE")
    bt["label"] = "Service type"
    cleaned = validate_flow(flow)
    assert next(s for s in cleaned if s["key"] == "BUSINESS_TYPE")["label"] == "Service type"


@pytest.mark.asyncio
async def test_add_custom_step_reflected_in_live_advance(client, flow_db):
    """Saved custom step becomes next phase after business name."""
    from app.flow import default_bahi_pos_flow, next_phase_key
    from app.tenants import Tenant
    from app.db.repo import get_tenant_row
    import app.db.engine as eng

    token = await _login(client)
    h = {"Authorization": f"Bearer {token}"}
    tid = flow_db["tenant_id"]

    flow = default_bahi_pos_flow()
    custom = {
        "id": "step_extra",
        "key": "EXTRA_Q",
        "type": "free_text_capture",
        "question_text": "Aapka city?",
        "options": [],
        "capture_field": "custom_1",
        "required": True,
        "skip_if_declined": False,
        "reserved": False,
        "system": False,
    }
    idx = next(i for i, s in enumerate(flow) if s["key"] == "BUSINESS_NAME")
    flow.insert(idx + 1, custom)

    r = await client.post(
        f"/api/dashboard/tenants/{tid}/config",
        headers=h,
        json={"flow": flow},
    )
    assert r.status_code == 200, r.text

    async with eng.get_db() as db:
        row = await get_tenant_row(db, tid)
    tenant = Tenant.from_db_row(row)
    assert next_phase_key(tenant, "BUSINESS_NAME") == "EXTRA_Q"

    from app.lead import handle_business_name
    meta = {"phase": "BUSINESS_NAME", "lang": "ur"}
    _, ok = handle_business_name(meta, "Shop X", lang="ur", tenant=tenant)
    assert ok
    assert meta["phase"] == "EXTRA_Q"


def test_dashboard_extra_text_question_types_are_recognized():
    """Extra questions saved as text_question or free_text_capture both count."""
    from app.main import _is_free_text_flow_step

    assert _is_free_text_flow_step(
        {"type": "text_question", "capture_field": "custom_1", "key": "EXTRA_1"}
    )
    assert _is_free_text_flow_step(
        {"type": "free_text_capture", "capture_field": "custom_1", "key": "EXTRA_1"}
    )
    assert not _is_free_text_flow_step(
        {"type": "text_question", "capture_field": "business_name", "key": "BUSINESS_NAME"}
    )
    assert not _is_free_text_flow_step(
        {"type": "list_options", "capture_field": "custom_1", "key": "EXTRA_BTNS"}
    )


@pytest.mark.asyncio
async def test_advance_to_extra_sends_question_text(monkeypatch):
    """When next phase is an Extra text question, WhatsApp must receive the body."""
    from app.flow import default_bahi_pos_flow
    from app.tenants import Tenant
    import app.main as main

    flow = default_bahi_pos_flow()
    flow.insert(
        next(i for i, s in enumerate(flow) if s["key"] == "BUSINESS_NAME") + 1,
        {
            "id": "step_tools",
            "key": "EXTRA_TOOLS",
            "type": "text_question",
            "question_text": "Which software/tools do you currently use?",
            "options": [],
            "capture_field": "custom_1",
            "required": True,
            "reserved": False,
            "system": False,
        },
    )
    tenant = Tenant(
        phone_number_id="x",
        name="T",
        flow_mode="lead",
        campaign_phrase="Bahi",
        demo_slots=["A", "B"],
    )
    tenant._raw_config = {"flow": flow}

    sent: list[str] = []

    async def fake_send(to, text=None, interactive_payload=None, tenant=None):
        if text:
            sent.append(text)
        return {"messages": [{"id": "wamid.x"}]}

    monkeypatch.setattr(main, "send_whatsapp_message", fake_send)

    meta = {"phase": "EXTRA_TOOLS", "lang": "en"}
    ok = await main._maybe_send_interactive("92001", meta, tenant)
    assert ok is True
    assert sent and "software/tools" in sent[0].lower()


def test_llm_advance_does_not_skip_extra_after_current_system():
    """Classic PHASES jump used to skip Extra questions between CURRENT_SYSTEM and SCHEDULING."""
    from app.flow import default_bahi_pos_flow
    from app.lead import _advance_phase
    from app.tenants import Tenant

    flow = default_bahi_pos_flow()
    sys_i = next(i for i, s in enumerate(flow) if s["key"] == "CURRENT_SYSTEM")
    flow.insert(
        sys_i + 1,
        {
            "id": "step_tools",
            "key": "EXTRA_TOOLS",
            "type": "free_text_capture",
            "question_text": "Which tools?",
            "options": [],
            "capture_field": "custom_1",
            "required": True,
            "reserved": False,
            "system": False,
        },
    )
    tenant = Tenant(
        phone_number_id="x",
        name="T",
        flow_mode="lead",
        campaign_phrase="Bahi",
        demo_slots=["A", "B"],
    )
    tenant._raw_config = {"flow": flow}

    meta = {"phase": "CURRENT_SYSTEM", "lang": "en"}
    # Claude says "slot" — old code jumped to SCHEDULING via PHASES index
    _advance_phase(meta, "we will confirm a slot with you", "ok", tenant=tenant)
    assert meta["phase"] == "EXTRA_TOOLS"


def test_niche_branch_option_next_key():
    """Selecting Assisted living jumps to niche questions, then merges to SCHEDULING."""
    from app.flow import (
        apply_flow_interactive_answer,
        default_bahi_pos_flow,
        next_phase_key,
        validate_flow,
    )
    from app.tenants import Tenant

    flow = default_bahi_pos_flow()
    # Niche picker after business name
    bn_i = next(i for i, s in enumerate(flow) if s["key"] == "BUSINESS_NAME")
    flow.insert(
        bn_i + 1,
        {
            "id": "step_niche",
            "key": "NICHE_PICK",
            "type": "list_options",
            "question_text": "Which facility type?",
            "options": [
                {
                    "id": "assisted",
                    "title": "Assisted living",
                    "value": "Assisted living",
                    "next_key": "ASSISTED_Q1",
                },
                {
                    "id": "memory",
                    "title": "Memory care",
                    "value": "Memory care",
                    "next_key": "MEMORY_Q1",
                },
            ],
            "capture_field": "custom_1",
            "required": True,
            "reserved": False,
            "system": False,
        },
    )
    flow.insert(
        bn_i + 2,
        {
            "id": "step_al1",
            "key": "ASSISTED_Q1",
            "type": "free_text_capture",
            "question_text": "How many assisted living beds?",
            "options": [],
            "capture_field": "custom_2",
            "next_key": "SCHEDULING",
            "required": True,
            "reserved": False,
            "system": False,
        },
    )
    flow.insert(
        bn_i + 3,
        {
            "id": "step_mc1",
            "key": "MEMORY_Q1",
            "type": "free_text_capture",
            "question_text": "Memory care census?",
            "options": [],
            "capture_field": "custom_3",
            "next_key": "SCHEDULING",
            "required": True,
            "reserved": False,
            "system": False,
        },
    )
    cleaned = validate_flow(flow)
    tenant = Tenant(
        phone_number_id="x",
        name="T",
        flow_mode="lead",
        campaign_phrase="Bahi",
        demo_slots=["A", "B"],
    )
    tenant._raw_config = {"flow": cleaned}

    assert next_phase_key(tenant, "BUSINESS_NAME") == "NICHE_PICK"

    meta = {"phase": "NICHE_PICK", "lang": "en"}
    ok, _ = apply_flow_interactive_answer(meta, "assisted", "Assisted living", tenant=tenant)
    assert ok
    assert meta["phase"] == "ASSISTED_Q1"
    assert meta.get("custom_1") == "Assisted living"
    assert meta.get("branch") == "assisted"

    assert next_phase_key(tenant, "ASSISTED_Q1") == "SCHEDULING"
    assert next_phase_key(tenant, "MEMORY_Q1") == "SCHEDULING"

    meta2 = {"phase": "NICHE_PICK", "lang": "en"}
    ok2, _ = apply_flow_interactive_answer(meta2, "memory", "Memory care", tenant=tenant)
    assert ok2
    assert meta2["phase"] == "MEMORY_Q1"
