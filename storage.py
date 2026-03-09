"""
Persistent storage via Supabase — survives redeploys.

Tables (created once in Supabase):
  tikthook_subscribers  (chat_id BIGINT PRIMARY KEY, added_at TIMESTAMPTZ)
  tikthook_live_state   (username TEXT PRIMARY KEY, is_live BOOLEAN, updated_at TIMESTAMPTZ)
"""

import logging
import os
from supabase import create_client, Client

logger = logging.getLogger(__name__)

_SUPABASE_URL = os.environ["SUPABASE_URL"]
_SUPABASE_KEY = os.environ["SUPABASE_KEY"]

def _client() -> Client:
    return create_client(_SUPABASE_URL, _SUPABASE_KEY)


# ---------------------------------------------------------------------------
# Subscribers
# ---------------------------------------------------------------------------

async def get_subscribers() -> list[int]:
    try:
        res = _client().table("tikthook_subscribers").select("chat_id").execute()
        return [row["chat_id"] for row in res.data]
    except Exception as e:
        logger.error("get_subscribers failed: %s", e)
        return []


async def add_subscriber(chat_id: int) -> bool:
    """Returns True if added, False if already present."""
    try:
        existing = (
            _client()
            .table("tikthook_subscribers")
            .select("chat_id")
            .eq("chat_id", chat_id)
            .execute()
        )
        if existing.data:
            return False
        _client().table("tikthook_subscribers").insert({"chat_id": chat_id}).execute()
        return True
    except Exception as e:
        logger.error("add_subscriber failed: %s", e)
        return False


async def remove_subscriber(chat_id: int) -> bool:
    """Returns True if removed, False if not found."""
    try:
        existing = (
            _client()
            .table("tikthook_subscribers")
            .select("chat_id")
            .eq("chat_id", chat_id)
            .execute()
        )
        if not existing.data:
            return False
        _client().table("tikthook_subscribers").delete().eq("chat_id", chat_id).execute()
        return True
    except Exception as e:
        logger.error("remove_subscriber failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Live state
# ---------------------------------------------------------------------------

async def get_live_state() -> dict[str, bool]:
    try:
        res = _client().table("tikthook_live_state").select("username, is_live").execute()
        return {row["username"]: row["is_live"] for row in res.data}
    except Exception as e:
        logger.error("get_live_state failed: %s", e)
        return {}


async def set_live_state(username: str, is_live: bool) -> None:
    try:
        _client().table("tikthook_live_state").upsert(
            {"username": username, "is_live": is_live, "updated_at": "now()"}
        ).execute()
    except Exception as e:
        logger.error("set_live_state failed: %s", e)


async def get_live_accounts() -> list[str]:
    try:
        res = (
            _client()
            .table("tikthook_live_state")
            .select("username")
            .eq("is_live", True)
            .execute()
        )
        return [row["username"] for row in res.data]
    except Exception as e:
        logger.error("get_live_accounts failed: %s", e)
        return []
