"""
Discord bot for TikThook live notifications.

Slash commands:
  /tikthook set              — all accounts → this channel (global)
  /tikthook remove           — remove global routing for this server
  /tikthook setlive username — one account → this channel (per-account)
  /tikthook removelive username — remove per-account routing
  /tikthook status           — see which TikTok accounts are currently live
  /tikthook help             — show all commands and best practices
"""

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands

import storage

logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]


class TikThookBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self) -> None:
        logger.info("Discord bot ready — logged in as %s (id=%s)", self.user, self.user.id)
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                logger.info("Commands synced to guild: %s (%s)", guild.name, guild.id)
            except Exception as e:
                logger.warning("Failed to sync to guild %s: %s", guild.name, e)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        try:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Joined new guild — commands synced instantly: %s (%s)", guild.name, guild.id)
        except Exception as e:
            logger.warning("Failed to sync to new guild %s: %s", guild.name, e)


bot = TikThookBot()


# ---------------------------------------------------------------------------
# Slash command group: /tikthook
# ---------------------------------------------------------------------------

group = app_commands.Group(name="tikthook", description="Gestion des notifications TikTok Live")


@group.command(name="set", description="Ce channel reçoit les notifs de tous les comptes (sauf set live ailleurs)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_set(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    channel = interaction.channel
    ok = await storage.set_discord_channel(guild.id, channel.id, guild.name)
    if ok:
        await interaction.response.send_message(
            f"✅ **#{channel.name}** recevra les notifs de tous les comptes *sans* set live ailleurs.\n"
            f"Pour un seul compte : `/tikthook setlive username` — Pour désactiver : `/tikthook remove`",
        )
        logger.info("Discord global channel set: guild=%s channel=%s", guild.name, channel.id)
    else:
        await interaction.response.send_message("❌ Erreur. Réessaie.", ephemeral=True)


@group.command(name="remove", description="Désactiver les notifications globales pour ce serveur")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_remove(interaction: discord.Interaction) -> None:
    removed = await storage.remove_discord_channel(interaction.guild.id)
    if removed:
        await interaction.response.send_message("⚫ Notifications globales désactivées pour ce serveur.")
    else:
        await interaction.response.send_message(
            "Aucune notification globale configurée. "
            "Pour les routages par compte : `/tikthook removelive username`",
            ephemeral=True,
        )


@group.command(name="setlive", description="Ce channel reçoit les notifs d'un seul compte (retire des autres)")
@app_commands.describe(username="Nom du compte TikTok (sans @)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_setlive(interaction: discord.Interaction, username: str) -> None:
    guild = interaction.guild
    channel = interaction.channel
    clean = username.lstrip("@").strip()
    ok = await storage.set_discord_channel(guild.id, channel.id, guild.name, tiktok_account=clean)
    if ok:
        await interaction.response.send_message(
            f"✅ **#{channel.name}** recevra les notifs uniquement pour **@{clean}** (retiré des autres channels).\n"
            f"Pour supprimer : `/tikthook removelive {clean}`",
        )
        logger.info("Discord per-account channel set: guild=%s account=@%s channel=%s", guild.name, clean, channel.id)
    else:
        await interaction.response.send_message("❌ Erreur. Réessaie.", ephemeral=True)


@group.command(name="removelive", description="Supprimer le routage set live de ce compte")
@app_commands.describe(username="Nom du compte TikTok (sans @)")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_removelive(interaction: discord.Interaction, username: str) -> None:
    clean = username.lstrip("@").strip()
    removed = await storage.remove_discord_channel(interaction.guild.id, tiktok_account=clean)
    if removed:
        await interaction.response.send_message(
            f"⚫ Routage pour **@{clean}** supprimé sur ce serveur."
        )
    else:
        await interaction.response.send_message(
            f"Aucun routage trouvé pour @{clean} sur ce serveur.",
            ephemeral=True,
        )


@group.command(name="status", description="Voir les comptes TikTok actuellement en live")
async def cmd_status(interaction: discord.Interaction) -> None:
    live_accounts = await storage.get_live_accounts()
    if live_accounts:
        lines = "\n".join(f"🔴 @{u}" for u in live_accounts)
        text = f"**Comptes actuellement en live :**\n{lines}"
    else:
        text = "Aucun compte n'est actuellement en live."
    await interaction.response.send_message(text)


DISCORD_HELP_TEXT = (
    "🤖 **TikThook — Notifications TikTok Live**\n"
    "\n"
    "📡 **Toutes les notifications → ce channel (global)**\n"
    "• `/tikthook set` — Ce channel reçoit les notifs de tous les comptes *sans* set live ailleurs\n"
    "• `/tikthook remove` — Désactiver les notifs globales\n"
    "\n"
    "🎯 **Notifications → un seul compte (set live)**\n"
    "• `/tikthook setlive username` — Ce channel reçoit uniquement les notifs de ce compte\n"
    "  *ex : /tikthook setlive roxane_mn*\n"
    "• `/tikthook removelive username` — Supprimer ce routage\n"
    "\n"
    "🔧 **Utilitaire**\n"
    "• `/tikthook status` — Voir les comptes actuellement en live\n"
    "• `/tikthook help` — Afficher ce message\n"
    "\n"
    "━━━━━━━━━━━━━━━━━━━━━━━\n"
    "✅ **Priorité** : Un compte set live (Telegram ou Discord) n'apparaît jamais en global.\n"
    "• Set live retire le compte de partout avant de l'assigner à ce channel."
)


@group.command(name="help", description="Aide et liste des commandes TikThook")
async def cmd_help(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(DISCORD_HELP_TEXT, ephemeral=False)


@group.error
async def group_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "❌ Tu as besoin de la permission **Gérer les channels** pour faire ça.",
            ephemeral=True,
        )
    else:
        logger.error("Discord command error: %s", error)


bot.tree.add_command(group)


# ---------------------------------------------------------------------------
# Notification sender (called by monitor)
# ---------------------------------------------------------------------------

async def send_discord_notification(display_name: str, username: str, is_live: bool) -> None:
    global_ch, per_acc = await storage.get_discord_channels_split(username)
    if per_acc:
        channels = per_acc
    else:
        # Règle 3: set global exclut les comptes déjà set live ailleurs (Telegram ou Discord)
        if await storage.account_has_setlive_anywhere(username):
            channels = []
        else:
            channels = global_ch

    if not channels:
        logger.warning(
            "Discord: 0 channel configuré pour @%s — exécute /tikthook set dans le channel Allure",
            username,
        )
        return

    if is_live:
        embed = discord.Embed(
            title="🔴 Live TikTok !",
            description=f"**{display_name}** (@{username}) est en live sur TikTok !",
            color=discord.Color.red(),
            url=f"https://www.tiktok.com/@{username}/live",
        )
    else:
        embed = discord.Embed(
            title="⚫ Live terminé",
            description=f"**{display_name}** (@{username}) a terminé son live.",
            color=discord.Color.dark_gray(),
        )

    logger.info(
        "📨 Discord @%s — envoi à %d channel(s) (%s)",
        username,
        len(channels),
        "par compte" if per_acc else "global",
    )
    for guild_id, channel_id in channels:
        ch = bot.get_channel(channel_id)
        if ch is None:
            try:
                ch = await bot.fetch_channel(channel_id)
            except Exception as exc:
                logger.warning("Discord: channel %s introuvable: %s", channel_id, exc)
                continue
        try:
            await ch.send(content="@everyone", embed=embed)
            logger.info("  ✅ Discord envoyé → guild=%s channel=%s", guild_id, channel_id)
        except discord.Forbidden as exc:
            try:
                await ch.send(embed=embed)
                logger.info("  ✅ Discord envoyé (sans @everyone) → guild=%s channel=%s", guild_id, channel_id)
            except Exception as exc2:
                logger.warning("  ❌ Discord échec → guild=%s channel=%s: %s", guild_id, channel_id, exc2)
        except Exception as exc:
            logger.warning("  ❌ Discord échec → guild=%s channel=%s: %s", guild_id, channel_id, exc)
