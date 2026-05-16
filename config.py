    import os
from dotenv import load_dotenv

load_dotenv()

# ── BOT ─────────────────────────────────────────────────────────────
BOT_TOKEN  = os.getenv("BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

# ── API KEYS ─────────────────────────────────────────────────────────
HELIUS_KEY  = os.getenv("HELIUS_KEY", "")
BIRDEYE_KEY = os.getenv("BIRDEYE_KEY", "")   # optional

# ── ENDPOINTS ────────────────────────────────────────────────────────
HELIUS_RPC   = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
DEXSCREENER  = "https://api.dexscreener.com/latest/dex/tokens"
RUGCHECK     = "https://api.rugcheck.xyz/v1/tokens"
BIRDEYE_BASE = "https://public-api.birdeye.so"
SOLSCAN_BASE = "https://pro-api.solscan.io/v2.0"

# ── LINKS ────────────────────────────────────────────────────────────
SITE_URL     = "https://solar-flash-web.vercel.app"
REPORT_URL   = f"{SITE_URL}/report"
TG_CHANNEL   = "https://t.me/SolarFlash_Sol"
X_URL        = "https://x.com/solarflash_sol"

# ── RATE LIMITING ────────────────────────────────────────────────────
SCAN_COOLDOWN_SEC = 8
ANALYSIS_TIMEOUT  = 28

# ── BURN ADDRESSES ───────────────────────────────────────────────────
BURN_ADDRS = {
    "1nc1nerator11111111111111111111111111111111",
    "11111111111111111111111111111111",
    "So11111111111111111111111111111111111111112",
}

    
