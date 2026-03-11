"""
Persistent storage via Airtable (base: ALLURE AGENCY).

Tables used:
  TikThook PUSH LIVE 🟢 — COMPTE (username), NOM (display name)
                         (Team / Telegram Live ID retiré — Telegram = uniquement /setlive)
  TikThook Channels    — TYPE (TELEGRAM | DISCORD),
                         TIKTOK_ACCOUNT (username, empty = global)
                           TELEGRAM: CHAT_ID (number), THREAD_ID (number, optional)
                           DISCORD:  GUILD (text), CHANNEL (text), GUILD_NAME (text)
  TikThook Subscribers — CHAT_ID (number)  [auto-managed via /start /stop]

Routing logic (priorité absolue setlive > global):
  - Un compte set live = UN SEUL thread/channel (Telegram ou Discord)
  - Set live dans un thread → retirer ce compte de TOUS les autres (threads, globaux)
  - Telegram : uniquement /setlive (pas de global)
  - Discord : set global exclut les comptes déjà set live ailleurs

Note: Discord IDs stored as text (GUILD/CHANNEL) to avoid JS float precision loss.
"""
from __future__ import annotations

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

def _username_from_record(r: dict) -> str:
    """Extract TikTok username from record; tries COMPTE, Compte, Username."""
    fields = r.get("fields", {})
    for key in ("COMPTE", "Compte", "compte", "Username", "username"):
        val = fields.get(key)
        if val and str(val).strip():
            return str(val).strip().lstrip("@")
    return ""


async def get_accounts() -> list[tuple[str, str, list[int]]]:
    """
    Returns list of (display_name, username, live_channel_ids).
    live_channel_ids: toujours [] — Team retiré, Telegram = uniquement /setlive.
    """
    try:
        records = _table("TikThook PUSH LIVE 🟢").all()
        accounts = []
        for r in records:
            username = _username_from_record(r)
            if not username:
                logger.warning(
                    "TikThook PUSH LIVE 🟢: record %s ignoré — aucun username (COMPTE/Compte vide)",
                    r.get("id", "?"),
                )
                continue
            fields = r["fields"]
            nom = (
                fields.get("NOM") or fields.get("Nom") or fields.get("nom") or username
            )
            nom = str(nom).strip()
            accounts.append((nom, username, []))
        return accounts
    except Exception as e:
        logger.exception("get_accounts failed: %s", e)
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
# TikThook Channels — Telegram (global + per-account)
# ---------------------------------------------------------------------------

def _parse_tg_record(r: dict) -> tuple[int, int | None, str]:
    """Returns (chat_id, thread_id, tiktok_account) from a TikThook Channels record."""
    chat_id = int(r["fields"]["CHAT_ID"])
    raw_thread = r["fields"].get("THREAD_ID")
    thread_id = int(raw_thread) if raw_thread else None
    account = r["fields"].get("TIKTOK_ACCOUNT", "").strip().lower().lstrip("@")
    return chat_id, thread_id, account


async def get_telegram_channels(username: str | None = None) -> list[tuple[int, int | None]]:
    """
    Returns (chat_id, thread_id) list for Telegram destinations.
    - If username is given: returns global channels + channels specifically for that account.
    - If username is None: returns only global channels.
    """
    global_ch, per_acc = await get_telegram_channels_split(username)
    return global_ch + per_acc


async def get_telegram_channels_split(
    username: str | None,
) -> tuple[list[tuple[int, int | None]], list[tuple[int, int | None]]]:
    """
    Returns (global_channels, per_account_channels).
    - global: TIKTOK_ACCOUNT empty → receive ALL accounts
    - per_account: TIKTOK_ACCOUNT set → receive ONLY that account
    """
    try:
        records = _table("TikThook Channels").all(
            formula='{TYPE}="TELEGRAM"',
            fields=["CHAT_ID", "THREAD_ID", "TIKTOK_ACCOUNT"],
        )
        global_list: list[tuple[int, int | None]] = []
        per_account_list: list[tuple[int, int | None]] = []
        clean = (username or "").lower().lstrip("@")
        for r in records:
            if "CHAT_ID" not in r["fields"]:
                continue
            chat_id, thread_id, account = _parse_tg_record(r)
            if account == "":
                global_list.append((chat_id, thread_id))
            elif clean and account == clean:
                per_account_list.append((chat_id, thread_id))
        return global_list, per_account_list
    except Exception as e:
        logger.error("get_telegram_channels_split failed: %s", e)
        return [], []


