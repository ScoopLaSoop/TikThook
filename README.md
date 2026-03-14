# TikThook

Bot de surveillance TikTok Live → notifications Telegram + Discord.
Détecte quand un compte TikTok passe en live ou le termine, et envoie une notification dans les bons channels.

---

## Prérequis

- Python 3.10+
- Un VPS Linux (Ubuntu 22.04 recommandé)
- Un bot Telegram (via [@BotFather](https://t.me/BotFather))
- Un bot Discord (via [Discord Developer Portal](https://discord.com/developers/applications))
- Un compte Airtable avec la base **ALLURE AGENCY** configurée
- `git` installé sur le VPS

---

## Installation sur VPS

### 1. Cloner le repo

```bash
git clone https://github.com/ton-user/tikthook.git
cd tikthook
```

### 2. Créer l'environnement virtuel et installer les dépendances

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configurer les variables d'environnement

Copier le fichier d'exemple et remplir les valeurs :

```bash
cp .env.example .env
nano .env
```

Contenu de `.env` :

```env
TELEGRAM_TOKEN=ton_token_telegram
AIRTABLE_TOKEN=ton_token_airtable
DISCORD_TOKEN=ton_token_discord
POLL_INTERVAL=60
```

| Variable | Description |
|----------|-------------|
| `TELEGRAM_TOKEN` | Token du bot Telegram (obtenu via @BotFather) |
| `AIRTABLE_TOKEN` | Personal Access Token Airtable (base : ALLURE AGENCY) |
| `DISCORD_TOKEN` | Token du bot Discord |
| `POLL_INTERVAL` | Intervalle de vérification en secondes (défaut : 60) |

### 4. Lancer le bot

**En test (premier lancement) :**

```bash
source venv/bin/activate
python main.py
```

**En production avec `systemd` (recommandé) :**

Créer le service :

```bash
sudo nano /etc/systemd/system/tikthook.service
```

Coller ce contenu (adapter les chemins) :

```ini
[Unit]
Description=TikThook Live Notification Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/tikthook
EnvironmentFile=/home/ubuntu/tikthook/.env
ExecStart=/home/ubuntu/tikthook/venv/bin/python main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Activer et démarrer :

```bash
sudo systemctl daemon-reload
sudo systemctl enable tikthook
sudo systemctl start tikthook
```

Vérifier que ça tourne :

```bash
sudo systemctl status tikthook
```

Voir les logs en temps réel :

```bash
sudo journalctl -u tikthook -f
```

---

## Structure Airtable

La base **ALLURE AGENCY** doit contenir ces tables :

| Table | Champs requis |
|-------|--------------|
| `TikThook PUSH LIVE 🟢` | `COMPTE` (username TikTok), `NOM` (texte), `👨‍💼 Team 2` (linked → `👨‍💼 Team`) |
| `👨‍💼 Team` | `Prénom` (nom affiché dans les notifications) |
| `TikThook Channels` | `TYPE` (TELEGRAM/DISCORD), `CHAT_ID`, `THREAD_ID`, `TIKTOK_ACCOUNT`, `GUILD`, `CHANNEL` |
| `TikThook Subscribers` | `CHAT_ID` |

> Le nom affiché dans les notifications est le champ `Prénom` du team member lié au compte TikTok via `👨‍💼 Team 2`.

---

## Commandes Telegram

| Commande | Description |
|----------|-------------|
| `/setlive @username` | Assigner un compte TikTok à ce thread |
| `/removelive @username` | Retirer l'assignation d'un compte |
| `/status` | Voir qui est en live en ce moment |
| `/id` | Afficher le chat ID et thread ID du groupe |
| `/help` | Aide complète |

## Commandes Discord

| Commande | Description |
|----------|-------------|
| `/tikthook set` | Assigner ce channel aux notifications globales |
| `/tikthook setlive @username` | Assigner un compte TikTok à ce channel |
| `/tikthook remove` | Retirer l'assignation |
| `/tikthook status` | Voir qui est en live |
| `/tikthook help` | Aide complète |

---

## Mise à jour

```bash
cd tikthook
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart tikthook
```

---

## Logique de routage

- **Set live** (`/setlive @username`) → notifications de ce compte envoyées **uniquement** dans ce thread/channel
- **Global Discord** → reçoit tous les comptes **sauf** ceux déjà set live ailleurs
- **Telegram** → uniquement via `/setlive` (pas de global)
- Un compte ne peut être set live que dans **un seul endroit** à la fois
