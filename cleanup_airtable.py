#!/usr/bin/env python3
"""
Script de nettoyage Airtable — TikThook.

Supprime tout l'historique des tables :
  - TikThook Channels (channels, threads, assignations de comptes)
  - TikThook Subscribers (abonnés /start)

À exécuter après la mise en place de la nouvelle logique set live.
Structure conservée, données supprimées.

Usage:
  export AIRTABLE_TOKEN=ton_token
  python cleanup_airtable.py
  # ou depuis le venv du projet
"""

import asyncio
import logging
import os

# Optionnel : décommenter si tu utilises python-dotenv
# from dotenv import load_dotenv
# load_dotenv()

import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not os.environ.get("AIRTABLE_TOKEN"):
        logger.error("AIRTABLE_TOKEN manquant. Configure .env")
        return

    logger.info("Nettoyage Airtable TikThook...")
    n_ch = await storage.clear_all_channels()
    n_sub = await storage.clear_all_subscribers()
    logger.info("Terminé : TikThook Channels=%d, TikThook Subscribers=%d", n_ch, n_sub)


if __name__ == "__main__":
    asyncio.run(main())
