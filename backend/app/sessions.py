"""
Conversation session storage — multi-tenant.

v2: DB-backed when DATABASE_URL is set; in-memory fallback otherwise.

The in-memory dicts here are always kept up-to-date by SessionStore.save()
so existing call sites (get_session / save_session / clear_session) continue
to work unchanged in both DB and fallback modes.

get_sender_lock is re-exported from app.db.store so callers only need one
import regardless of mode.
"""

import asyncio
from typing import Dict, List, Tuple

# (tenant_id, sender) → conversation history
_sessions: Dict[Tuple[str, str], List[dict]] = {}
# (tenant_id, sender) → asyncio.Lock
_locks: Dict[Tuple[str, str], asyncio.Lock] = {}


def _key(tenant_id: str, sender: str) -> Tuple[str, str]:
    return (tenant_id, sender)


def get_session(sender: str, tenant_id: str = "") -> List[dict]:
    return _sessions.setdefault(_key(tenant_id, sender), [])


def save_session(sender: str, history: List[dict], tenant_id: str = "") -> None:
    _sessions[_key(tenant_id, sender)] = history


def clear_session(sender: str, tenant_id: str = "") -> None:
    _sessions.pop(_key(tenant_id, sender), None)


def get_sender_lock(sender: str, tenant_id: str = "") -> asyncio.Lock:
    """Return (creating if needed) a per-sender-per-tenant asyncio.Lock."""
    k = _key(tenant_id, sender)
    return _locks.setdefault(k, asyncio.Lock())
