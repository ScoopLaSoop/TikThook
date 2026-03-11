# Logique de routage des notifications TikThook

## Schéma de la nouvelle logique

```
                    ┌─────────────────────────────────────────────────────────┐
                    │              Compte TikTok @username                     │
                    └─────────────────────────────────────────────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │         account_has_setlive_anywhere(username) ?          │
                    └─────────────────────────────────────────────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    │ OUI                                      │ NON
                    ▼                                          ▼
    ┌───────────────────────────────┐          ┌───────────────────────────────┐
    │ Envoi UNIQUEMENT au channel   │          │ Telegram: Team + abonnés       │
    │ où le compte a été set live   │          │ Discord: channels globaux      │
    │ (1 seul destination)          │          │                                │
    └───────────────────────────────┘          └───────────────────────────────┘
```

## Règles implémentées

### Règle 1 — Set Live dans un thread (Telegram)
- Quand un compte est **set live** dans un thread/channel → **retirer ce compte de TOUS** les autres threads et globaux (Telegram + Discord)
- Les notifications de ce compte vont **uniquement** dans le thread où il a été set live
- Aucune fuite ailleurs

### Règle 2 — Telegram = uniquement /setlive
- **Supprimé** : `/addgroup`, `/removegroup`, `/start`, `/stop`, Team
- Sur Telegram : uniquement `/setlive username` dans le topic cible
- Chaque compte = un thread dédié, pas de global, pas d'abonnés

### Règle 3 — Set Global (Discord uniquement)
- Le set global reste disponible **seulement sur Discord** (`/tikthook set`)
- Lors d'un set global Discord → **exclure automatiquement** tout compte déjà set live dans un channel spécifique (Telegram ou Discord)
- Un compte "set live" a **priorité absolue** sur le global

## Tables Airtable

| Table | Rôle |
|-------|------|
| **TikThook PUSH LIVE 🟢** | Comptes TikTok surveillés, Team, Telegram "Live" ID Channel |
| **TikThook Channels** | Destinations (TYPE=TELEGRAM ou DISCORD, TIKTOK_ACCOUNT vide = global) |
| **TikThook Subscribers** | Abonnés individuels (/start) |

## Nettoyage Airtable

Après déploiement de la nouvelle logique, exécuter :

```bash
python cleanup_airtable.py
```

Cela supprime :
- Tous les enregistrements de **TikThook Channels**
- Tous les enregistrements de **TikThook Subscribers**

La structure des tables est conservée.
