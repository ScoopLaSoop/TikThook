"""
TikTok live monitor: polls all accounts every POLL_INTERVAL seconds.

For each account it performs a lightweight HTTP check (is_live()) — no WebSocket
is opened unless the account is confirmed live. On state transitions it calls
the provided notify callback.
"""

import asyncio
import logging
import random
from typing import Callable, Coroutine, Any

from TikTokLive import TikTokLiveClient
from TikTokLive.client.errors import UserOfflineError

from config import ACCOUNTS, POLL_INTERVAL
import storage

logger = logging.getLogger(__name__)

NotifyCallback = Callable[[str, str, bool], Coroutine[Any, Any, None]]
# notify(display_name, username, is_live)


async def _check_account(
    display_name: str,
    username: str,
    notify: NotifyCallback,
) -> None:
    """Check one account and fire the notify callback on state changes."""
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
        return  # no transition — nothing to do

    await storage.set_live_state(username, currently_live)

    try:
        await notify(display_name, username, currently_live)
    except Exception as exc:
        logger.error("Notify callback failed for @%s: %s", username, exc)


async def polling_loop(notify: NotifyCallback) -> None:
    """
    Main monitoring loop. Runs forever, checking all accounts concurrently
    every POLL_INTERVAL seconds with a small per-account jitter to spread
    the HTTP burst.
    """
    logger.info("Monitor started — %d accounts, interval=%ds", len(ACCOUNTS), POLL_INTERVAL)

    while True:
        tasks = []
        for display_name, username in ACCOUNTS:
            jitter = random.uniform(0, 3)
            tasks.append(_run_with_jitter(display_name, username, notify, jitter))

        await asyncio.gather(*tasks, return_exceptions=True)
        logger.debug("Poll cycle complete — sleeping %ds", POLL_INTERVAL)
        await asyncio.sleep(POLL_INTERVAL)


async def _run_with_jitter(
    display_name: str,
    username: str,
    notify: NotifyCallback,
    delay: float,
) -> None:
    await asyncio.sleep(delay)
    await _check_account(display_name, username, notify)
