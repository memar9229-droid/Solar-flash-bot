# ⊙ SOLAR SIGNAL BOT
**by Solar Flash — Elite Solana Intelligence**

---

## File Structure

```
solar-flash-bot/
├── bot.py           ← Entry point
├── config.py        ← API keys & settings
├── fetchers.py      ← All API calls (Helius, DexScreener, RugCheck)
├── parser.py        ← Normalize raw data
├── scorer.py        ← Solar Signal Score engine + AI summary
├── handlers.py      ← Telegram commands & messages
├── formatters.py    ← Premium message formatting
├── requirements.txt
├── Procfile         ← Railway deployment
└── .env.example     ← Environment variables template
```

---

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | How to use |
| `/about` | About Solar Flash |
| `/analyze <address>` | Full intelligence report |
| `/score <address>` | Quick score card |
| Paste address | Auto-triggers full report |

---

## Deploy on Railway

1. Create new GitHub repo: `solar-flash-bot`
2. Upload all files
3. Go to railway.app → New Project → Deploy from GitHub
4. Add Variables:
   - `BOT_TOKEN` = your telegram bot token
   - `HELIUS_KEY` = your helius api key
5. Deploy ✅

---

## Score Breakdown

| Score | Weight | Description |
|---|---|---|
| Safety Score | 35% | Mint/Freeze authority, LP status |
| Whale Risk | 25% | Holder concentration |
| Community | 20% | Holders, social presence |
| Narrative Heat | 10% | Price action, volume, buy pressure |
| Scam Risk | 10% | Contract red flags |

---

⊙ Part of the Solar Flash ecosystem.
