"""
TikThook — TikTok Live → Telegram + Discord notification bot
Entry point: starts both bots and the TikTok polling loop concurrently.
"""

import asyncio
import logging
import sys

from telegram.ext import Application

from telegram_bot import build_application, send_live_notification
from discord_bot import bot as discord_bot, send_discord_notification, DISCORD_TOKEN
from monitor import polling_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def run(app: Application) -> None:
    async def notify(display_name: str, username: str, is_live: bool, group_ids: list[int]) -> None:
        await asyncio.gather(
            send_live_notification(app, display_name, username, is_live, group_ids),
            send_discord_notification(display_name, username, is_live),
        )

    async with app:
        await app.start()
        logger.info("Telegram bot started — @TikThook_bot")

        await asyncio.gather(
            app.updater.start_polling(drop_pending_updates=True),
            discord_bot.start(DISCORD_TOKEN),
            polling_loop(notify),
        )


def main() -> None:
    app = build_application()
    asyncio.run(run(app))


if __name__ == "__main__":
    main()
