"""
Discord bot for TikThook live notifications.

Slash commands:
  /tikthook set    — set the current channel as the notification channel for this server
  /tikthook remove — stop notifications for this server
  /tikthook status — see which TikTok accounts are currently live
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

    async def setup_hook(self) -> None:
        await self.tree.sync()
        logger.info("Discord slash commands synced globally.")

    async def on_ready(self) -> None:
        logger.info("Discord bot ready — logged in as %s (id=%s)", self.user, self.user.id)


bot = TikThookBot()


# ---------------------------------------------------------------------------
# Slash command group: /tikthook
# ---------------------------------------------------------------------------

group = app_commands.Group(name="tikthook", description="Gestion des notifications TikTok Live")


@group.command(name="set", description="Définir ce channel pour les notifications TikTok Live")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_set(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    channel = interaction.channel
    ok = await storage.set_discord_channel(guild.id, channel.id, guild.name)
    if ok:
        await interaction.response.send_message(
            f"✅ Ce channel **#{channel.name}** recevra désormais les notifications TikTok Live !\n"
            f"Utilise `/tikthook remove` pour désactiver.",
            ephemeral=False,
        )
        logger.info("Discord channel set: guild=%s (%s) channel=%s", guild.name, guild.id, channel.id)
    else:
        await interaction.response.send_message(
            "❌ Erreur lors de l'enregistrement. Réessaie.",
            ephemeral=True,
        )


@group.command(name="remove", description="Désactiver les notifications TikTok Live sur ce serveur")
@app_commands.checks.has_permissions(manage_channels=True)
async def cmd_remove(interaction: discord.Interaction) -> None:
    removed = await storage.remove_discord_channel(interaction.guild.id)
    if removed:
        await interaction.response.send_message(
            "⚫ Notifications TikTok Live désactivées pour ce serveur.",
            ephemeral=False,
        )
    else:
        await interaction.response.send_message(
            "Aucune notification n'était configurée pour ce serveur.",
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
    await interaction.response.send_message(text, ephemeral=False)


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
    channels = await storage.get_discord_channels()
    if not channels:
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

    logger.info("📨 Discord — envoi à %d serveur(s)...", len(channels))
    for guild_id, channel_id in channels:
        channel = bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await bot.fetch_channel(channel_id)
            except Exception as exc:
                logger.warning("Discord: channel %s introuvable: %s", channel_id, exc)
                continue
        try:
            await channel.send(embed=embed)
            logger.info("  ✅ Discord envoyé → guild=%s channel=%s", guild_id, channel_id)
        except Exception as exc:
            logger.warning("  ❌ Discord échec → channel=%s: %s", channel_id, exc)
