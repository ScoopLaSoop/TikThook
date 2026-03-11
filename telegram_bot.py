"""
Telegram bot handlers and notification sender.

Commands:
    /status      — list accounts currently live
    /id          — get current chat ID and thread ID
    /setlive     — register this topic for a SPECIFIC account (admin only)
    /removelive  — unregister per-account routing (admin only)
    /help        — show all commands and best practices

Telegram = uniquement /setlive. Pas d'abonnés, pas de Team.
"""

import logging

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode

from config import TELEGRAM_TOKEN
import storage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

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
    msg = update.message
    thread_id = msg.message_thread_id if msg else None

    lines = [
        f"*Ton user ID :* `{user.id}`",
        f"*Chat ID (ce chat) :* `{chat.id}`",
        f"*Type de chat :* {chat.type}",
    ]
    if chat.title:
        lines.append(f"*Nom du groupe :* {chat.title}")
    if thread_id:
        lines.append(f"*Topic ID (ce topic) :* `{thread_id}`")

    if chat.type != "private":
        lines.append(
            "\n➡️ Utilise `/setlive username` dans ce topic pour recevoir les notifs d'un compte."
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# Help command
# ---------------------------------------------------------------------------

HELP_TEXT = (
    "🤖 <b>TikThook — Notifications TikTok Live</b>\n"
    "\n"
    "🎯 <b>Telegram — uniquement /setlive</b>\n"
    "• /setlive <code>username</code> — Ce topic reçoit les notifs uniquement pour ce compte\n"
    "  <i>ex : /setlive roxane_mn</i>\n"
    "• /removelive <code>username</code> — Supprimer ce routage\n"
    "\n"
    "🔧 <b>Utilitaire</b>\n"
    "• /status — Voir qui est en live en ce moment\n"
    "• /id — Afficher l'ID de ce chat et du topic\n"
    "• /help — Afficher ce message\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📋 <b>Bonnes pratiques</b>\n"
    "\n"
    "✅ Ajoute le bot comme <b>administrateur</b> avant toute commande\n"
    "✅ Chaque compte = un seul topic. /setlive retire le compte des autres topics.\n"
    "✅ Tape <code>/setlive username</code> dans le topic cible\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🎮 <b>Discord</b>\n"
    "\n"
    "✅ <code>/tikthook set</code> → toutes les notifs (sauf comptes set live ailleurs)\n"
    "✅ <code>/tikthook setlive username</code> → notifs d'un seul compte\n"
)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# Group registration commands (admin only)
# ---------------------------------------------------------------------------

async def _is_admin(update: Update, context) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if chat.type == "private":
        return True
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def cmd_setlive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Register this group/topic for notifications of ONE specific TikTok account."""
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Seuls les admins peuvent configurer les notifications.")
        return

    if update.effective_chat.type == "private":
        await update.message.reply_text(
            "Cette commande doit être utilisée dans un groupe.\n"
            "Ex : /setlive roxane_mn"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Usage : <code>/setlive username</code>\n"
            "Ex : <code>/setlive roxane_mn</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    username = context.args[0].lstrip("@").strip()
    chat = update.effective_chat
    msg = update.message
    thread_id = msg.message_thread_id if msg else None
    description = chat.title or ""

    added = await storage.add_telegram_channel(chat.id, thread_id, description, tiktok_account=username)

    topic_info = f" (topic <code>{thread_id}</code>)" if thread_id else ""
    if added:
        await update.message.reply_text(
            f"✅ Ce topic{topic_info} recevra les notifs uniquement pour <b>@{username}</b> "
            f"(retiré des autres topics).\n"
            f"Utilise <code>/removelive {username}</code> pour désactiver.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"Ce routage existe déjà pour @{username}. "
            f"Utilise <code>/removelive {username}</code> pour le retirer.",
            parse_mode=ParseMode.HTML,
        )


async def cmd_removelive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove per-account routing for a specific TikTok account."""
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Seuls les admins peuvent modifier les notifications.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage : <code>/removelive username</code>\n"
            "Ex : <code>/removelive roxane_mn</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    username = context.args[0].lstrip("@").strip()
    chat = update.effective_chat
    msg = update.message
    thread_id = msg.message_thread_id if msg else None

    removed = await storage.remove_telegram_channel(chat.id, thread_id, tiktok_account=username)

    if removed:
        await update.message.reply_text(
            f"⚫ Routage supprimé pour <b>@{username}</b> sur ce topic.",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            f"Aucun routage trouvé pour @{username} sur ce topic.",
        )


# ---------------------------------------------------------------------------
# Notification sender (called by the monitor loop)
# ---------------------------------------------------------------------------

async def send_live_notification(
    app: Application,
    display_name: str,
    username: str,
    is_live: bool,
    live_channel_ids: list[int],
) -> None:
    status = "EN LIVE" if is_live else "FIN DE LIVE"
    logger.info("🔔 Transition détectée : @%s — %s", username, status)

    if is_live:
        text = f"🔴 *{display_name}* (@{username}) est en live sur TikTok !"
    else:
        text = f"⚫ *{display_name}* (@{username}) a terminé son live."

    seen: set[tuple[int, int | None]] = set()
    targets: list[tuple[int, int | None]] = []

    def _add(cid: int, tid: int | None) -> None:
        key = (cid, tid)
        if key not in seen:
            seen.add(key)
            targets.append((cid, tid))

    # Telegram = uniquement /setlive (pas de Team, pas d'abonnés)
    _, per_acc = await storage.get_telegram_channels_split(username)
    for chat_id, thread_id in per_acc:
        _add(chat_id, thread_id)

    if not targets:
        logger.warning(
            "⚠️  Notification @%s ignorée : 0 destinataires. "
            "Fais /setlive %s dans un topic Telegram.",
            username, username,
        )
        return

    logger.info(
        "📨 Envoi Telegram @%s → %d dest. (setlive)",
        username, len(targets),
    )
    for chat_id, thread_id in targets:
        try:
            kwargs: dict = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": ParseMode.MARKDOWN,
            }
            if thread_id:
                kwargs["message_thread_id"] = thread_id
            await app.bot.send_message(**kwargs)
            logger.info("  ✅ Envoyé à %s (thread=%s)", chat_id, thread_id)
        except Exception as exc:
            logger.warning("  ❌ Échec envoi à %s: %s", chat_id, exc)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

BOT_COMMANDS = [
    BotCommand("status",      "Voir les comptes actuellement en live"),
    BotCommand("setlive",     "Ce topic reçoit les notifs uniquement pour ce compte (admin)"),
    BotCommand("removelive",  "Supprimer le routage de ce compte sur ce topic (admin)"),
    BotCommand("id",          "Afficher l'ID de ce chat et du topic"),
    BotCommand("help",        "Aide et bonnes pratiques"),
]


def build_application() -> Application:
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(_register_commands)
        .build()
    )
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("setlive", cmd_setlive))
    app.add_handler(CommandHandler("removelive", cmd_removelive))
    app.add_handler(CommandHandler("help", cmd_help))
    return app


async def _register_commands(app: Application) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands registered with Telegram.")
