import os

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "")

POLL_INTERVAL = 60  # seconds between each polling cycle

# Each entry: (display_name, tiktok_username)
# Multiple accounts per person — all are monitored independently.
ACCOUNTS: list[tuple[str, str]] = [
    # Roxane (iambby_roxane retiré — compte invalide selon TikTok)
    ("Roxane", "roxane_mn"),
    ("Roxane", "roxane_mneee"),
    # Elisa (drd_elisa0 retiré — compte invalide selon TikTok)
    ("Elisa", "lolaxkitty"),
    ("Elisa", "elisa.durand03"),
    # Cleo (Cleo_mrti et cleo.mrti retirés — comptes invalides selon TikTok)
    ("Cleo", "cleomrti01"),
    ("Cleo", "cleomrti02"),
    # Mel
    ("Mel", "mel_reels_x"),
    ("Mel", "myintimeside2.0"),
    ("Mel", "mel_bassin"),
    # Laly (Laly_chauvt et laly.chauvt retirés — comptes invalides selon TikTok)
    ("Laly", "chauvette7mc"),
    # Kath (Kathklf retiré — compte invalide selon TikTok)
    ("Kath", "kathelyn.klfoff"),
    # Iggpvv2katt
    ("Iggpvv2katt", "iggpvv2katt"),
]
