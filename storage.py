"""
Persistent JSON storage for subscriber chat IDs and live state tracking.

Schema:
{
    "subscribers": [123456789, ...],
    "live_state": {"username": true/false, ...}
}
"""

import json
import os
import asyncio
from typing import Any

from config import STORAGE_PATH

_lock = asyncio.Lock()

_DEFAULT: dict[str, Any] = {
    "subscribers": [],
    "live_state": {},
}


def _load_raw() -> dict[str, Any]:
    if not os.path.exists(STORAGE_PATH):
        return dict(_DEFAULT)
    with open(STORAGE_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = {}
    return {**_DEFAULT, **data}


def _save_raw(data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(STORAGE_PATH) or ".", exist_ok=True)
    tmp = STORAGE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, STORAGE_PATH)


# ---------------------------------------------------------------------------
# Subscribers
# ---------------------------------------------------------------------------

async def get_subscribers() -> list[int]:
    async with _lock:
        return list(_load_raw()["subscribers"])


async def add_subscriber(chat_id: int) -> bool:
    """Returns True if the subscriber was added, False if already present."""
    async with _lock:
        data = _load_raw()
        if chat_id in data["subscribers"]:
            return False
        data["subscribers"].append(chat_id)
        _save_raw(data)
        return True


async def remove_subscriber(chat_id: int) -> bool:
    """Returns True if the subscriber was removed, False if not found."""
    async with _lock:
        data = _load_raw()
        if chat_id not in data["subscribers"]:
            return False
        data["subscribers"].remove(chat_id)
        _save_raw(data)
        return True


# ---------------------------------------------------------------------------
# Live state
# ---------------------------------------------------------------------------

async def get_live_state() -> dict[str, bool]:
    async with _lock:
        return dict(_load_raw()["live_state"])


async def set_live_state(username: str, is_live: bool) -> None:
    async with _lock:
        data = _load_raw()
        data["live_state"][username] = is_live
        _save_raw(data)


async def get_live_accounts() -> list[str]:
    state = await get_live_state()
    return [u for u, v in state.items() if v]