async def remove_account_from_all_channels(username: str) -> int:
    """
    Remove this account from ALL TikThook Channels (Telegram + Discord).
    Used when setting live: one account = one destination only.
    Returns number of records deleted.
    """
    try:
        clean = username.strip().lower().lstrip("@")
        if not clean:
            return 0
        formula = f'AND({{TIKTOK_ACCOUNT}}="{clean}", OR({{TYPE}}="TELEGRAM", {{TYPE}}="DISCORD"))'
        records = _table("TikThook Channels").all(formula=formula, fields=["id"])
        for r in records:
            _table("TikThook Channels").delete(r["id"])
        return len(records)
    except Exception as e:
        logger.error("remove_account_from_all_channels failed: %s", e)
        return 0


async def account_has_setlive_anywhere(username: str) -> bool:
    """True if this account has per-account routing in Telegram or Discord."""
    try:
        clean = (username or "").strip().lower().lstrip("@")
        if not clean:
            return False
        formula = f'AND({{TIKTOK_ACCOUNT}}="{clean}", OR({{TYPE}}="TELEGRAM", {{TYPE}}="DISCORD"))'
        records = _table("TikThook Channels").all(formula=formula, fields=["id"], max_records=1)
        return len(records) > 0
    except Exception as e:
        logger.error("account_has_setlive_anywhere failed: %s", e)
        return False


async def add_telegram_channel(
    chat_id: int,
    thread_id: int | None,
    description: str = "",
    tiktok_account: str = "",
) -> bool:
    """
    Register a Telegram group/topic for ONE specific account (setlive only).
    Règle 1: Retire ce compte de TOUS les autres threads et globaux avant d'ajouter.
    Returns True if added, False if already present for this exact (chat, thread, account).
    """
    try:
        clean_account = tiktok_account.strip().lower().lstrip("@")
        if not clean_account:
            logger.warning("add_telegram_channel: tiktok_account required (no global on Telegram)")
            return False

        # Règle 1: retirer ce compte de partout (Telegram + Discord)
        removed = await remove_account_from_all_channels(clean_account)
        if removed:
            logger.info("Removed @%s from %d other channel(s) before setlive", clean_account, removed)

        formula = f'AND({{TYPE}}="TELEGRAM", {{CHAT_ID}}={chat_id}'
        if thread_id is not None:
            formula += f", {{THREAD_ID}}={thread_id}"
        else:
            formula += ", OR({THREAD_ID}=BLANK(), {THREAD_ID}=\"\")"
        formula += f', {{TIKTOK_ACCOUNT}}="{clean_account}")'

        existing = _table("TikThook Channels").all(formula=formula, fields=["CHAT_ID"])
        if existing:
            return False

        data: dict = {"TYPE": "TELEGRAM", "CHAT_ID": chat_id, "TIKTOK_ACCOUNT": clean_account}
        if thread_id is not None:
            data["THREAD_ID"] = thread_id
        if description:
            data["DESCRIPTION"] = description
        _table("TikThook Channels").create(data)
        return True
    except Exception as e:
        logger.error("add_telegram_channel failed: %s", e)
        return False


async def remove_telegram_channel(
    chat_id: int,
    thread_id: int | None,
    tiktok_account: str = "",
) -> bool:
    """Remove a Telegram group/topic entry (setlive only — tiktok_account required)."""
    try:
        clean_account = tiktok_account.strip().lower().lstrip("@")
        if not clean_account:
            return False
        formula = f'AND({{TYPE}}="TELEGRAM", {{CHAT_ID}}={chat_id}'
        if thread_id is not None:
            formula += f", {{THREAD_ID}}={thread_id}"
        else:
            formula += ", OR({THREAD_ID}=BLANK(), {THREAD_ID}=\"\")"
        formula += f', {{TIKTOK_ACCOUNT}}="{clean_account}")'

        existing = _table("TikThook Channels").all(formula=formula, fields=["CHAT_ID"])
        if not existing:
            return False
        for r in existing:
            _table("TikThook Channels").delete(r["id"])
        return True
    except Exception as e:
        logger.error("remove_telegram_channel failed: %s", e)
        return False


# ---------------------------------------------------------------------------
# TikThook Channels — Discord (global + per-account)
# ---------------------------------------------------------------------------

async def get_discord_channels(username: str | None = None) -> list[tuple[int, int]]:
    """
    Returns (guild_id, channel_id) list for Discord destinations.
    - If username is given: returns global channels + channels for that account.
    - If username is None: returns only global channels.
    """
    global_ch, per_acc = await get_discord_channels_split(username)
    return global_ch + per_acc


