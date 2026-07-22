"""Owner first-run business setup — template + knowledge + hours."""

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

PID = "PID_SETUP"
ADMIN_USER = "setupadmin"
ADMIN_PASS = "setuppass"
JWT_SECRET = "owner-setup-jwt-secret-32chars!!"


@pytest.fixture
def setup_env(monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", ADMIN_USER)
    monkeypatch.setenv("DASHBOARD_PASSWORD", ADMIN_PASS)
    monkeypatch.setenv("DASHBOARD_JWT_SECRET", JWT_SECRET)


@pytest_asyncio.fixture
async def setup_db(tmp_path, monkeypatch, setup_env):
    url = f"sqlite+aiosqlite:///{tmp_path}/setup.db"
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

    t = Tenant(
        phone_number_id=PID,
        name="Fresh Biz",
        flow_mode="lead",
        campaign_phrase="Hello",
        demo_slots=["Mon 10am"],
        greeting_text="",
    )

    async with eng.get_db() as db:
        await sync_tenants_to_db(db, [t])
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
        row = (
            await db.execute(select(DBTenant).where(DBTenant.phone_number_id == PID))
        ).scalar_one()
        if not await get_user_by_username(db, "setupowner"):
            await create_user(
                db,
                username="setupowner",
                password_hash=hash_password("ownerpass1"),
                role="owner",
                tenant_id=row.id,
            )

    yield {"tenant_id": row.id, "pid": PID}


@pytest_asyncio.fixture
async def client(setup_db):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _login(client, user, password):
    r = await client.post("/api/auth/login", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def test_resolve_setup_template_by_vertical():
    from app.owner_setup import resolve_setup_template

    assert resolve_setup_template(template_id=None, vertical="salon", flow_mode="lead") == "salon_booking"
    assert resolve_setup_template(template_id=None, vertical="restaurant", flow_mode="order") == "restaurant"
    assert resolve_setup_template(template_id=None, vertical="unknown_xyz", flow_mode="lead") == "generic_lead"
    assert resolve_setup_template(template_id=None, vertical="unknown_xyz", flow_mode="order") == "generic_order"
    assert resolve_setup_template(template_id="salon_booking", vertical=None, flow_mode="lead") == "salon_booking"


def test_setup_preview_uses_owner_offer_not_bahi_pos():
    from app.owner_setup import setup_preview

    p = setup_preview(
        template_id="pos_lead",
        business_name="AccellionX",
        overview="Automation for senior living",
        offer="EHR integrations, staff scheduling, AI agents",
        location="Lahore",
        greeting_language="roman_urdu",
        flow_mode="lead",
    )
    blob = str(p).lower()
    assert "bahi pos" not in blob
    assert "fbr" not in blob
    assert "accellionx" in blob
    assert "ehr" in blob or "scheduling" in blob
    sched = next(q for q in p["questions"] if q["key"] == "q_scheduling")
    assert "AccellionX" in sched["text"]
    buttons = next(q for q in p["questions"] if q["key"] == "buttons_business_types")
    assert "Grocery" not in buttons["text"]
    assert "EHR" in buttons["text"] or "scheduling" in buttons["text"].lower()


def test_message_overrides_applied():
    from app.owner_setup import apply_owner_setup_to_config
    from types import SimpleNamespace

    row = SimpleNamespace(
        config={},
        flow_mode="lead",
        name="Old",
        phone_number_id="x",
    )
    cfg, tid = apply_owner_setup_to_config(
        row,
        business_name="AX",
        flow_mode="lead",
        template_id="pos_lead",
        greeting_language="roman_urdu",
        greeting_text="Hello from AX",
        business_hours={"enabled": False},
        overview="We automate ops",
        offer="Bots, dashboards",
        location="Karachi",
        message_overrides={
            "lead": {
                "q_scheduling": "Custom schedule question for AX?",
                "handoff": "Custom handoff — AX team will call.",
            },
            "interactive": {"business_types_text": "Bots, Dashboards, Other"},
        },
    )
    assert tid == "pos_lead"
    lead = (cfg.get("messages") or {}).get("lead") or {}
    assert lead["q_scheduling"] == "Custom schedule question for AX?"
    assert lead["handoff"] == "Custom handoff — AX team will call."
    titles = [
        r["title"]
        for r in ((cfg.get("messages") or {}).get("interactive") or {}).get("business_types") or []
    ]
    assert "Bots" in titles
    assert "Dashboards" in titles


def test_build_knowledge_and_hours_text():
    from app.owner_setup import build_knowledge_from_answers, format_hours_for_knowledge

    bh = {
        "enabled": True,
        "timezone": "Asia/Karachi",
        "away_message": "Closed",
        "days": {
            "mon": [["09:00", "17:00"]],
            "tue": [["09:00", "17:00"]],
            "wed": [],
            "thu": [["09:00", "17:00"]],
            "fri": [["09:00", "17:00"]],
            "sat": [["10:00", "14:00"]],
            "sun": [],
        },
    }
    text = format_hours_for_knowledge(bh)
    assert "Monday: 09:00–17:00" in text
    assert "Wednesday: Closed" in text

    kb = build_knowledge_from_answers(
        business_name="Al-Noor Salon",
        overview="Hair and bridal salon in DHA",
        offer="Haircut, facial, bridal",
        location="DHA Phase 5",
        contact="03001234567",
        business_hours=bh,
    )
    assert kb["status"] == "published"
    assert kb["enabled"] is True
    assert "Al-Noor" in kb["complete_knowledge"]
    assert "Haircut" in kb["sections"]["products_services"]
    assert "Monday" in kb["sections"]["business_hours"]


@pytest.mark.asyncio
async def test_owner_setup_status_needed(client, setup_db):
    data = await _login(client, "setupowner", "ownerpass1")
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    r = await client.get("/api/dashboard/owner/setup", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["needed"] is True
    assert body["templates"]["lead"]
    assert body["templates"]["order"]

    me = await client.get("/api/dashboard/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["tenant"]["setup_needed"] is True


@pytest.mark.asyncio
async def test_owner_setup_preview_and_apply(client, setup_db):
    data = await _login(client, "setupowner", "ownerpass1")
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    prev = await client.get(
        "/api/dashboard/owner/setup/preview",
        params={
            "template_id": "salon_booking",
            "business_name": "Al-Noor Salon",
            "greeting_language": "roman_urdu",
            "flow_mode": "lead",
        },
        headers=headers,
    )
    assert prev.status_code == 200, prev.text
    preview = prev.json()
    assert preview["template_id"] == "salon_booking"
    assert len(preview["greetings"]) >= 1
    greet = preview["greetings"][0]["text"]

    r = await client.post(
        "/api/dashboard/owner/setup",
        headers=headers,
        json={
            "business_name": "Al-Noor Salon",
            "flow_mode": "lead",
            "template_id": "salon_booking",
            "greeting_language": "roman_urdu",
            "greeting_text": greet,
            "business_hours": {
                "enabled": True,
                "timezone": "Asia/Karachi",
                "away_message": "Band hain",
                "days": {
                    "mon": [["10:00", "19:00"]],
                    "tue": [["10:00", "19:00"]],
                    "wed": [["10:00", "19:00"]],
                    "thu": [["10:00", "19:00"]],
                    "fri": [["10:00", "19:00"]],
                    "sat": [["11:00", "16:00"]],
                    "sun": [],
                },
            },
            "overview": "Premium salon in DHA offering bridal and hair services.",
            "offer": "Haircut, facial, bridal makeup",
            "location": "DHA Phase 5, Lahore",
            "contact": "03001234567",
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
    assert out["template_id"] == "salon_booking"

    cfg = out["config"]["config"]
    assert cfg["greeting_text"] == greet
    assert cfg["knowledge_base"]["status"] == "published"
    assert "Bridal" in cfg["knowledge_base"]["complete_knowledge"] or "bridal" in cfg[
        "knowledge_base"
    ]["complete_knowledge"].lower()
    assert cfg["business_hours"]["enabled"] is True
    assert cfg["onboarding"]["content_set"] is True
    assert cfg["onboarding"]["owner_setup_complete"] is True
    assert cfg.get("messages") or cfg.get("messages_draft")
    assert cfg.get("flow")

    # Wizard should no longer be needed
    st = await client.get("/api/dashboard/owner/setup", headers=headers)
    assert st.json()["needed"] is False
    me = await client.get("/api/dashboard/me", headers=headers)
    assert me.json()["tenant"]["setup_needed"] is False


@pytest.mark.asyncio
async def test_owner_setup_order_mode(client, setup_db):
    data = await _login(client, "setupowner", "ownerpass1")
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    r = await client.post(
        "/api/dashboard/owner/setup",
        headers=headers,
        json={
            "business_name": "Karachi Biryani",
            "flow_mode": "order",
            "template_id": "restaurant",
            "greeting_language": "en",
            "greeting_text": "Welcome to Karachi Biryani! Browse the menu to order.",
            "business_hours": {"enabled": False},
            "overview": "Home-style biryani and karahi delivery.",
            "offer": "Chicken biryani, beef karahi",
            "location": "Gulshan",
            "contact": "0211234567",
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["flow_mode"] == "order"
    cfg = out["config"]["config"]
    assert cfg.get("menu_v2") or cfg.get("menu_v2_draft")
    assert cfg["knowledge_base"]["status"] == "published"


def test_retarget_rewrites_more_replies_to_english():
    from app.owner_setup import retarget_config_language

    cfg = {
        "greeting_text": "Assalam o Alaikum AccellionX",
        "greeting_language": "roman_urdu",
        "demo_slots": ["Kal 11am", "Kal 4pm"],
        "messages_draft": {
            "lead": {
                "confirm_slot": (
                    "Shukriya. Aap ka AccellionX slot {{slot}} ke liye booked ho gaya hai. "
                    "Hamari team aap se is number par rabta karegi."
                ),
                "handoff": "AccellionX ki team jald aap se rabta karegi. Shukriya apna waqt dene ka.",
                "ack_business_name": "Shukriya — AccellionX ke liye aap ki info record ho gayi.",
            }
        },
        "messages": {
            "lead": {
                "confirm_slot": "Shukriya published urdu {{slot}}",
                "handoff": "Urdu handoff",
            }
        },
        "knowledge_base": {
            "sections": {
                "overview": "We automate ops",
                "products_services": "Automation",
                "locations": "Lahore",
            }
        },
    }
    out = retarget_config_language(
        cfg,
        business_name="AccellionX",
        flow_mode="lead",
        greeting_language="en",
    )
    lead = (out["messages_draft"] or {}).get("lead") or {}
    pub = (out["messages"] or {}).get("lead") or {}
    assert "Thank you" in lead["confirm_slot"]
    assert "Shukriya" not in lead["confirm_slot"]
    assert "{{slot}}" in lead["confirm_slot"]
    assert "contact you" in lead["handoff"].lower()
    assert "Thank you" in lead["ack_business_name"]
    assert lead["confirm_slot"] == pub["confirm_slot"]
    assert lead["handoff"] == pub["handoff"]


def test_english_selection_has_no_roman_urdu_copy():
    """Selecting English must rewrite greeting, questions, slots, and more replies."""
    import re
    from app.messages import default_messages
    from app.owner_setup import apply_owner_setup_to_config, retarget_config_language
    from app.templates import build_draft_patch

    markers = re.compile(
        r"(?i)\b(aap(?:ka|ki)?|shukriya|assalam|muntakhib|barah-e-karam|dilchaspi|"
        r"farmaayein|hamari|kaunsi|neeche|maazrat|likhein|dekhein|\bkal\b|kuch nahi)\b"
    )

    def assert_clean(obj, label: str) -> None:
        if isinstance(obj, str):
            assert not markers.search(obj), f"{label}: {obj[:120]}"
        elif isinstance(obj, list):
            for i, x in enumerate(obj):
                assert_clean(x, f"{label}[{i}]")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                assert_clean(v, f"{label}.{k}")

    assert_clean(default_messages("en"), "defaults")

    patch = build_draft_patch(
        "pos_lead", greeting_language="en", business_name="AccellionX"
    )
    assert_clean(patch.get("greeting_text"), "greet")
    assert_clean(patch.get("demo_slots"), "slots")
    assert_clean(patch.get("messages_draft"), "draft")

    class Row:
        config = {}

    cfg, _ = apply_owner_setup_to_config(
        Row(),
        business_name="AccellionX",
        flow_mode="lead",
        template_id="pos_lead",
        greeting_language="en",
        greeting_text="Welcome! Thanks for your interest in AccellionX.",
        business_hours={"enabled": False},
        overview="We automate ops",
        offer="Automation",
        location="Lahore",
    )
    assert_clean(cfg.get("greeting_text"), "apply.greet")
    assert_clean(cfg.get("demo_slots"), "apply.slots")
    assert_clean(cfg.get("messages_draft"), "apply.draft")
    assert cfg["demo_slots"][0].startswith("Tomorrow")

    urdu_cfg = {
        "greeting_text": "Assalam o Alaikum AccellionX mein aap ki dilchaspi ka shukriya.",
        "demo_slots": ["Kal 11am", "Kal 4pm"],
        "messages_draft": default_messages("roman_urdu"),
        "messages": default_messages("roman_urdu"),
        "knowledge_base": {
            "sections": {
                "overview": "We help",
                "products_services": "Automation",
                "locations": "Lahore",
            }
        },
    }
    en_cfg = retarget_config_language(
        urdu_cfg,
        business_name="AccellionX",
        flow_mode="lead",
        greeting_language="en",
    )
    assert_clean(en_cfg.get("greeting_text"), "retarget.greet")
    assert_clean(en_cfg.get("demo_slots"), "retarget.slots")
    assert_clean(en_cfg.get("messages_draft"), "retarget.draft")
    assert "Welcome" in en_cfg["greeting_text"] or "Thanks" in en_cfg["greeting_text"]
    assert en_cfg["messages_draft"]["interactive"]["select_button_label"] == "Select"
