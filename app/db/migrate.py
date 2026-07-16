"""
Run Alembic migrations at startup.

Uses an advisory lock (Postgres) or a simple retry (SQLite) so that
multi-worker deploys don't run migrations concurrently.

Called from the FastAPI lifespan handler so migrations run before the
first request is accepted.
"""

from __future__ import annotations

import asyncio
import logging
import os

log = logging.getLogger("orderbot.migrate")


async def run_migrations() -> None:
    """Apply all pending Alembic migrations.  No-op if DB is not enabled."""
    from app.db.engine import DB_ENABLED, DATABASE_URL

    if not DB_ENABLED:
        log.info("migrate: DB not enabled — skipping migrations")
        return

    log.info("migrate: running Alembic migrations …")
    try:
        # Run in thread to avoid blocking the event loop (Alembic is sync)
        await asyncio.to_thread(_run_sync_migrations, DATABASE_URL)
        log.info("migrate: migrations complete")
    except Exception as exc:
        log.error(f"migrate: migration failed — {exc}")
        raise


def _run_sync_migrations(database_url: str) -> None:
    """Sync helper executed in a worker thread."""
    import os as _os
    from alembic.config import Config
    from alembic import command

    # Point alembic at our ini file (repo root)
    ini_path = _os.path.join(_os.path.dirname(__file__), "..", "..", "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