async def get_discord_channels_split(
    username: str | None,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """
    Returns (global_channels, per_account_channels).
    - global: TIKTOK_ACCOUNT empty → receive ALL accounts
    - per_account: TIKTOK_ACCOUNT set → receive ONLY that account
    """
    try:
        records = _table("TikThook Channels").all(
            formula='{TYPE}="DISCORD"',
            fields=["GUILD", "CHANNEL", "TIKTOK_ACCOUNT"],
        )
        global_list: list[tuple[int, int]] = []
        per_account_list: list[tuple[int, int]] = []
        clean = (username or "").lower().lstrip("@")
        for r in records:
            gid = r["fields"].get("GUILD")
            cid = r["fields"].get("CHANNEL")
            if not gid or not cid:
                continue
            try:
                pair = (int(str(gid)), int(str(cid)))
            except (ValueError, TypeError):
                logger.warning("Discord record invalide: GUILD=%s CHANNEL=%s", gid, cid)
                continue
            account = r["fields"].get("TIKTOK_ACCOUNT", "").strip().lower().lstrip("@")
            if account == "":
                global_list.append(pair)
            elif clean and account == clean:
                per_account_list.append(pair)
        return global_list, per_account_list
    except Exception as e:
        logger.error("get_discord_channels_split failed: %s", e)
        return [], []


async def set_discord_channel(
    guild_id: int,
    channel_id: int,
    guild_name: str,
    tiktok_account: str = "",
) -> bool:
    """
    Upsert a Discord channel entry.
    - Global (tiktok_account empty): receives accounts without setlive elsewhere.
    - Setlive (tiktok_account set): Règle 1+3 — retire ce compte de partout avant d'ajouter.
    """
    try:
        clean_account = tiktok_account.strip().lower().lstrip("@")

        if clean_account:
            # Règle 1: retirer ce compte de tous les channels (Telegram + Discord)
            removed = await remove_account_from_all_channels(clean_account)
            if removed:
                logger.info("Removed @%s from %d other channel(s) before Discord setlive", clean_account, removed)

        formula = f'AND({{TYPE}}="DISCORD", {{GUILD}}="{guild_id}"'
        if clean_account:
            formula += f', {{TIKTOK_ACCOUNT}}="{clean_account}"'
        else:
            formula += ', {TIKTOK_ACCOUNT}=""'
        formula += ")"

        existing = _table("TikThook Channels").all(formula=formula, fields=["GUILD"])
        data: dict = {
            "TYPE": "DISCORD",
            "GUILD": str(guild_id),
            "CHANNEL": str(channel_id),
            "GUILD_NAME": guild_name,
        }
        if clean_account:
            data["TIKTOK_ACCOUNT"] = clean_account
        if existing:
            _table("TikThook Channels").update(existing[0]["id"], data)
        else:
            _table("TikThook Channels").create(data)
        return True
    except Exception as e:
        logger.error("set_discord_channel failed: %s", e)
        return False


async def remove_discord_channel(guild_id: int, tiktok_account: str = "") -> bool:
    try:
        clean_account = tiktok_account.strip().lower().lstrip("@")
        formula = f'AND({{TYPE}}="DISCORD", {{GUILD}}="{guild_id}"'
        if clean_account:
            formula += f', {{TIKTOK_ACCOUNT}}="{clean_account}"'
        else:
            formula += ', {TIKTOK_ACCOUNT}=""'
        formula += ")"

        existing = _table("TikThook Channels").all(formula=formula, fields=["GUILD"])
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


# ---------------------------------------------------------------------------
# Airtable cleanup (channels, threads, assignations)
# ---------------------------------------------------------------------------

async def clear_all_channels() -> int:
    """Delete all records from TikThook Channels. Returns count deleted."""
    try:
        records = _table("TikThook Channels").all(fields=["TYPE"])
        for r in records:
            _table("TikThook Channels").delete(r["id"])
        n = len(records)
        logger.info("Cleared TikThook Channels: %d record(s) deleted", n)
        return n
    except Exception as e:
        logger.error("clear_all_channels failed: %s", e)
        return 0


async def clear_all_subscribers() -> int:
    """Delete all records from TikThook Subscribers. Returns count deleted."""
    try:
        records = _table("TikThook Subscribers").all(fields=["CHAT_ID"])
        for r in records:
            _table("TikThook Subscribers").delete(r["id"])
        n = len(records)
        logger.info("Cleared TikThook Subscribers: %d record(s) deleted", n)
        return n
    except Exception as e:
        logger.error("clear_all_subscribers failed: %s", e)
        return 0
