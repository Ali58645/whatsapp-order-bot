"""
Run Alembic migrations at startup.

Uses a Postgres advisory lock (or a no-op for SQLite) so that
multi-worker deploys don't run migrations concurrently.

Called from the FastAPI lifespan handler so migrations run before the
first request is accepted.
"""

from __future__ import annotations

import asyncio
import logging

log = logging.getLogger("orderbot.migrate")

# Arbitrary lock key — unique to this app
_ADVISORY_LOCK_KEY = 74231459


def _to_sync_url(url: str) -> str:
    """Alembic/SQLAlchemy sync engines can't use asyncpg / aiosqlite drivers."""
    if url.startswith("postgresql+asyncpg://"):
        url = "postgresql://" + url[len("postgresql+asyncpg://"):]
    if url.startswith("sqlite+aiosqlite://"):
        url = "sqlite://" + url[len("sqlite+aiosqlite://"):]
    # Sync psycopg2 wants sslmode=, not asyncpg's ssl=
    if "ssl=require" in url and "sslmode=" not in url:
        url = url.replace("ssl=require", "sslmode=require")
    return url


async def run_migrations() -> None:
    """Apply all pending Alembic migrations.  No-op if DB is not enabled."""
    from app.db.engine import DB_ENABLED, DATABASE_URL

    if not DB_ENABLED:
        log.info("migrate: DB not enabled — skipping migrations")
        return

    log.info("migrate: running Alembic migrations …")
    try:
        await asyncio.to_thread(_run_sync_migrations, DATABASE_URL)
        log.info("migrate: migrations complete")
    except Exception as exc:
        log.error(f"migrate: migration failed — {exc}")
        raise


def _run_sync_migrations(database_url: str) -> None:
    """Sync helper executed in a worker thread."""
    import os as _os

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    sync_url = _to_sync_url(database_url)
    ini_path = _os.path.join(_os.path.dirname(__file__), "..", "..", "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", sync_url)

    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            if conn.dialect.name == "postgresql":
                got_lock = conn.execute(
                    text(f"SELECT pg_try_advisory_lock({_ADVISORY_LOCK_KEY})")
                ).scalar()
                if not got_lock:
                    log.info("migrate: another worker holds the lock — skipping")
                    return
                try:
                    command.upgrade(cfg, "head")
                finally:
                    conn.execute(text(f"SELECT pg_advisory_unlock({_ADVISORY_LOCK_KEY})"))
                    conn.commit()
            else:
                command.upgrade(cfg, "head")
    finally:
        engine.dispose()
