"""
Persistence tests — SessionStore / MuteStore / EventStore with SQLite.

These exercise the DB-backed path (DATABASE_URL set). Existing suite tests
run without DATABASE_URL and cover the in-memory fallback.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

# Env stubs before app imports (same pattern as other test modules)
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "testtoken")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "faketoken")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "12345")
os.environ.setdefault("OWNER_WHATSAPP", "9200000000")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fake")
os.environ.setdefault("FLOW_MODE", "lead")
os.environ.setdefault("BUSINESS_WA_ID", "92300BUSINESS")
os.environ.setdefault("CAMPAIGN_PHRASE", "Bahi POS")

SENDER = "923009998887"
PID = "PID_PERSIST_TEST"


def _make_tenant():
    from app.tenants import Tenant
    return Tenant(
        phone_number_id=PID,
        name="Persist Test",
        flow_mode="lead",
        business_wa_id="92300BIZ",
        owner_whatsapp="9200000000",
        campaign_phrase="Bahi POS",
        demo_slots=["Kal 11am", "Kal 4pm"],
    )


@pytest_asyncio.fixture
async def db_ready(tmp_path, monkeypatch):
    """Spin up a fresh SQLite DB and wire it into app.db.engine."""
    url = f"sqlite+aiosqlite:///{tmp_path}/persist.db"
    monkeypatch.setenv("DATABASE_URL", url)

    import app.db.engine as eng
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.db.models import Base
    from app.db.repo import sync_tenants_to_db

    if eng.engine is not None:
        await eng.engine.dispose()

    engine = create_async_engine(url, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(eng, "DATABASE_URL", url)
    monkeypatch.setattr(eng, "DB_ENABLED", True)
    monkeypatch.setattr(eng, "engine", engine)
    monkeypatch.setattr(eng, "AsyncSessionLocal", session_factory)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    tenant = _make_tenant()
    async with eng.get_db() as db:
        await sync_tenants_to_db(db, [tenant])

    # Clear in-memory mirrors so "restart" is meaningful
    from app import sessions, gate, lead
    sessions._sessions.clear()
    sessions._locks.clear()
    gate._muted.clear()
    lead._meta.clear()

    yield tenant

    await engine.dispose()
    monkeypatch.setattr(eng, "DB_ENABLED", False)
    monkeypatch.setattr(eng, "engine", None)
    monkeypatch.setattr(eng, "AsyncSessionLocal", None)
    monkeypatch.setattr(eng, "DATABASE_URL", "")


@pytest.mark.asyncio
async def test_session_survives_simulated_restart(db_ready):
    """Write via SessionStore, clear memory, load with a new store instance."""
    from app.db.store import SessionStore
    from app import sessions, lead

    tenant = db_ready
    store = await SessionStore.load(SENDER, tenant, profile_name="Ali")
    store.meta = {
        "phase": "BUSINESS_NAME",
        "lead_source": "Ad: Bahi POS",
        "business_name": "Ali Store",
    }
    store.phase = "BUSINESS_NAME"
    store.history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "salam"},
    ]
    await store.save()

    # Simulate process restart — wipe in-memory state
    sessions._sessions.clear()
    lead._meta.clear()

    restored = await SessionStore.load(SENDER, tenant)
    assert restored.phase == "BUSINESS_NAME"
    assert restored.meta.get("business_name") == "Ali Store"
    assert restored.meta.get("lead_source") == "Ad: Bahi POS"
    assert len(restored.history) == 2
    assert restored.history[0]["content"] == "hi"


@pytest.mark.asyncio
async def test_one_active_session_constraint(db_ready):
    """At most one ACTIVE session per (tenant, contact)."""
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from app.db.engine import get_db
    from app.db.models import DBSession
    from app.db.repo import get_db_tenant_id, get_or_create_contact, create_session
    from app.db.store import SessionStore

    tenant = db_ready

    store = await SessionStore.load(SENDER, tenant)
    store.meta = {"phase": "GREETING", "lead_source": "test"}
    store.phase = "GREETING"
    await store.save()

    async with get_db() as db:
        tid = await get_db_tenant_id(db, tenant.phone_number_id)
        contact = await get_or_create_contact(db, tid, SENDER)
        # Second active insert must violate the partial unique index
        try:
            await create_session(db, tid, contact.id, flow_mode="lead", phase="GREETING")
            await db.flush()
            pytest.fail("expected IntegrityError for second active session")
        except IntegrityError:
            await db.rollback()

    # After closing the first, a new active session is allowed
    await store.close("confirmed")
    store2 = await SessionStore.load(SENDER, tenant)
    store2.meta = {"phase": "GREETING", "lead_source": "again"}
    store2.phase = "GREETING"
    await store2.save()

    async with get_db() as db:
        tid = await get_db_tenant_id(db, tenant.phone_number_id)
        contact = await get_or_create_contact(db, tid, SENDER)
        result = await db.execute(
            select(DBSession).where(
                DBSession.tenant_id == tid,
                DBSession.contact_id == contact.id,
                DBSession.status == "active",
            )
        )
        active = result.scalars().all()
        assert len(active) == 1


@pytest.mark.asyncio
async def test_mute_persistence(db_ready):
    """Mute survives in-memory wipe when read back via MuteStore."""
    from app.db.store import MuteStore
    from app import gate

    tenant = db_ready
    await MuteStore.mute(SENDER, tenant, duration_s=3600)
    assert await MuteStore.is_muted(SENDER, tenant) is True

    # Simulate restart
    gate._muted.clear()
    assert gate.is_muted(SENDER, tenant.phone_number_id) is False

    # DB-backed check should restore mute into memory
    assert await MuteStore.is_muted(SENDER, tenant) is True
    assert gate.is_muted(SENDER, tenant.phone_number_id) is True


@pytest.mark.asyncio
async def test_events_on_activation_and_confirm(db_ready):
    """EventStore writes activation + confirmed rows."""
    from sqlalchemy import select
    from app.db.engine import get_db
    from app.db.models import DBEvent
    from app.db.repo import get_db_tenant_id
    from app.db.store import SessionStore, EventStore

    tenant = db_ready

    await EventStore.append(
        tenant, "activation",
        {"lead_source": "Ad: test"},
        wa_id=SENDER,
    )

    store = await SessionStore.load(SENDER, tenant)
    store.meta = {"phase": "CONFIRMED", "lead_source": "Ad: test", "demo_slot": "Kal 11am"}
    store.phase = "CONFIRMED"
    await store.close("confirmed")
    await EventStore.append(
        tenant, "confirmed",
        {"phase": "CONFIRMED"},
        wa_id=SENDER,
    )

    async with get_db() as db:
        tid = await get_db_tenant_id(db, tenant.phone_number_id)
        result = await db.execute(
            select(DBEvent.type).where(DBEvent.tenant_id == tid).order_by(DBEvent.id)
        )
        types = [row[0] for row in result.all()]
        assert "activation" in types
        assert "confirmed" in types
