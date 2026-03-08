"""
TikThook — TikTok Live → Telegram notification bot
Entry point: starts the Telegram bot and the TikTok polling loop concurrently.
"""

import asyncio
import logging
import sys

from telegram.ext import Application

from telegram_bot import build_application, send_live_notification
from monitor import polling_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def run(app: Application) -> None:
    """Initialise the Telegram app, then run the bot and the monitor in parallel."""

    async def notify(display_name: str, username: str, is_live: bool) -> None:
        await send_live_notification(app, display_name, username, is_live)

    async with app:
        await app.start()
        logger.info("Telegram bot started — @TikThook_bot")

        # Run polling updater and TikTok monitor concurrently
        await asyncio.gather(
            app.updater.start_polling(drop_pending_updates=True),
            polling_loop(notify),
        )


def main() -> None:
    app = build_application()
    asyncio.run(run(app))


if __name__ == "__main__":
    main()
