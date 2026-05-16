    import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
HELIUS_KEY = os.getenv("HELIUS_KEY", "")
BIRDEYE_KEY = os.getenv("BIRDEYE_KEY", "")

HELIUS_RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
DEXSCREENER = "https://api.dexscreener.com/latest/dex/tokens"
RUGCHECK = "https://api.rugcheck.xyz/v1/tokens"
BIRDEYE_BASE = "https://public-api.birdeye.so"

SITE_URL = "https://solar-flash-web.vercel.app"
REPORT_URL = f"{SITE_URL}/report"
TG_CHANNEL = "https://t.me/SolarFlash_Sol"
X_URL = "https://x.com/solarflash_sol"

SCAN_COOLDOWN_SEC = 8
ANALYSIS_TIMEOUT = 28

BURN_ADDRS = {
    "1nc1nerator11111111111111111111111111111111",
    "11111111111111111111111111111111",
    "So11111111111111111111111111111111111111112",
}

    
