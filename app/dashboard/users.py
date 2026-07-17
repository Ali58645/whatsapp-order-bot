"""Dashboard user seeding and password helpers."""

from __future__ import annotations

import logging
import os

import bcrypt

log = logging.getLogger("orderbot.users")


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


async def seed_admin_user() -> None:
    """Create admin from DASHBOARD_USER/PASSWORD if no users exist."""
    from app.db.engine import DB_ENABLED, get_db
    from app.db.repo import get_user_by_username, create_user
    from sqlalchemy import select, func

    if not DB_ENABLED:
        return
    if not all(os.environ.get(k) for k in ("DASHBOARD_USER", "DASHBOARD_PASSWORD", "DASHBOARD_JWT_SECRET")):
        return

    async with get_db() as db:
        from app.db.models import DBUser
        count = (await db.execute(select(func.count(DBUser.id)))).scalar_one()
        if count and count > 0:
            return
        username = os.environ["DASHBOARD_USER"]
        existing = await get_user_by_username(db, username)
        if existing:
            return
        pw = os.environ["DASHBOARD_PASSWORD"]
        stored = pw if pw.startswith(("$2a$", "$2b$", "$2y$")) else hash_password(pw)
        await create_user(db, username=username, password_hash=stored, role="admin", tenant_id=None)
        log.info(f"users: seeded admin {username!r}")
