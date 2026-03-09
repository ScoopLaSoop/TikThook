"""
TikTok live monitor: polls all accounts from Airtable every POLL_INTERVAL seconds.
"""

import asyncio
import logging
import random
from typing import Callable, Coroutine, Any

from TikTokLive import TikTokLiveClient
from TikTokLive.client.errors import UserOfflineError

from config import POLL_INTERVAL
import storage

logger = logging.getLogger(__name__)

# (display_name, username, is_live, live_channel_ids)
NotifyCallback = Callable[[str, str, bool, list[int]], Coroutine[Any, Any, None]]


async def _check_account(
    display_name: str,
    username: str,
    live_channel_ids: list[int],
    notify: NotifyCallback,
) -> None:
    try:
        client = TikTokLiveClient(unique_id=username)
        currently_live = await client.is_live()
    except UserOfflineError:
        currently_live = False
    except Exception as exc:
        logger.warning("Error checking @%s: %s", username, exc)
        return

    previous_state = (await storage.get_live_state()).get(username, False)

    if currently_live == previous_state:
        return

    await storage.set_live_state(username, currently_live)

    try:
        await notify(display_name, username, currently_live, live_channel_ids)
    except Exception as exc:
        logger.error("Notify callback failed for @%s: %s", username, exc)


async def polling_loop(notify: NotifyCallback) -> None:
    logger.info("Monitor started — interval=%ds", POLL_INTERVAL)

    while True:
        accounts = await storage.get_accounts()
        if not accounts:
            logger.warning("No accounts found in Airtable TikThook table — retrying in %ds", POLL_INTERVAL)
            await asyncio.sleep(POLL_INTERVAL)
            continue

        logger.debug("Poll cycle — %d accounts to check", len(accounts))

        tasks = [
            _run_with_jitter(name, username, live_channel_ids, notify, random.uniform(0, 3))
            for name, username, live_channel_ids in accounts
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.sleep(POLL_INTERVAL)


async def _run_with_jitter(
    display_name: str,
    username: str,
    live_channel_ids: list[int],
    notify: NotifyCallback,
    delay: float,
) -> None:
    await asyncio.sleep(delay)
    await _check_account(display_name, username, live_channel_ids, notify)
