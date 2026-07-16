"""
Database engine — SQLAlchemy 2.0 async.

DATABASE_URL from env:
  - postgresql+asyncpg://...  → real Postgres (production / Railway)
  - sqlite+aiosqlite:///...   → SQLite (tests / local without Postgres)
  - absent / empty            → DB_ENABLED = False, in-memory fallback mode

Railway note: Railway sets DATABASE_URL as postgres://... (no +asyncpg).
We normalise that automatically.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("orderbot.db")

# ── Resolve URL ──────────────────────────────────────────────────────────────

def _normalise_url(raw: str) -> str:
    """Convert Railway-style postgres:// to postgresql+asyncpg://"""
    if raw.startswith("postgres://"):
        return "postgresql+asyncpg://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://") and "+asyncpg" not in raw:
        return "postgresql+asyncpg://" + raw[len("postgresql://"):]
    return raw


_RAW_URL: str = os.environ.get("DATABASE_URL", "")
DATABASE_URL: str = _normalise_url(_RAW_URL) if _RAW_URL else ""

DB_ENABLED: bool = bool(DATABASE_URL)

# ── Engine / session factory ─────────────────────────────────────────────────

engine = None
AsyncSessionLocal = None

if DB_ENABLED:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

        _connect_args: dict = {}
        if DATABASE_URL.startswith("sqlite"):
            _connect_args = {"check_same_thread": False}

        engine = create_async_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            connect_args=_connect_args,
        )

        AsyncSessionLocal = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        log.info(f"db: engine created — {DATABASE_URL.split('@')[-1]}")  # hide credentials
    except Exception as exc:
        log.warning(f"db: failed to create engine ({exc}) — falling back to in-memory mode")
        DB_ENABLED = False
else:
    log.warning(
        "db: DATABASE_URL not set — running in in-memory fallback mode "
        "(sessions/leads/mutes will not survive restarts)"
    )


# ── Context manager helper ───────────────────────────────────────────────────

from contextlib import asynccontextmanager
from typing import AsyncGenerator


@asynccontextmanager
async def get_db() -> AsyncGenerator:
    """Async context manager that yields a DB session, or raises if DB disabled."""
    if not DB_ENABLED or AsyncSessionLocal is None:
        raise RuntimeError("DB not enabled")
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
