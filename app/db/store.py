"""
DB-backed store façades for sessions, lead meta, and mutes.

When DB_ENABLED is False these fall back to the in-memory dicts already
in sessions.py / gate.py / lead.py — zero behaviour change for tests and
local dev without a DATABASE_URL.

Call pattern from main.py and flow handlers:
  store = await SessionStore.load(sender, tenant)
  # … mutate store.history, store.meta, store.phase …
  await store.save()
  await store.close("confirmed")   # optional final status

MuteStore:
  await MuteStore.mute(wa_id, tenant, duration_s)
  await MuteStore.is_muted(wa_id, tenant)
  await MuteStore.clear(wa_id, tenant)

EventStore:
  await EventStore.append(tenant, event_type, payload, wa_id=None)

All DB errors are caught and logged; the in-memory path is used as
fallback so the bot keeps responding even if Postgres is temporarily down.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.tenants import Tenant

log = logging.getLogger("orderbot.store")

# ── In-process sender locks (always in-memory, fine for single instance) ────
_locks: dict[tuple[str, str], asyncio.Lock] = {}


def get_sender_lock(sender: str, tenant_id: str = "") -> asyncio.Lock:
    k = (tenant_id, sender)
    return _locks.setdefault(k, asyncio.Lock())


# ── helpers ──────────────────────────────────────────────────────────────────

async def _get_db_tenant_id(db, phone_number_id: str) -> Optional[int]:
    from app.db.repo import get_db_tenant_id
    return await get_db_tenant_id(db, phone_number_id)


# ═════════════════════════════════════════════════════════════════════════════
# SessionStore  — one instance per (sender, tenant) per webhook call
# ═════════════════════════════════════════════════════════════════════════════

class SessionStore:
    """
    Holds session state for one (sender, tenant) pair.

    Usage:
        store = await SessionStore.load(sender, tenant)
        # read/write store.history, store.meta, store.phase
        await store.save()
    """

    def __init__(
        self,
        sender: str,
        tenant: "Tenant",
        *,
        history: list,
        meta: dict,
        phase: str,
        _db_session_row: Any = None,
        _db_conn=None,
        _contact_id: Optional[int] = None,
        _tenant_db_id: Optional[int] = None,
    ):
        self.sender = sender
        self.tenant = tenant
        self.history: list = history
        self.meta: dict = meta
        self.phase: str = phase

        self._db_session_row = _db_session_row
        self._db_conn = _db_conn
        self._contact_id = _contact_id
        self._tenant_db_id = _tenant_db_id

    # ── Factory ──────────────────────────────────────────────────────────────

    @classmethod
    async def load(
        cls,
        sender: str,
        tenant: "Tenant",
        profile_name: str = "",
    ) -> "SessionStore":
        """Load or create session state for (sender, tenant)."""
        from app.db.engine import DB_ENABLED

        if DB_ENABLED:
            try:
                return await cls._load_from_db(sender, tenant, profile_name)
            except Exception as exc:
                log.error(f"store: DB load failed for {sender} — {exc}; using in-memory")

        return cls._load_from_memory(sender, tenant)

    @classmethod
    def _load_from_memory(cls, sender: str, tenant: "Tenant") -> "SessionStore":
        from app.sessions import get_session as _mem_get_session
        from app.lead import get_lead_meta as _mem_get_meta

        tid = tenant.phone_number_id
        history = list(_mem_get_session(sender, tenant_id=tid))
        meta = dict(_mem_get_meta(sender, tenant_id=tid))
        phase = meta.get("phase", "GREETING")
        return cls(sender, tenant, history=history, meta=meta, phase=phase)

    @classmethod
    async def _load_from_db(
        cls, sender: str, tenant: "Tenant", profile_name: str = ""
    ) -> "SessionStore":
        from app.db.engine import get_db
        from app.db.repo import (
            get_db_tenant_id, get_or_create_contact,
            get_active_session,
        )

        async with get_db() as db:
            tenant_db_id = await get_db_tenant_id(db, tenant.phone_number_id)
            if tenant_db_id is None:
                raise ValueError(f"Tenant {tenant.phone_number_id!r} not in DB")

            contact = await get_or_create_contact(db, tenant_db_id, sender, profile_name)
            contact_id = contact.id

            db_sess = await get_active_session(db, tenant_db_id, contact_id)
            if db_sess is None:
                # Nothing stored yet — return empty state (not persisted until save())
                return cls(
                    sender, tenant,
                    history=[], meta={}, phase="GREETING",
                    _db_session_row=None,
                    _db_conn=None,
                    _contact_id=contact_id,
                    _tenant_db_id=tenant_db_id,
                )

            meta = dict(db_sess.meta or {})
            phase = db_sess.phase or meta.get("phase", "GREETING")
            meta["phase"] = phase  # keep in sync

            return cls(
                sender, tenant,
                history=list(db_sess.history or []),
                meta=meta,
                phase=phase,
                _db_session_row=db_sess,
                _db_conn=None,  # we don't keep the connection open between calls
                _contact_id=contact_id,
                _tenant_db_id=tenant_db_id,
            )

    # ── Persistence ──────────────────────────────────────────────────────────

    async def save(self) -> None:
        """Persist current state back to DB and in-memory store."""
        # Always keep in-memory up-to-date (for tests + fallback reads)
        self._sync_to_memory()

        from app.db.engine import DB_ENABLED
        if not DB_ENABLED:
            return

        try:
            await self._save_to_db(status="active")
        except Exception as exc:
            log.error(f"store: DB save failed for {self.sender} — {exc}")

    async def close(self, status: str = "closed") -> None:
        """Save final state and mark session closed."""
        self.meta["phase"] = status.upper() if status not in ("closed",) else self.phase
        self._sync_to_memory()
        self._clear_memory()

        from app.db.engine import DB_ENABLED
        if not DB_ENABLED:
            return

        try:
            await self._save_to_db(status=status)
        except Exception as exc:
            log.error(f"store: DB close failed for {self.sender} — {exc}")

    def _sync_to_memory(self) -> None:
        """Mirror state to the in-memory dicts so existing code keeps working."""
        from app.sessions import save_session as _mem_save
        from app.lead import _meta as _lead_meta

        tid = self.tenant.phone_number_id
        _mem_save(self.sender, self.history, tenant_id=tid)
        self.meta["phase"] = self.phase
        _lead_meta[(tid, self.sender)] = self.meta

    def _clear_memory(self) -> None:
        from app.sessions import clear_session as _mem_clear
        from app.lead import clear_lead_meta as _mem_clear_meta

        tid = self.tenant.phone_number_id
        _mem_clear(self.sender, tenant_id=tid)
        _mem_clear_meta(self.sender, tenant_id=tid)

    async def _save_to_db(self, status: str) -> None:
        from app.db.engine import get_db
        from app.db.repo import (
            get_db_tenant_id, get_or_create_contact,
            get_active_session, create_session,
            save_session_state, upsert_lead_record,
        )

        async with get_db() as db:
            tenant_db_id = self._tenant_db_id
            contact_id = self._contact_id

            if tenant_db_id is None:
                tenant_db_id = await get_db_tenant_id(db, self.tenant.phone_number_id)
            if contact_id is None:
                contact = await get_or_create_contact(db, tenant_db_id, self.sender)
                contact_id = contact.id

            db_sess = self._db_session_row
            if db_sess is None:
                # Re-fetch in case another save already created it
                db_sess = await get_active_session(db, tenant_db_id, contact_id)

            if db_sess is None:
                db_sess = await create_session(
                    db, tenant_db_id, contact_id,
                    flow_mode=self.tenant.flow_mode,
                    phase=self.phase,
                    meta=self.meta,
                )
                self._db_session_row = db_sess
                self._tenant_db_id = tenant_db_id
                self._contact_id = contact_id
                # Apply final status/history even on first write (e.g. close-on-create)
                await save_session_state(
                    db, db_sess,
                    phase=self.phase,
                    meta=self.meta,
                    history=self.history,
                    status=status,
                )
            else:
                await save_session_state(
                    db, db_sess,
                    phase=self.phase,
                    meta=self.meta,
                    history=self.history,
                    status=status,
                )

            # Upsert lead record if this is a lead session
            if self.tenant.flow_mode == "lead" and self.meta.get("lead_source"):
                await upsert_lead_record(
                    db, tenant_db_id, contact_id, db_sess.id, self.meta
                )

    # ── Convenience property mirrors ─────────────────────────────────────────

    @property
    def is_active_lead(self) -> bool:
        phase = self.meta.get("phase", "GREETING")
        return phase not in (None, "CONFIRMED", "STALLED", "GREETING") or bool(
            self.meta.get("lead_source")
        )

    def get_meta(self) -> dict:
        return self.meta

    def set_phase(self, phase: str) -> None:
        self.phase = phase
        self.meta["phase"] = phase


# ═════════════════════════════════════════════════════════════════════════════
# MuteStore  — async wrapper around in-memory + DB mutes
# ═════════════════════════════════════════════════════════════════════════════

class MuteStore:
    """Static async methods for managing mutes."""

    @staticmethod
    async def mute(
        wa_id: str,
        tenant: "Tenant",
        duration_s: int = 24 * 3600,
    ) -> None:
        """Mute wa_id for duration_s seconds."""
        from app.gate import mute_contact as _mem_mute
        _mem_mute(wa_id, tenant.phone_number_id, duration_s)

        from app.db.engine import DB_ENABLED
        if not DB_ENABLED:
            return
        try:
            from app.db.engine import get_db
            from app.db.repo import get_db_tenant_id, set_mute
            muted_until = datetime.now(timezone.utc) + timedelta(seconds=duration_s)
            async with get_db() as db:
                tid = await get_db_tenant_id(db, tenant.phone_number_id)
                if tid is not None:
                    await set_mute(db, tid, wa_id, muted_until)
        except Exception as exc:
            log.error(f"store: DB mute failed for {wa_id} — {exc}")

    @staticmethod
    async def is_muted(wa_id: str, tenant: "Tenant") -> bool:
        """True if wa_id is currently muted for this tenant."""
        from app.gate import is_muted as _mem_is_muted
        if _mem_is_muted(wa_id, tenant.phone_number_id):
            return True

        from app.db.engine import DB_ENABLED
        if not DB_ENABLED:
            return False
        try:
            from app.db.engine import get_db
            from app.db.repo import get_db_tenant_id, get_mute_until
            async with get_db() as db:
                tid = await get_db_tenant_id(db, tenant.phone_number_id)
                if tid is None:
                    return False
                until = await get_mute_until(db, tid, wa_id)
                if until is None:
                    return False
                now = datetime.now(timezone.utc)
                if until.tzinfo is None:
                    until = until.replace(tzinfo=timezone.utc)
                if now >= until:
                    await clear_mute_in_db(db, tid, wa_id)
                    return False
                # Sync back to in-memory
                from app.gate import _muted
                _muted[(tenant.phone_number_id, wa_id)] = until.timestamp()
                return True
        except Exception as exc:
            log.error(f"store: DB mute check failed for {wa_id} — {exc}")
            return False

    @staticmethod
    async def clear(wa_id: str, tenant: "Tenant") -> None:
        from app.gate import clear_mute as _mem_clear
        _mem_clear(wa_id, tenant.phone_number_id)

        from app.db.engine import DB_ENABLED
        if not DB_ENABLED:
            return
        try:
            from app.db.engine import get_db
            from app.db.repo import get_db_tenant_id, clear_mute as _db_clear_mute
            async with get_db() as db:
                tid = await get_db_tenant_id(db, tenant.phone_number_id)
                if tid is not None:
                    await _db_clear_mute(db, tid, wa_id)
        except Exception as exc:
            log.error(f"store: DB mute clear failed for {wa_id} — {exc}")


async def clear_mute_in_db(db, tenant_db_id: int, wa_id: str) -> None:
    from app.db.repo import clear_mute as _db_clear
    await _db_clear(db, tenant_db_id, wa_id)


# ═════════════════════════════════════════════════════════════════════════════
# EventStore  — fire-and-forget audit events
# ═════════════════════════════════════════════════════════════════════════════

class EventStore:
    @staticmethod
    async def append(
        tenant: "Tenant",
        event_type: str,
        payload: dict,
        wa_id: str | None = None,
    ) -> None:
        """Append an audit event.  Silently no-ops if DB not enabled."""
        from app.db.engine import DB_ENABLED
        if not DB_ENABLED:
            return
        try:
            from app.db.engine import get_db
            from app.db.repo import (
                get_db_tenant_id, get_or_create_contact, append_event
            )
            async with get_db() as db:
                tid = await get_db_tenant_id(db, tenant.phone_number_id)
                if tid is None:
                    return
                contact_id = None
                if wa_id:
                    contact = await get_or_create_contact(db, tid, wa_id)
                    contact_id = contact.id
                await append_event(db, tid, event_type, payload, contact_id=contact_id)
        except Exception as exc:
            log.error(f"store: event append failed ({event_type}) — {exc}")


# ═════════════════════════════════════════════════════════════════════════════
# OrderStore  — persist confirmed orders
# ═════════════════════════════════════════════════════════════════════════════

class OrderStore:
    @staticmethod
    async def save_order(
        tenant: "Tenant",
        wa_id: str,
        order: dict,
        session_store: SessionStore,
    ) -> None:
        from app.db.engine import DB_ENABLED
        if not DB_ENABLED:
            return
        try:
            from app.db.engine import get_db
            from app.db.repo import (
                get_db_tenant_id, get_or_create_contact,
                get_active_session, create_order_record,
            )
            async with get_db() as db:
                tid = await get_db_tenant_id(db, tenant.phone_number_id)
                if tid is None:
                    return
                contact = await get_or_create_contact(db, tid, wa_id)
                # Use session_store's cached DB row id if available
                session_id = (
                    session_store._db_session_row.id
                    if session_store._db_session_row is not None
                    else None
                )
                if session_id is None:
                    db_sess = await get_active_session(db, tid, contact.id)
                    session_id = db_sess.id if db_sess else None
                if session_id:
                    await create_order_record(db, tid, contact.id, session_id, order)
        except Exception as exc:
            log.error(f"store: order save failed — {exc}")
