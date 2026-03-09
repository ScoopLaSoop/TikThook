"""
Persistent storage via Airtable (base: ALLURE AGENCY).

Tables used:
  TikThook             — COMPTE (username), NOM (display name),
                         👨‍💼 Team (link → Team table),
                         Telegram "Live" ID Channel (lookup from Team)
  TikThook Channels    — TYPE (TELEGRAM | DISCORD),
                           TELEGRAM: CHAT_ID (number), THREAD_ID (number, optional)
                           DISCORD:  GUILD (text), CHANNEL (text), GUILD_NAME (text)
  TikThook Subscribers — CHAT_ID (number)  [auto-managed via /start /stop]

Note: Discord IDs stored as text (GUILD/CHANNEL) to avoid JS float precision loss.
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

async def get_accounts() -> list[tuple[str, str, list[int]]]:
    """
    Returns list of (display_name, username, live_channel_ids).
    live_channel_ids: Telegram channel IDs from the linked Team member's
    'Telegram Live ID Channel' field. Empty list if no Team linked.
    """
    try:
        records = _table("TikThook").all(
            fields=["COMPTE", "NOM", 'Telegram "Live" ID Channel (from 👨‍💼 Team 2)']
        )
        accounts = []
        for r in records:
            username = r["fields"].get("COMPTE", "").strip()
            nom = r["fields"].get("NOM", username).strip()
            if not username:
                continue
            raw_ids = r["fields"].get('Telegram "Live" ID Channel (from 👨‍💼 Team 2)', [])
            live_channel_ids: list[int] = []
            for raw in (raw_ids if isinstance(raw_ids, list) else [raw_ids]):
                try:
                    if raw:
                        live_channel_ids.append(int(str(raw).strip()))
                except (ValueError, TypeError):
                    pass
            accounts.append((nom, username, live_channel_ids))
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
# TikThook Channels — Telegram groups
# ---------------------------------------------------------------------------

async def get_telegram_channels() -> list[tuple[int, int | None]]:
    """
    Returns list of (chat_id, thread_id) for all TELEGRAM entries.
    thread_id is None for regular groups; set it to target a specific forum topic.
    """
    try:
        records = _table("TikThook Channels").all(
            formula='{TYPE}="TELEGRAM"',
            fields=["CHAT_ID", "THREAD_ID"],
        )
        result = []
        for r in records:
            raw_chat = r["fields"].get("CHAT_ID")
            if raw_chat is None:
                continue
            thread_id = r["fields"].get("THREAD_ID")
            result.append((int(raw_chat), int(thread_id) if thread_id else None))
        return result
    except Exception as e:
        logger.error("get_telegram_channels failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# TikThook Channels — Discord channels
# ---------------------------------------------------------------------------

async def get_discord_channels() -> list[tuple[int, int]]:
    """Returns list of (guild_id, channel_id) for all DISCORD entries."""
    try:
        records = _table("TikThook Channels").all(
            formula='{TYPE}="DISCORD"',
            fields=["GUILD", "CHANNEL"],
        )
        result = []
        for r in records:
            gid = r["fields"].get("GUILD")
            cid = r["fields"].get("CHANNEL")
            if gid and cid:
                result.append((int(gid), int(cid)))
        return result
    except Exception as e:
        logger.error("get_discord_channels failed: %s", e)
        return []


async def set_discord_channel(guild_id: int, channel_id: int, guild_name: str) -> bool:
    """Upsert: one entry per guild."""
    try:
        existing = _table("TikThook Channels").all(
            formula=f'AND({{TYPE}}="DISCORD", {{GUILD}}="{guild_id}")',
            fields=["GUILD"],
        )
        data = {
            "TYPE": "DISCORD",
            "GUILD": str(guild_id),
            "CHANNEL": str(channel_id),
            "GUILD_NAME": guild_name,
        }
        if existing:
            _table("TikThook Channels").update(existing[0]["id"], data)
        else:
            _table("TikThook Channels").create(data)
        return True
    except Exception as e:
        logger.error("set_discord_channel failed: %s", e)
        return False


async def remove_discord_channel(guild_id: int) -> bool:
    try:
        existing = _table("TikThook Channels").all(
            formula=f'AND({{TYPE}}="DISCORD", {{GUILD}}="{guild_id}")',
            fields=["GUILD"],
        )
        if not existing:
            return False
        for r in existing:
            _table("TikThook Channels").delete(r["id"])
        return True
    except Exception as e:
        logger.error("remove_discord_channel failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# Live state (in-memory — resets on restart, intentional)
# ---------------------------------------------------------------------------

_live_state: dict[str, bool] = {}


async def get_live_state() -> dict[str, bool]:
    return dict(_live_state)


async def set_live_state(username: str, is_live: bool) -> None:
    _live_state[username] = is_live


async def get_live_accounts() -> list[str]:
    return [u for u, v in _live_state.items() if v]
