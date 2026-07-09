"""
Conversation session storage.

v1: in-memory dict — fine for a single Railway instance and a pilot shop.
If the process restarts, conversations reset (customers just start over).
Upgrade path: swap these three functions for Redis when you have >3 clients.
"""

import asyncio
from typing import Dict, List

_sessions: Dict[str, List[dict]] = {}
_locks: Dict[str, asyncio.Lock] = {}


def get_session(sender: str) -> List[dict]:
    return _sessions.setdefault(sender, [])


def save_session(sender: str, history: List[dict]) -> None:
    _sessions[sender] = history


def clear_session(sender: str) -> None:
    _sessions.pop(sender, None)


def get_sender_lock(sender: str) -> asyncio.Lock:
    """Return (creating if needed) a per-sender asyncio.Lock."""
    return _locks.setdefault(sender, asyncio.Lock())
