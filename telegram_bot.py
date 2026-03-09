"""
Telegram bot handlers and notification sender.

Commands:
    /start      — subscribe to live notifications
    /stop       — unsubscribe
    /status     — list accounts currently live
    /id         — get current chat ID and thread ID
    /addgroup    — register this group/topic to receive notifications (admin only)
    /removegroup — unregister this group/topic (admin only)
    /help        — show all commands and best practices
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

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    added = await storage.add_subscriber(chat_id)
    if added:
        await update.message.reply_text(
            "Tu es maintenant abonné(e) aux notifications TikTok Live ! 🔔\n"
            "Tu recevras un message dès qu'un compte surveillé passe en live.\n\n"
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
            "\n➡️ Utilise `/addgroup` directement ici pour enregistrer ce "
            + ("topic" if thread_id else "groupe")
            + " automatiquement."
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# Help command
# ---------------------------------------------------------------------------

HELP_TEXT = (
    "🤖 <b>TikThook — Notifications TikTok Live</b>\n"
    "\n"
    "👤 <b>En privé (abonnement personnel)</b>\n"
    "• /start — Recevoir les notifs dans ce chat\n"
    "• /stop — Arrêter de recevoir les notifs\n"
    "• /status — Voir qui est en live en ce moment\n"
    "\n"
    "👥 <b>Dans un groupe (admin uniquement)</b>\n"
    "• /addgroup — Enregistrer ce groupe/topic pour recevoir les notifs\n"
    "• /removegroup — Désactiver les notifs pour ce groupe/topic\n"
    "\n"
    "🔧 <b>Utilitaire</b>\n"
    "• /id — Afficher l'ID de ce chat et du topic\n"
    "• /help — Afficher ce message\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📋 <b>Bonnes pratiques Telegram</b>\n"
    "\n"
    "✅ Ajoute le bot comme <b>administrateur</b> du groupe avant de faire /addgroup\n"
    "✅ Groupe avec topics (forum) ? Tape /addgroup <b>directement dans le topic</b> voulu — le bot cible ce topic automatiquement\n"
    "✅ Un seul /start suffit — pas besoin de le refaire à chaque connexion\n"
    "✅ /status pour voir en temps réel qui est en live\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "🎮 <b>Bonnes pratiques Discord</b>\n"
    "\n"
    "✅ Invite le bot avec les permissions <b>Envoyer des messages</b> et <b>Lire les messages</b>\n"
    "✅ Va dans le channel cible et tape <code>/tikthook set</code>\n"
    "✅ <code>/tikthook remove</code> pour désactiver sur ce serveur\n"
    "✅ <code>/tikthook status</code> pour voir les comptes en live depuis Discord\n"
    "✅ Nécessite la permission <b>Gérer les channels</b>"
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


async def cmd_addgroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Seuls les admins peuvent enregistrer ce groupe.")
        return

    chat = update.effective_chat
    msg = update.message
    thread_id = msg.message_thread_id if msg else None

    if chat.type == "private":
        await update.message.reply_text(
            "Cette commande doit être utilisée dans un groupe, pas en privé."
        )
        return

    description = chat.title or ""
    added = await storage.add_telegram_channel(chat.id, thread_id, description)

    if added:
        topic_info = f" (topic `{thread_id}`)" if thread_id else ""
        await update.message.reply_text(
            f"✅ Ce groupe{topic_info} recevra désormais les notifications TikTok Live !\n"
            f"Utilise /removegroup pour désactiver.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            "Ce groupe est déjà enregistré. Utilise /removegroup pour le retirer."
        )


async def cmd_removegroup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _is_admin(update, context):
        await update.message.reply_text("❌ Seuls les admins peuvent retirer ce groupe.")
        return

    chat = update.effective_chat
    msg = update.message
    thread_id = msg.message_thread_id if msg else None

    removed = await storage.remove_telegram_channel(chat.id, thread_id)

    if removed:
        await update.message.reply_text(
            "⚫ Ce groupe ne recevra plus les notifications TikTok Live."
        )
    else:
        await update.message.reply_text(
            "Ce groupe n'était pas enregistré. Utilise /addgroup pour l'ajouter."
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

    seen: set[int] = set()
    targets: list[tuple[int, int | None]] = []

    # 1. Telegram channel lié à la modèle (Telegram "Live" ID Channel from Team)
    for chat_id in live_channel_ids:
        if chat_id not in seen:
            seen.add(chat_id)
            targets.append((chat_id, None))

    # 2. Groupes Telegram globaux (table TikThook Channels, TYPE=TELEGRAM)
    for chat_id, thread_id in await storage.get_telegram_channels():
        if chat_id not in seen:
            seen.add(chat_id)
            targets.append((chat_id, thread_id))

    # 3. Abonnés individuels (/start)
    for chat_id in await storage.get_subscribers():
        if chat_id not in seen:
            seen.add(chat_id)
            targets.append((chat_id, None))

    if not targets:
        logger.warning(
            "⚠️  Notification @%s ignorée : 0 destinataires. "
            "Lie un membre Team au compte TikThook, ajoute un groupe dans "
            "'TikThook Channels' (TYPE=TELEGRAM), ou fais /start.",
            username,
        )
        return

    logger.info("📨 Envoi Telegram à %d destinataire(s)...", len(targets))
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
    BotCommand("start",       "S'abonner aux notifications TikTok Live"),
    BotCommand("stop",        "Se désabonner des notifications"),
    BotCommand("status",      "Voir les comptes actuellement en live"),
    BotCommand("addgroup",    "Enregistrer ce groupe/topic (admin)"),
    BotCommand("removegroup", "Désactiver les notifs pour ce groupe (admin)"),
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
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("addgroup", cmd_addgroup))
    app.add_handler(CommandHandler("removegroup", cmd_removegroup))
    app.add_handler(CommandHandler("help", cmd_help))
    return app


async def _register_commands(app: Application) -> None:
    await app.bot.set_my_commands(BOT_COMMANDS)
    logger.info("Bot commands registered with Telegram.")
