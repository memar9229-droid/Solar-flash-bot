import os

# ── BOT ─────────────────────────────────────────────────────────────
BOT_TOKEN  = os.getenv("BOT_TOKEN",  "8609897160:AAG-bhw2pLlyHoF8mQiSXvHhOxBpRIRtFok")

# ── API KEYS ─────────────────────────────────────────────────────────
HELIUS_KEY = os.getenv("HELIUS_KEY", "3ef572d9-b813-4361-bf5b-3f7a4bff3985")
BIRDEYE_KEY= os.getenv("BIRDEYE_KEY","")          # optional — add yours

# ── ENDPOINTS ────────────────────────────────────────────────────────
HELIUS_RPC    = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
DEXSCREENER   = "https://api.dexscreener.com/latest/dex/tokens"
RUGCHECK      = "https://api.rugcheck.xyz/v1/tokens"
BIRDEYE_BASE  = "https://public-api.birdeye.so"

# ── LINKS ────────────────────────────────────────────────────────────
SITE_URL      = "https://solar-flash-web.vercel.app"
REPORT_URL    = f"{SITE_URL}/report"
TG_CHANNEL    = "https://t.me/SolarFlash_Sol"
X_URL         = "https://x.com/solarflash_sol"
BOT_USERNAME  = "@SolarFlashbot"

# ── RATE LIMITS ──────────────────────────────────────────────────────
MAX_REQUESTS_PER_MIN = 10
ANALYSIS_TIMEOUT_SEC = 25
