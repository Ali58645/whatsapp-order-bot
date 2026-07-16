"""
SQLAlchemy 2.0 ORM models.

Table summary:
  tenants      — mirrors the Tenant pydantic model; config stored as JSONB
  contacts     — one row per (tenant, wa_id); profile info
  sessions     — one ACTIVE session per (tenant, contact); holds phase+meta+history
  leads        — structured lead fields extracted from session meta
  orders       — confirmed order records
  mutes        — bot-silence records
  events       — append-only audit trail for dashboard activity feed

JSONB columns are mapped as JSON for SQLite compatibility in tests.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def _json_col():
    """Use JSONB on Postgres, JSON on everything else (SQLite for tests)."""
    # We use JSON type which SQLAlchemy maps to JSONB on Postgres via type coercion
    # when the dialect supports it.  For real JSONB we patch in alembic migration.
    return JSON


class Base(DeclarativeBase):
    pass


# ── Tenants ──────────────────────────────────────────────────────────────────

class DBTenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    phone_number_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    flow_mode: Mapped[str] = mapped_column(String(16), nullable=False)  # "lead" | "order"
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    contacts: Mapped[list["DBContact"]] = relationship(back_populates="tenant")
    sessions: Mapped[list["DBSession"]] = relationship(back_populates="tenant")
    mutes: Mapped[list["DBMute"]] = relationship(back_populates="tenant")
    events: Mapped[list["DBEvent"]] = relationship(back_populates="tenant")


# ── Contacts ─────────────────────────────────────────────────────────────────

class DBContact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "wa_id", name="uq_contacts_tenant_wa"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    wa_id: Mapped[str] = mapped_column(String(32), nullable=False)
    profile_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant: Mapped["DBTenant"] = relationship(back_populates="contacts")
    sessions: Mapped[list["DBSession"]] = relationship(back_populates="contact")
    leads: Mapped[list["DBLead"]] = relationship(back_populates="contact")
    orders: Mapped[list["DBOrder"]] = relationship(back_populates="contact")
    mutes: Mapped[list["DBMute"]] = relationship(back_populates="contact")
    events: Mapped[list["DBEvent"]] = relationship(back_populates="contact")


# ── Sessions ─────────────────────────────────────────────────────────────────

class DBSession(Base):
    """
    One row per conversation session.
    Partial unique index enforces at most one ACTIVE session per (tenant, contact).
    """
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    contact_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contacts.id"), nullable=False)
    flow_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False, default="GREETING")
    meta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )  # active | confirmed | stalled | closed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["DBTenant"] = relationship(back_populates="sessions")
    contact: Mapped["DBContact"] = relationship(back_populates="sessions")
    leads: Mapped[list["DBLead"]] = relationship(back_populates="session")
    orders: Mapped[list["DBOrder"]] = relationship(back_populates="session")

    # Partial unique index created in the Alembic migration (not expressible
    # purely via __table_args__ in a dialect-neutral way for partial indexes).
    __table_args__ = (
        Index(
            "ix_sessions_active_one_per_contact",
            "tenant_id",
            "contact_id",
            unique=True,
            postgresql_where="status = 'active'",
            sqlite_where="status = 'active'",
        ),
    )


# ── Leads ────────────────────────────────────────────────────────────────────

class DBLead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    contact_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contacts.id"), nullable=False)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sessions.id"), nullable=False)
    business_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    business_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    locations: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    current_system: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    demo_slot: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    entry_intent: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    ad_source: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["DBTenant"] = relationship()
    contact: Mapped["DBContact"] = relationship(back_populates="leads")
    session: Mapped["DBSession"] = relationship(back_populates="leads")


# ── Orders ────────────────────────────────────────────────────────────────────

class DBOrder(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    contact_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("contacts.id"), nullable=False)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sessions.id"), nullable=False)
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location_lat: Mapped[float | None] = mapped_column(nullable=True)
    location_lng: Mapped[float | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="confirmed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["DBTenant"] = relationship()
    contact: Mapped["DBContact"] = relationship(back_populates="orders")
    session: Mapped["DBSession"] = relationship(back_populates="orders")


# ── Mutes ─────────────────────────────────────────────────────────────────────

class DBMute(Base):
    __tablename__ = "mutes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "wa_id", name="uq_mutes_tenant_wa"),
    )

    tenant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tenants.id"), primary_key=True, nullable=False
    )
    wa_id: Mapped[str] = mapped_column(String(32), primary_key=True, nullable=False)
    muted_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant: Mapped["DBTenant"] = relationship(back_populates="mutes")
    contact: Mapped["DBContact"] = relationship(
        primaryjoin="and_(DBMute.tenant_id == DBContact.tenant_id, DBMute.wa_id == DBContact.wa_id)",
        foreign_keys="[DBMute.tenant_id, DBMute.wa_id]",
        viewonly=True,
    )


# ── Events ────────────────────────────────────────────────────────────────────

class DBEvent(Base):
    """
    Append-only audit trail.  Never updated after insert.
    Dashboard activity feed reads from this table.
    """
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tenants.id"), nullable=False)
    contact_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("contacts.id"), nullable=True
    )
    # activation | phase_change | confirmed | stalled | mute | human_takeover | error
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["DBTenant"] = relationship(back_populates="events")
    contact: Mapped["DBContact"] = relationship(back_populates="events")
