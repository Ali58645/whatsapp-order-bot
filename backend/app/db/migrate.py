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
from pathlib import Path

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


def check_migrations_at_head(database_url: str) -> bool | None:
    """
    True when alembic_version matches script head.
    None when DB is disabled or the check cannot run.
    """
    if not database_url:
        return None
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from sqlalchemy import create_engine

        sync_url = _to_sync_url(database_url)
        backend_root = Path(__file__).resolve().parent.parent.parent
        ini_path = backend_root / "alembic.ini"
        script_location = backend_root / "alembic"

        cfg = Config(str(ini_path))
        cfg.set_main_option("script_location", str(script_location))
        cfg.set_main_option("sqlalchemy.url", sync_url)

        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        engine = create_engine(sync_url)
        try:
            with engine.connect() as conn:
                current = MigrationContext.configure(conn).get_current_revision()
        finally:
            engine.dispose()
        if head is None:
            return True
        return current == head
    except Exception as exc:
        log.warning("migrate: head check failed — %s", exc)
        return None


def _run_sync_migrations(database_url: str) -> None:
    """Sync helper executed in a worker thread."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, text

    sync_url = _to_sync_url(database_url)
    backend_root = Path(__file__).resolve().parent.parent.parent  # app/db -> backend
    ini_path = backend_root / "alembic.ini"
    script_location = backend_root / "alembic"

    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(script_location))
    cfg.set_main_option("sqlalchemy.url", sync_url)

    engine = create_engine(sync_url)
    try:
        with engine.connect() as conn:
            if conn.dialect.name == "postgresql":
                # Block until we hold the lock — never skip migrations on contention.
                conn.execute(text(f"SELECT pg_advisory_lock({_ADVISORY_LOCK_KEY})"))
                try:
                    command.upgrade(cfg, "head")
                finally:
                    conn.execute(text(f"SELECT pg_advisory_unlock({_ADVISORY_LOCK_KEY})"))
                    conn.commit()
            else:
                command.upgrade(cfg, "head")
    finally:
        engine.dispose()
