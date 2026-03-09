"""
Telegram bot handlers and notification sender.

Commands:
    /start  — subscribe to live notifications
    /stop   — unsubscribe
    /status — list accounts currently live
    /id     — get current chat ID (to add to TikThook Groups in Airtable)
"""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from config import TELEGRAM_TOKEN
import storage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    added = await storage.add_subscriber(chat_id)
    if added:
        await update.message.reply_text(
            "Tu es maintenant abonné(e) aux notifications TikTok Live ! 🔔\n"
            "Tu recevras un message dès qu'un compte surveille passe en live.\n\n"
            "Utilise /stop pour te désabonner."
        )
    else:
        await update.message.reply_text(
            "Tu es déjà abonné(e). Utilise /stop pour te désabonner."
        )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    removed = await storage.remove_subscriber(chat_id)
    if removed:
        await update.message.reply_text(
            "Tu es désabonné(e). Tu ne recevras plus de notifications.\n"
            "Utilise /start pour te réabonner."
        )
    else:
        await update.message.reply_text(
            "Tu n'étais pas abonné(e). Utilise /start pour t'abonner."
        )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    live_accounts = await storage.get_live_accounts()
    if live_accounts:
        lines = "\n".join(f"🔴 @{u}" for u in live_accounts)
        text = f"*Comptes actuellement en live :*\n{lines}"
    else:
        text = "Aucun compte n'est actuellement en live."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    lines = [
        f"*Ton user ID :* `{user.id}`",
        f"*Chat ID (ce chat) :* `{chat.id}`",
        f"*Type de chat :* {chat.type}",
    ]
    if chat.title:
        lines.append(f"*Nom du groupe :* {chat.title}")
    lines.append(
        "\n➡️ Pour notifier ce groupe, ajoute ce *Chat ID* dans la table "
        "*TikThook Groups* de ta base Airtable (champ CHAT\\_ID)."
    )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# Notification sender (called by the monitor loop)
# ---------------------------------------------------------------------------

async def send_live_notification(
    app: Application,
    display_name: str,
    username: str,
    is_live: bool,
) -> None:
    status = "EN LIVE" if is_live else "FIN DE LIVE"
    logger.info("🔔 Transition détectée : @%s — %s", username, status)

    if is_live:
        text = f"🔴 *{display_name}* (@{username}) est en live sur TikTok !"
    else:
        text = f"⚫ *{display_name}* (@{username}) a terminé son live."

    seen: set = set()
    targets: list[int] = []

    # 1. All Telegram groups (global list from GROUPES_TELEGRAM + TikThook Groups table)
    for chat_id in await storage.get_all_telegram_groups():
        if chat_id not in seen:
            seen.add(chat_id)
            targets.append(chat_id)

    # 2. Individual subscribers (/start users)
    for chat_id in await storage.get_subscribers():
        if chat_id not in seen:
            seen.add(chat_id)
            targets.append(chat_id)

    if not targets:
        logger.warning(
            "⚠️  Notification @%s ignorée : 0 destinataires. "
            "Ajoute des groupes dans GROUPES_TELEGRAM ou 'TikThook Groups', ou fais /start.",
            username,
        )
        return

    logger.info("📨 Envoi à %d destinataire(s)...", len(targets))
    for target in targets:
        try:
            await app.bot.send_message(
                chat_id=target,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
            logger.info("  ✅ Envoyé à %s", target)
        except Exception as exc:
            logger.warning("  ❌ Échec envoi à %s: %s", target, exc)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def build_application() -> Application:
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("id", cmd_id))
    return app
