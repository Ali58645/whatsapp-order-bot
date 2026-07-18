"""Alembic env — sync migrations (used by app startup + alembic CLI)."""

from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection

from app.db.models import Base  # noqa: F401

config = context.config

# backend/ — parent of alembic/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _to_sync_url(raw: str) -> str:
    """Alembic runs sync — strip async drivers; keep Neon sslmode."""
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql+asyncpg://"):
        raw = "postgresql://" + raw[len("postgresql+asyncpg://"):]
    if raw.startswith("sqlite+aiosqlite://"):
        raw = "sqlite://" + raw[len("sqlite+aiosqlite://"):]
    return raw


def _get_url() -> str:
    configured = config.get_main_option("sqlalchemy.url") or ""
    fallback = _BACKEND_ROOT / "test_migration.db"
    raw = configured or os.environ.get("DATABASE_URL", "") or f"sqlite:///{fallback}"
    return _to_sync_url(raw)


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
