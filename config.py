import os

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID", "")
STORAGE_PATH = os.environ.get("STORAGE_PATH", "storage.json")

POLL_INTERVAL = 60  # seconds between each polling cycle

# Each entry: (display_name, tiktok_username)
# Multiple accounts per person — all are monitored independently.
ACCOUNTS: list[tuple[str, str]] = [
    # Roxane
    ("Roxane", "iambby_roxane"),
    ("Roxane", "roxane_mn"),
    ("Roxane", "roxane_mneee"),
    # Elisa / Cleo
    ("Elisa", "lolaxkitty"),
    ("Elisa", "drd_elisa0"),
    ("Elisa", "elisa.durand03"),
    ("Cleo", "Cleo_mrti"),
    ("Cleo", "cleo.mrti"),
    ("Cleo", "cleomrti01"),
    ("Cleo", "cleomrti02"),
    # Mel
    ("Mel", "mel_reels_x"),
    ("Mel", "myintimeside2.0"),
    ("Mel", "mel_bassin"),
    # Laly
    ("Laly", "Laly_chauvt"),
    ("Laly", "laly.chauvt"),
    ("Laly", "chauvette7mc"),
    # Kath
    ("Kath", "Kathklf"),
    ("Kath", "kathelyn.klfoff"),
]
