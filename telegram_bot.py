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
        lines.append(f"*Thread ID (topic actuel) :* `{thread_id}`")

    lines.append(
        "\n➡️ Dans Airtable *TikThook Channels*, ajoute une ligne avec :\n"
        "• *TYPE* = TELEGRAM\n"
        "• *CHAT\\_ID* = Chat ID du groupe\n"
        "• *THREAD\\_ID* = Thread ID du topic *(laisser vide pour le topic général)*"
    )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# Help command
# ---------------------------------------------------------------------------

HELP_TEXT = """
🤖 *TikThook — Bot de notifications TikTok Live*

*Commandes disponibles :*

👤 *En privé (abonnement personnel)*
• `/start` — Recevoir les notifs directement dans ce chat
• `/stop` — Arrêter de recevoir les notifs
• `/status` — Voir quels comptes sont en live en ce moment

👥 *Dans un groupe (admin uniquement)*
• `/addgroup` — Enregistrer ce groupe pour recevoir les notifs
  _→ Dans un forum : tape la commande dans le topic souhaité_
• `/removegroup` — Désactiver les notifs pour ce groupe

🔧 *Utilitaire*
• `/id` — Afficher l'ID de ce chat et du topic actuel
• `/help` — Afficher ce message

━━━━━━━━━━━━━━━━━━━━━━━
📋 *Bonnes pratiques Telegram*

✅ Ajoute le bot comme *administrateur* du groupe avant de faire `/addgroup` \(sinon il ne pourra pas envoyer de messages\)
✅ Pour les groupes avec *topics* \(forums\), tape `/addgroup` directement *dans le topic* qui recevra les notifs
✅ Un seul `/start` suffit par personne — pas besoin de le refaire à chaque connexion
✅ Utilise `/status` pour vérifier en temps réel qui est en live

━━━━━━━━━━━━━━━━━━━━━━━
🎮 *Bonnes pratiques Discord*

✅ Invite le bot sur ton serveur avec les permissions *Envoyer des messages* et *Lire les messages*
✅ Va dans le channel où tu veux recevoir les notifs et tape `/tikthook set`
✅ `/tikthook remove` pour désactiver sur ce serveur
✅ `/tikthook status` pour voir les comptes en live directement depuis Discord
✅ Seuls les membres avec la permission *Gérer les channels* peuvent configurer le bot
""".strip()


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN_V2)


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
    app.add_handler(CommandHandler("addgroup", cmd_addgroup))
    app.add_handler(CommandHandler("removegroup", cmd_removegroup))
    app.add_handler(CommandHandler("help", cmd_help))
    return app
