import os
import re
import time
import asyncio
import logging
import aiohttp
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

load_dotenv()
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
HELIUS_KEY = os.getenv("HELIUS_KEY", "")
BIRDEYE_KEY = os.getenv("BIRDEYE_KEY", "")
HELIUS_RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
REPORT_URL = "https://solar-flash-web.vercel.app/report"
TG_CHANNEL = "https://t.me/SolarFlash_Sol"
X_URL = "https://x.com/solarflash_sol"
SOL_RE = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")
BURN_ADDRS = {"1nc1nerator11111111111111111111111111111111", "11111111111111111111111111111111"}
COOLDOWN = {}
T = aiohttp.ClientTimeout(total=12)
