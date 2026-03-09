"""
Persistent storage via Airtable (base: ALLURE AGENCY).

Tables used:
  TikThook                  — COMPTE (TikTok username), NOM (display name)
  TikThook Subscribers      — CHAT_ID (Telegram user/chat ID, via /start)
  TikThook Groups           — CHAT_ID (Telegram group ID to notify)
  TikThook Discord Channels — GUILD_ID, CHANNEL_ID, GUILD_NAME
"""

import logging
import os
from pyairtable import Api

logger = logging.getLogger(__name__)

_BASE_ID = "appxPSRdBvtivWojx"


def _api() -> Api:
    return Api(os.environ["AIRTABLE_TOKEN"])


def _table(name: str):
    return _api().table(_BASE_ID, name)


# ---------------------------------------------------------------------------
# TikTok accounts
# ---------------------------------------------------------------------------

async def get_accounts() -> list[tuple[str, str]]:
    """Returns list of (display_name, username) from the TikThook table."""
    try:
        records = _table("TikThook").all(fields=["COMPTE", "NOM"])
        accounts = []
        for r in records:
            username = r["fields"].get("COMPTE", "").strip()
            nom = r["fields"].get("NOM", username).strip()
            if username:
                accounts.append((nom, username))
        return accounts
    except Exception as e:
        logger.error("get_accounts failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Telegram — individual subscribers (/start users)
# ---------------------------------------------------------------------------

async def get_subscribers() -> list[int]:
    try:
        records = _table("TikThook Subscribers").all(fields=["CHAT_ID"])
        return [int(r["fields"]["CHAT_ID"]) for r in records if "CHAT_ID" in r["fields"]]
    except Exception as e:
        logger.error("get_subscribers failed: %s", e)
        return []


async def add_subscriber(chat_id: int) -> bool:
    """Returns True if added, False if already present."""
    try:
        existing = _table("TikThook Subscribers").all(
            formula=f"{{CHAT_ID}}={chat_id}", fields=["CHAT_ID"]
        )
        if existing:
            return False
        _table("TikThook Subscribers").create({"CHAT_ID": chat_id})
        return True
    except Exception as e:
        logger.error("add_subscriber failed: %s", e)
        return False


async def remove_subscriber(chat_id: int) -> bool:
    """Returns True if removed, False if not found."""
    try:
        existing = _table("TikThook Subscribers").all(
            formula=f"{{CHAT_ID}}={chat_id}", fields=["CHAT_ID"]
        )
        if not existing:
            return False
        for r in existing:
            _table("TikThook Subscribers").delete(r["id"])
        return True
    except Exception as e:
        logger.error("remove_subscriber failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Telegram — group chat IDs
# ---------------------------------------------------------------------------

async def get_group_chat_ids() -> list[int]:
    """Returns all Telegram group chat IDs from the TikThook Groups table."""
    try:
        records = _table("TikThook Groups").all(fields=["CHAT_ID"])
        return [int(r["fields"]["CHAT_ID"]) for r in records if "CHAT_ID" in r["fields"]]
    except Exception as e:
        logger.error("get_group_chat_ids failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Discord channels
# ---------------------------------------------------------------------------

async def get_discord_channels() -> list[tuple[int, int]]:
    """Returns list of (guild_id, channel_id) from TikThook Discord Channels."""
    try:
        records = _table("TikThook Discord Channels").all(fields=["GUILD_ID", "CHANNEL_ID"])
        result = []
        for r in records:
            gid = r["fields"].get("GUILD_ID")
            cid = r["fields"].get("CHANNEL_ID")
            if gid and cid:
                result.append((int(gid), int(cid)))
        return result
    except Exception as e:
        logger.error("get_discord_channels failed: %s", e)
        return []


async def set_discord_channel(guild_id: int, channel_id: int, guild_name: str) -> bool:
    """Upsert: one entry per guild."""
    try:
        existing = _table("TikThook Discord Channels").all(
            formula=f"{{GUILD_ID}}={guild_id}", fields=["GUILD_ID"]
        )
        data = {"GUILD_ID": guild_id, "CHANNEL_ID": channel_id, "GUILD_NAME": guild_name}
        if existing:
            _table("TikThook Discord Channels").update(existing[0]["id"], data)
        else:
            _table("TikThook Discord Channels").create(data)
        return True
    except Exception as e:
        logger.error("set_discord_channel failed: %s", e)
        return False


async def remove_discord_channel(guild_id: int) -> bool:
    try:
        existing = _table("TikThook Discord Channels").all(
            formula=f"{{GUILD_ID}}={guild_id}", fields=["GUILD_ID"]
        )
        if not existing:
            return False
        for r in existing:
            _table("TikThook Discord Channels").delete(r["id"])
        return True
    except Exception as e:
        logger.error("remove_discord_channel failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Live state (in-memory — resets on restart, intentional:
# first poll after restart re-detects and re-notifies if still live)
# ---------------------------------------------------------------------------

_live_state: dict[str, bool] = {}


async def get_live_state() -> dict[str, bool]:
    return dict(_live_state)


async def set_live_state(username: str, is_live: bool) -> None:
    _live_state[username] = is_live


async def get_live_accounts() -> list[str]:
    return [u for u, v in _live_state.items() if v]
