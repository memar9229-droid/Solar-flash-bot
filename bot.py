"""
⊙ SOLAR FLASH — Phase 2A Intelligence Engine
Solana-native signal intelligence platform.
"""
import os, re, sys, time, asyncio, logging, traceback, aiohttp, json
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ── LOGGING ──────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO, force=True, stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ── ENV ──────────────────────────────────────────────────────────────
load_dotenv(override=False)
BOT_TOKEN   = os.getenv("BOT_TOKEN",  "").strip()
HELIUS_KEY  = os.getenv("HELIUS_KEY", "").strip()
BIRDEYE_KEY = os.getenv("BIRDEYE_KEY","").strip()

log.info("=== Solar Flash Phase 2 Starting ===")
log.info(f"BOT_TOKEN present: {bool(BOT_TOKEN)} | length: {len(BOT_TOKEN)}")
log.info(f"HELIUS_KEY present: {bool(HELIUS_KEY)}")

if not BOT_TOKEN:
    log.critical("FATAL: BOT_TOKEN missing.")
    sys.exit(1)

# ── CONFIG ───────────────────────────────────────────────────────────
HELIUS_RPC  = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
REPORT_URL  = "https://solar-flash-web.vercel.app/report"
SITE_URL    = "https://solar-flash-web.vercel.app"
TG_CHANNEL  = "https://t.me/SolarFlash_Sol"
X_URL       = "https://x.com/solarflash_sol"
BOT_LINK    = "https://t.me/SolarFlashbot"

SOL_RE      = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")
BURN_ADDRS  = {"1nc1nerator11111111111111111111111111111111","11111111111111111111111111111111"}
T           = aiohttp.ClientTimeout(total=12)

# ── TIER SYSTEM ──────────────────────────────────────────────────────
# In production, replace with database (PostgreSQL/Redis)
# Format: {user_id: {"tier": "free"|"plus"|"alpha", "scans_today": int, "last_scan_date": str, "xp": int, "joined": float}}
USER_DATA: dict[int, dict] = {}

TIERS = {
    "free":  {"name": "FREE",  "emoji": "⚡", "daily_scans": 5,  "color": "rgba(255,255,255,.6)"},
    "plus":  {"name": "PLUS",  "emoji": "🔥", "daily_scans": 50, "color": "rgba(255,180,0,.9)"},
    "alpha": {"name": "ALPHA", "emoji": "☀️", "daily_scans": 999,"color": "rgba(180,80,255,.9)"},
}

PLUS_PRICE  = "$9.99/mo (Founding Rate)"
ALPHA_PRICE = "$29/mo (Early Access)"

def get_user(uid: int) -> dict:
    if uid not in USER_DATA:
        USER_DATA[uid] = {
            "tier": "free",
            "scans_today": 0,
            "last_scan_date": "",
            "xp": 0,
            "joined": time.time(),
            "total_scans": 0,
        }
    return USER_DATA[uid]

def get_tier(uid: int) -> str:
    return get_user(uid)["tier"]

def is_plus(uid: int) -> bool:
    return get_tier(uid) in ("plus", "alpha")

def is_alpha(uid: int) -> bool:
    return get_tier(uid) == "alpha"

def add_xp(uid: int, amount: int = 10):
    u = get_user(uid)
    u["xp"] = u.get("xp", 0) + amount
    u["total_scans"] = u.get("total_scans", 0) + 1

def get_rank(xp: int) -> tuple[str, str]:
    if xp >= 5000: return "⊙ SOLAR MASTER",  "Legendary intelligence operator"
    if xp >= 2000: return "🔥 SIGNAL ELITE",  "Advanced frequency alignment"
    if xp >= 1000: return "🌟 FLASH HUNTER",  "Active intelligence seeker"
    if xp >= 500:  return "⚡ PULSE RIDER",   "Growing signal awareness"
    if xp >= 100:  return "📡 AWAKENING",     "Signal detected — path begun"
    return "🌑 DARK MATTER",               "Unaligned — frequency dormant"

def check_scan_limit(uid: int) -> tuple[bool, int]:
    u   = get_user(uid)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if u["last_scan_date"] != today:
        u["scans_today"]    = 0
        u["last_scan_date"] = today
    limit = TIERS[u["tier"]]["daily_scans"]
    if u["scans_today"] >= limit:
        return False, limit
    return True, limit

def consume_scan(uid: int):
    u = get_user(uid)
    u["scans_today"] = u.get("scans_today", 0) + 1

COOLDOWN: dict[int, float] = {}

# ── KEYBOARDS ────────────────────────────────────────────────────────
def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Scan Token", switch_inline_query_current_chat="/analyze "),
         InlineKeyboardButton("⚡ Live Pulse", callback_data="pulse")],
        [InlineKeyboardButton("🌐 Web Scanner", url=REPORT_URL),
         InlineKeyboardButton("🚀 Join $FLASH", url=TG_CHANNEL)],
    ])

def kb_upgrade_plus():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Upgrade to PLUS — "+PLUS_PRICE, url=TG_CHANNEL)],
        [InlineKeyboardButton("⊙ Back to Free Scan", callback_data="back")],
    ])

def kb_upgrade_alpha():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("☀️ Join ALPHA Waitlist", url=TG_CHANNEL)],
    ])

def kb_report(dex_url=None):
    rows = []
    if dex_url:
        rows.append([InlineKeyboardButton("📈 DexScreener", url=dex_url)])
    rows.append([
        InlineKeyboardButton("🌐 Web Scanner", url=REPORT_URL),
        InlineKeyboardButton("⚡ $FLASH", url=TG_CHANNEL),
    ])
    return InlineKeyboardMarkup(rows)

# ── FORMATTERS ───────────────────────────────────────────────────────
def fmt_num(n):
    if n is None: return "—"
    if n >= 1e9:  return f"{n/1e9:.2f}B"
    if n >= 1e6:  return f"{n/1e6:.2f}M"
    if n >= 1e3:  return f"{n/1e3:.1f}K"
    return f"{int(n):,}"

def fmt_usd(n):
    if n is None: return "—"
    if n >= 1e9:  return f"${n/1e9:.2f}B"
    if n >= 1e6:  return f"${n/1e6:.2f}M"
    if n >= 1e3:  return f"${n/1e3:.1f}K"
    return f"${n:.2f}"

def fmt_price(p):
    if p is None: return "—"
    if p == 0:    return "$0"
    if p >= 1:    return f"${p:,.4f}"
    if p >= 0.01: return f"${p:.6f}"
    s = f"{p:.30f}"
    m = re.match(r"^0\.(0*)(\d{1,8})", s)
    if not m: return f"${p:.12f}"
    zeros = len(m.group(1))
    sig   = m.group(2).rstrip("0")[:6]
    SUB   = str.maketrans("0123456789","₀₁₂₃₄₅₆₇₈₉")
    if zeros < 4: return f"$0.{'0'*zeros}{sig}"
    return f"$0.0{str(zeros).translate(SUB)}{sig}"

def sbar(v,w=10): f=round(max(0,min(100,v))/100*w); return "█"*f+"░"*(w-f)
def rbar(v,w=8):  f=round(max(0,min(100,v))/100*w); return "▓"*f+"░"*(w-f)
def short(a):     return f"{a[:5]}…{a[-5:]}" if a else "—"

# ── API FETCHERS ─────────────────────────────────────────────────────
async def rpc(session, method, params):
    try:
        async with session.post(HELIUS_RPC,
            json={"jsonrpc":"2.0","id":1,"method":method,"params":params},
            headers={"Content-Type":"application/json"}, timeout=T) as r:
            return (await r.json()).get("result")
    except Exception as e:
        log.warning(f"RPC {method}: {e}")
        return None

async def fetch_dex(session, mint):
    try:
        async with session.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=T) as r:
            j     = await r.json()
            pairs = j.get("pairs") or []
            if not pairs: return None
            return sorted(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd",0) or 0), reverse=True)[0]
    except Exception as e:
        log.warning(f"DEX: {e}")
        return None

async def fetch_rug(session, mint):
    try:
        async with session.get(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary", timeout=T) as r:
            if r.status == 200: return await r.json()
    except Exception as e:
        log.warning(f"RUG: {e}")
    return None

async def fetch_sol_price():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", timeout=T) as r:
                d = await r.json()
                return d.get("solana",{}).get("usd")
    except: return None

async def fetch_trending_tokens():
    """Get top tokens by volume from DexScreener Solana"""
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112", timeout=T) as r:
                j = await r.json()
                return (j.get("pairs") or [])[:5]
    except: return []

# ── CORE ANALYSIS ENGINE ─────────────────────────────────────────────
async def run_token_analysis(mint: str) -> dict:
    async with aiohttp.ClientSession() as s:
        asset, mint_info_raw, holders_raw, dex, rug = await asyncio.gather(
            rpc(s,"getAsset",{"id":mint,"displayOptions":{"showFungible":True}}),
            rpc(s,"getAccountInfo",[mint,{"encoding":"jsonParsed"}]),
            rpc(s,"getTokenLargestAccounts",[mint]),
            fetch_dex(s, mint),
            fetch_rug(s, mint),
        )

    mint_info = {}
    if mint_info_raw:
        mint_info = (((mint_info_raw.get("value") or {}).get("data") or {})
                     .get("parsed",{}).get("info",{}))
    holders = (holders_raw or {}).get("value") or []

    meta   = (asset or {}).get("content",{}).get("metadata",{})
    ti     = (asset or {}).get("token_info",{}) or {}
    name   = meta.get("name") or ti.get("symbol") or "Unknown"
    symbol = ti.get("symbol") or "???"

    dec    = int(mint_info.get("decimals",6))
    s_raw  = int(mint_info.get("supply",0))
    supply = s_raw/10**dec if s_raw else None
    top1   = int(holders[0]["amount"])/s_raw*100 if holders and s_raw else 0
    top5   = sum(int(h["amount"]) for h in holders[:5])/s_raw*100 if holders and s_raw else 0
    top10  = sum(int(h["amount"]) for h in holders[:10])/s_raw*100 if holders and s_raw else 0
    lp_b   = any(h.get("address","") in BURN_ADDRS for h in holders)

    dev_wallet, dev_pct = None, 0.0
    for h in holders[:5]:
        addr = h.get("address","")
        pct  = int(h.get("amount",0))/s_raw*100 if s_raw else 0
        if addr not in BURN_ADDRS and not addr.startswith("11111") and pct > 3:
            dev_wallet, dev_pct = addr, pct; break

    mint_auth   = mint_info.get("mintAuthority")
    freeze_auth = mint_info.get("freezeAuthority")
    dx = dex or {}

    def _f(d,k,sub=None):
        v = d.get(k) if not sub else (d.get(k) or {}).get(sub)
        try: return float(v) if v not in (None,"","0") else None
        except: return None

    price  = _f(dx,"priceUsd");  mcap  = _f(dx,"fdv")
    liq    = _f(dx,"liquidity","usd"); vol24 = _f(dx,"volume","h24")
    chg24  = _f(dx,"priceChange","h24")
    buys   = (dx.get("txns") or {}).get("h24",{}).get("buys") or 0
    sells  = (dx.get("txns") or {}).get("h24",{}).get("sells") or 0
    dex_url= dx.get("url")

    socials  = (dx.get("info") or {}).get("socials") or []
    has_tw   = any(s.get("type","").lower() in ("twitter","x") for s in socials)
    has_tg   = any(s.get("type","").lower()=="telegram" for s in socials)
    has_web  = len((dx.get("info") or {}).get("websites") or []) > 0

    pair_age = dx.get("pairCreatedAt")
    age_str  = "—"
    if pair_age:
        diff = time.time()-pair_age/1000
        d2,h2,m2 = int(diff//86400),int((diff%86400)//3600),int((diff%3600)//60)
        age_str = f"{d2}d {h2}h" if d2>0 else f"{h2}h {m2}m" if h2>0 else f"{m2}m"

    rug_score = (rug or {}).get("score")

    # SCORING
    safety = 100
    if mint_auth:   safety -= 30
    if freeze_auth: safety -= 20
    if not lp_b:    safety -= 35
    if rug_score and rug_score>=700: safety -= 20
    elif rug_score and rug_score>=400: safety -= 10
    safety = max(0, min(100, safety))

    whale = min(100, (60 if top1>50 else 35 if top1>25 else 15 if top1>10 else 0) +
                     (30 if top10>70 else 15 if top10>40 else 0))

    community = max(0, min(100, 30 +
        (40 if len(holders)>=2000 else 25 if len(holders)>=500 else 10 if len(holders)>=100 else -10) +
        (10 if has_tw else 0)+(12 if has_tg else 0)+(8 if has_web else 0)))

    heat = max(0, min(100, 20+
        (40 if (chg24 or 0)>200 else 25 if (chg24 or 0)>50 else 12 if (chg24 or 0)>10 else -15 if (chg24 or 0)<-50 else 0)+
        (25 if (vol24 or 0)>500000 else 15 if (vol24 or 0)>100000 else 8 if (vol24 or 0)>10000 else 0)+
        (10 if buys+sells>0 and buys>sells*1.5 else 0)))

    scam = min(100, (25 if mint_auth else 0)+(20 if freeze_auth else 0)+
               (30 if not lp_b else 0)+(15 if top1>30 else 0))
    meme = min(100, 20+(20 if has_tw else 0)+(15 if has_tg else 0)+min(40,int((vol24 or 0)/10000)))
    cult = min(100, 20+(25 if has_tg else 0)+(20 if buys+sells>200 else 0)+(15 if has_tw else 0)+(20 if (chg24 or 0)>50 else 0))

    solar = max(0,min(100,round(safety*0.30+(100-whale)*0.25+community*0.20+heat*0.12+(100-scam)*0.08+50*0.05)))

    if   solar>=80: grade,verdict,gem = "A","STRONG SIGNAL","🟢"
    elif solar>=65: grade,verdict,gem = "B","MODERATE SIGNAL","🟡"
    elif solar>=45: grade,verdict,gem = "C","WEAK SIGNAL","🟠"
    else:           grade,verdict,gem = "D","DANGER — AVOID","🔴"

    if solar>=80:   ai=f"Solar Signal detects strong structural integrity for ${symbol}. Contract architecture is secure and community signals are positive."
    elif solar>=65: ai=f"Solar Signal identifies moderate opportunity for ${symbol} with manageable risk profile. Monitor whale movements closely."
    elif solar>=45: ai=f"Solar Signal flags elevated risk for ${symbol}. Proceed with strict caution and small position sizing."
    else:           ai=f"Solar Signal issues HIGH RISK alert for ${symbol}. Multiple critical red flags. Capital protection is priority."

    return dict(
        mint=mint, name=name, symbol=symbol, supply=supply,
        mint_auth=mint_auth, freeze_auth=freeze_auth,
        lp_burned=lp_b, rug_score=rug_score,
        holders=len(holders), top1=top1, top5=top5, top10=top10,
        dev_wallet=dev_wallet, dev_pct=dev_pct,
        price=price, mcap=mcap, liq=liq, vol24=vol24, chg24=chg24,
        buys=buys, sells=sells, dex_url=dex_url, age=age_str,
        has_tw=has_tw, has_tg=has_tg, has_web=has_web,
        safety=safety, whale=whale, community=community,
        heat=heat, scam=scam, meme=meme, cult=cult,
        solar=solar, grade=grade, verdict=verdict, gem=gem, ai=ai,
    )

def build_report(d: dict, full=True) -> str:
    total_tx = d["buys"]+d["sells"]
    bs_row = ""
    if total_tx > 0:
        bp   = d["buys"]/total_tx*100
        blen = round(bp/100*10)
        bs_row = f"\n🔀 B/S:       `{'🟢'*blen}{'🔴'*(10-blen)}` {bp:.0f}% buy\n             {d['buys']} buys / {d['sells']} sells"

    soc = []
    if d["has_tw"]: soc.append("𝕏")
    if d["has_tg"]: soc.append("TG")
    if d["has_web"]:soc.append("🌐")

    chg_str = ""
    if d["chg24"] is not None:
        arrow   = "📈" if d["chg24"]>=0 else "📉"
        sign    = "+" if d["chg24"]>=0 else ""
        chg_str = f" {arrow} {sign}{d['chg24']:.1f}%"

    dev_line = f"\n👨‍💻 Dev:       `{short(d['dev_wallet'])}` ({d['dev_pct']:.1f}%)" if d["dev_wallet"] else ""
    sell_s   = "RESTRICTED" if d["scam"]>=60 else "CAUTION" if d["scam"]>=30 else "LIKELY OK"
    sell_e   = "🚨" if d["scam"]>=60 else "⚠️" if d["scam"]>=30 else "✅"

    if full:
        return (
            f"☀️ *SOLAR SIGNAL REPORT*\n"
            f"${d['symbol']} — {d['name']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 `{short(d['mint'])}`\n"
            f"🕐 Age: `{d['age']}` · Social: `{' '.join(soc) or 'None'}`\n\n"
            f"{d['gem']} *Solar Signal: {d['solar']}/100 — {d['verdict']}*\n"
            f"`{sbar(d['solar'],14)}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *SUB-SCORES*\n"
            f"🛡 Safety:        `{sbar(d['safety'])}` {d['safety']}/100\n"
            f"🐋 Whale Risk:    `{rbar(d['whale'])}` {d['whale']}/100\n"
            f"👥 Community:    `{sbar(d['community'])}` {d['community']}/100\n"
            f"🔥 Narrative:    `{sbar(d['heat'])}` {d['heat']}/100\n"
            f"☠️ Scam Risk:     `{rbar(d['scam'])}` {d['scam']}/100\n"
            f"🎭 Meme:          `{sbar(d['meme'])}` {d['meme']}/100\n"
            f"⛪ Cult:           `{sbar(d['cult'])}` {d['cult']}/100\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *MARKET DATA*\n"
            f"💲 Price:    `{fmt_price(d['price'])}`{chg_str}\n"
            f"📦 Mkt Cap:  `{fmt_usd(d['mcap'])}`\n"
            f"💧 Liquidity:`{fmt_usd(d['liq'])}`\n"
            f"📊 Vol 24h:  `{fmt_usd(d['vol24'])}`\n"
            f"🪙 Supply:   `{fmt_num(d['supply'])}`\n"
            f"👥 Holders:  `{fmt_num(d['holders'])}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🐋 *WHALE INTELLIGENCE*\n"
            f"🥇 Top 1:   `{d['top1']:.1f}%`\n"
            f"🏆 Top 5:   `{d['top5']:.1f}%`\n"
            f"📊 Top 10:  `{d['top10']:.1f}%`{dev_line}\n"
            f"🔥 LP:      `{'BURNED ✅' if d['lp_burned'] else 'NOT BURNED 🚨'}`{bs_row}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔒 *SELL RISK*\n"
            f"Sellability: {sell_e} `{sell_s}`\n"
            f"Mint Auth:   `{'ACTIVE ⚠️' if d['mint_auth'] else 'REVOKED ✅'}`\n"
            f"Freeze Auth: `{'ACTIVE ⚠️' if d['freeze_auth'] else 'REVOKED ✅'}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 *AI SIGNAL*\n_{d['ai']}_\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⊙ *Solar Flash Intelligence* · _Not financial advice_"
        )
    else:
        return (
            f"☀️ *QUICK SCORE — ${d['symbol']}*\n\n"
            f"{d['gem']} *{d['solar']}/100 — {d['verdict']}*\n"
            f"`{sbar(d['solar'],12)}`\n\n"
            f"🛡 Safety:    {d['safety']}/100\n"
            f"🐋 Whale:     {d['whale']}/100\n"
            f"👥 Community: {d['community']}/100\n"
            f"🔥 Narrative: {d['heat']}/100\n"
            f"☠️ Scam Risk:  {d['scam']}/100\n\n"
            f"🔥 LP: `{'BURNED ✅' if d['lp_burned'] else 'NOT BURNED 🚨'}`\n\n"
            f"🧠 _{d['ai']}_\n\n"
            f"⊙ Use /analyze for full intelligence report"
        )

# ── COMMAND HANDLERS ──────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    u    = get_user(uid)
    tier = TIERS[u["tier"]]
    name = update.effective_user.first_name or "Operator"

    await update.message.reply_text(
        f"☀️ *Welcome to Solar Flash Phase II* ⚡\n"
        f"_{name}_ — your Solana intelligence layer is now active.\n\n"
        f"Your tier: {tier['emoji']} *{tier['name']}*\n\n"
        f"*Choose your path:*\n"
        f"📊 /analyze — Scan any token contract\n"
        f"⚡ /pulse — Live Solana market pulse\n"
        f"📈 /daily — Daily Flash insights\n"
        f"🔬 /deep — Advanced token intelligence _{('(PLUS)' if not is_plus(uid) else '')}_\n"
        f"🏆 /rank — Your Flash rank & XP\n"
        f"❓ /help — All commands\n\n"
        f"_Paste any Solana token address to scan instantly._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_main(),
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(
        "☀️ *SOLAR FLASH COMMANDS*\n\n"
        "*⚡ FREE TIER*\n"
        "/analyze `<address>` — Full intelligence report\n"
        "/score `<address>` — Quick signal score\n"
        "/pulse — Live Solana market pulse\n"
        "/daily — Daily Flash insights\n"
        "/rank — Your Flash rank & XP\n"
        "/about — About Solar Flash\n\n"
        "*🔥 PLUS TIER* _("+PLUS_PRICE+")_\n"
        "/deep `<address>` — Advanced token scan\n"
        "/signals — Premium trading signals\n"
        "/alerts — Premium market alerts\n\n"
        "*☀️ ALPHA TIER* _("+ALPHA_PRICE+")_\n"
        "/alpha — Limited alpha feed\n"
        "/whales — Whale wallet tracking\n"
        "/stealth — Emerging token intelligence\n\n"
        "_Signal before noise._ ⊙",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_about(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⊙ *SOLAR FLASH — Solana Intelligence Engine*\n\n"
        "_Built to detect signal before noise._\n"
        "_Real-time Solana token analysis, risk scoring, and market pulse._\n\n"
        "📡 *Data Sources:*\n"
        "• Helius RPC — on-chain data\n"
        "• DexScreener — market data\n"
        "• RugCheck — contract risk\n\n"
        "🚀 *Ecosystem:*\n"
        f"• Bot: {BOT_LINK}\n"
        f"• Web: {SITE_URL}\n"
        f"• Community: {TG_CHANNEL}\n\n"
        "_Phase 2 Intelligence Engine — Now Live._",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
    )


async def cmd_pulse(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    msg = await update.message.reply_text(
        "⚡ *Scanning Solana pulse...*", parse_mode=ParseMode.MARKDOWN
    )
    try:
        sol_price = await asyncio.wait_for(fetch_sol_price(), timeout=8)

        # Build live pulse from DexScreener data
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://api.dexscreener.com/latest/dex/search?q=sol",
                timeout=T
            ) as r:
                data  = await r.json()
                pairs = (data.get("pairs") or [])[:20]

        total_vol = sum(float((p.get("volume") or {}).get("h24",0) or 0) for p in pairs)
        avg_chg   = sum(float((p.get("priceChange") or {}).get("h24",0) or 0) for p in pairs) / max(len(pairs),1)
        total_buys  = sum((p.get("txns") or {}).get("h24",{}).get("buys",0) or 0 for p in pairs)
        total_sells = sum((p.get("txns") or {}).get("h24",{}).get("sells",0) or 0 for p in pairs)

        # Sentiment calculation
        bull_score = 0
        if avg_chg > 5:   bull_score += 40
        elif avg_chg > 0: bull_score += 20
        else:             bull_score -= 20
        total_tx = total_buys + total_sells
        if total_tx > 0:
            buy_ratio = total_buys / total_tx * 100
            if buy_ratio > 60:   bull_score += 30
            elif buy_ratio > 50: bull_score += 15
            else:                bull_score -= 15
        if total_vol > 100_000_000: bull_score += 30
        elif total_vol > 50_000_000: bull_score += 15

        if bull_score >= 50:    sentiment, sent_e = "BULLISH",  "🟢"
        elif bull_score >= 10:  sentiment, sent_e = "NEUTRAL",  "🟡"
        elif bull_score >= -10: sentiment, sent_e = "CAUTIOUS", "🟠"
        else:                   sentiment, sent_e = "BEARISH",  "🔴"

        risk_temp = max(0, min(100, 50 + int(-avg_chg/2)))
        liq_flow  = "↑ INFLOW" if avg_chg > 2 else "↓ OUTFLOW" if avg_chg < -2 else "→ NEUTRAL"

        buy_ratio_str = f"{buy_ratio:.0f}%" if total_tx > 0 else "—"

        now = datetime.now(timezone.utc).strftime("%H:%M UTC")

        text = (
            f"⚡ *SOLANA MARKET PULSE*\n"
            f"_{now} · Live Data_\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{sent_e} *Sentiment:*     `{sentiment}`\n"
            f"💧 *Liquidity Flow:* `{liq_flow}`\n"
            f"🌡 *Risk Temp:*      `{sbar(risk_temp)} {risk_temp}/100`\n"
            f"🔥 *Narrative Heat:* `{sbar(min(100,int(total_vol/1_000_000)))} {min(100,int(total_vol/1_000_000))}/100`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *MARKET STATS*\n"
            f"💰 SOL Price:     `${sol_price:,.2f}`\n" if sol_price else ""
            f"📈 Avg 24h Δ:    `{'+' if avg_chg>=0 else ''}{avg_chg:.1f}%`\n"
            f"💸 Total Vol:    `{fmt_usd(total_vol)}`\n"
            f"🔀 Buy Pressure: `{buy_ratio_str}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        )

        if not is_plus(uid):
            text += (
                f"🔒 *Full Pulse Data — PLUS only*\n"
                f"• Whale flow tracking\n"
                f"• Sector rotation signals\n"
                f"• Early momentum detection\n\n"
                f"_Upgrade to PLUS: {PLUS_PRICE}_"
            )
        else:
            text += (
                f"🔥 *PLUS INTELLIGENCE*\n"
                f"• Sector: Meme tokens leading\n"
                f"• Smart money: Accumulating\n"
                f"• Next catalyst: Watch $FLASH\n"
            )

        text += f"\n\n⊙ _Solar Flash Intelligence_"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔥 Upgrade to PLUS", url=TG_CHANNEL)] if not is_plus(uid) else
            [InlineKeyboardButton("📊 Scan Token", switch_inline_query_current_chat="/analyze ")],
            [InlineKeyboardButton("🌐 Dashboard", url=SITE_URL)],
        ])
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        add_xp(uid, 5)

    except Exception as e:
        log.error(f"Pulse error: {e}", exc_info=True)
        await msg.edit_text("❌ Pulse scan failed. Try again.", parse_mode=ParseMode.MARKDOWN)


async def cmd_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    now = datetime.now(timezone.utc)

    text = (
        f"☀️ *DAILY FLASH SIGNAL*\n"
        f"_{now.strftime('%A %d %b %Y · %H:%M UTC')}_\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ *TODAY'S INTELLIGENCE*\n\n"
        f"📡 *Market Narrative:*\n"
        f"Solana ecosystem activity remains elevated. Meme sector showing rotation signals. Community-driven tokens outperforming utility plays in current cycle.\n\n"
        f"⚠️ *Risk Alerts:*\n"
        f"• High rug activity detected — scan before buying\n"
        f"• Whale distribution in several mid-caps\n"
        f"• New LP pulls in anonymous launches\n\n"
        f"🔥 *Frequency Signal:*\n"
        f"Solar Flash Protocol continues alignment. $FLASH holders maintain frequency advantage.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    if not is_plus(uid):
        text += (
            f"🔒 *Premium Daily Signals — PLUS only*\n"
            f"• Specific token opportunities\n"
            f"• Entry/exit intelligence\n"
            f"• Whale wallet monitoring\n\n"
            f"_Upgrade: {PLUS_PRICE}_"
        )
    else:
        text += (
            f"🎯 *PLUS OPPORTUNITIES* _(educational only)_\n"
            f"• Scan high-volume new launches\n"
            f"• Monitor liquidity adds > $50K\n"
            f"• Watch social volume spikes\n"
        )

    text += "\n\n⊙ _Not financial advice. DYOR._"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Scan a Token", switch_inline_query_current_chat="/analyze "),
         InlineKeyboardButton("⚡ Live Pulse", callback_data="pulse_cmd")],
        [InlineKeyboardButton("🔥 Upgrade PLUS", url=TG_CHANNEL) if not is_plus(uid) else
         InlineKeyboardButton("🌐 Dashboard", url=SITE_URL)],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    add_xp(uid, 3)


async def cmd_rank(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    u    = get_user(uid)
    xp   = u.get("xp", 0)
    rank_title, rank_desc = get_rank(xp)
    tier = TIERS[u["tier"]]
    scans = u.get("total_scans", 0)
    joined_days = max(1, int((time.time() - u.get("joined", time.time())) / 86400))

    # XP progress to next rank
    thresholds = [100, 500, 1000, 2000, 5000, 99999]
    next_xp    = next((t for t in thresholds if t > xp), 99999)
    progress   = min(100, int(xp / next_xp * 100)) if next_xp < 99999 else 100
    xp_needed  = max(0, next_xp - xp)

    await update.message.reply_text(
        f"🏆 *FLASH RANK*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{rank_title}\n"
        f"_{rank_desc}_\n\n"
        f"⚡ *XP:*      `{xp:,}`\n"
        f"📊 *Progress:* `{sbar(progress,12)}` {progress}%\n"
        f"🎯 *Next rank:* `{xp_needed:,} XP needed`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *YOUR STATS*\n"
        f"🔍 Total Scans: `{scans}`\n"
        f"📅 Member for:  `{joined_days} days`\n"
        f"{tier['emoji']} Tier: *{tier['name']}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"*HOW TO EARN XP*\n"
        f"• /analyze — +10 XP\n"
        f"• /pulse — +5 XP\n"
        f"• /daily — +3 XP\n"
        f"• /deep — +20 XP (PLUS)\n\n"
        f"⊙ _Solar Flash Intelligence_",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_deep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_plus(uid):
        await update.message.reply_text(
            "🔬 *Deep Scan — Solar Flash PLUS*\n\n"
            "Deep Scan unlocks advanced intelligence layers not available in free tier:\n\n"
            "• Full holder concentration analysis\n"
            "• Liquidity lock & burn verification\n"
            "• Dev wallet activity tracking\n"
            "• Contract anomaly detection\n"
            "• Deployment age analysis\n"
            "• Advanced risk breakdown\n"
            "• RugCheck full report\n\n"
            f"🔥 *Upgrade to PLUS — {PLUS_PRICE}*\n"
            f"_Future price: $14.99–19.99/mo_\n\n"
            "_Lock in founding rate before it's gone._ ⚡",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_upgrade_plus(),
        )
        return

    if not ctx.args:
        await update.message.reply_text(
            "Usage: `/deep <token_address>`", parse_mode=ParseMode.MARKDOWN
        )
        return

    mint = ctx.args[0].strip()
    if not SOL_RE.fullmatch(mint):
        await update.message.reply_text("❌ Invalid Solana address.")
        return

    ok, limit = check_scan_limit(uid)
    if not ok:
        await update.message.reply_text(f"⏳ Daily scan limit ({limit}) reached. Resets at midnight UTC.")
        return

    msg = await update.message.reply_text(
        "🔬 *Deep Intelligence Scan...*\n\n"
        "⛓ Full on-chain analysis\n"
        "🐋 Whale pattern detection\n"
        "🔍 Contract anomaly scan\n"
        "📊 Advanced risk breakdown",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        d = await asyncio.wait_for(run_token_analysis(mint), timeout=28)
        consume_scan(uid)
        add_xp(uid, 20)

        risk_factors = []
        if d["mint_auth"]:    risk_factors.append("🚨 Mint authority active")
        if d["freeze_auth"]:  risk_factors.append("🚨 Freeze authority active")
        if not d["lp_burned"]:risk_factors.append("🚨 LP not burned")
        if d["top1"] > 30:    risk_factors.append(f"⚠️ Top wallet: {d['top1']:.1f}%")
        if d["dev_pct"] > 5:  risk_factors.append(f"⚠️ Dev holds: {d['dev_pct']:.1f}%")
        if d["rug_score"] and d["rug_score"] > 400: risk_factors.append(f"⚠️ RugCheck: {d['rug_score']}/1000")
        if not risk_factors:  risk_factors.append("✅ No critical risk factors detected")

        text = (
            f"🔬 *DEEP INTELLIGENCE SCAN*\n"
            f"${d['symbol']} — {d['name']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{d['gem']} *Solar Signal: {d['solar']}/100 — {d['verdict']}*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔍 *CONTRACT ANALYSIS*\n"
            f"📋 Address: `{short(d['mint'])}`\n"
            f"🕐 Pair Age: `{d['age']}`\n"
            f"Mint Auth:   `{'ACTIVE ⚠️' if d['mint_auth'] else 'REVOKED ✅'}`\n"
            f"Freeze Auth: `{'ACTIVE ⚠️' if d['freeze_auth'] else 'REVOKED ✅'}`\n"
            f"LP Burned:   `{'YES 🔥' if d['lp_burned'] else 'NO 🚨'}`\n"
            f"RugCheck:    `{d['rug_score']}/1000` {'🚨' if d['rug_score'] and d['rug_score']>400 else '✅'}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🐋 *HOLDER INTELLIGENCE*\n"
            f"Total Holders: `{fmt_num(d['holders'])}`\n"
            f"Top 1 Wallet:  `{d['top1']:.2f}%`\n"
            f"Top 5 Wallets: `{d['top5']:.2f}%`\n"
            f"Top 10:        `{d['top10']:.2f}%`\n"
            f"Dev Wallet:    `{d['dev_pct']:.2f}%` {'⚠️' if d['dev_pct']>5 else '✅'}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ *RISK FACTORS*\n"
            + "\n".join(risk_factors) + "\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *MARKET*\n"
            f"Price:     `{fmt_price(d['price'])}`\n"
            f"Mkt Cap:   `{fmt_usd(d['mcap'])}`\n"
            f"Liquidity: `{fmt_usd(d['liq'])}`\n"
            f"Vol 24h:   `{fmt_usd(d['vol24'])}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 *AI SIGNAL*\n_{d['ai']}_\n\n"
            f"⊙ *Solar Flash PLUS Intelligence*"
        )
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                            reply_markup=kb_report(d.get("dex_url")),
                            disable_web_page_preview=True)
    except asyncio.TimeoutError:
        await msg.edit_text("⏱ Scan timed out. Try again.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"Deep scan error: {e}", exc_info=True)
        await msg.edit_text("❌ Deep scan failed. Check address.", parse_mode=ParseMode.MARKDOWN)


async def cmd_alpha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_alpha(uid):
        await update.message.reply_text(
            "☀️ *Solar Flash ALPHA — Restricted Access*\n\n"
            "Alpha intelligence is limited to verified ALPHA members only.\n\n"
            "What ALPHA includes:\n"
            "• Early-stage token intelligence\n"
            "• Whale wallet tracking\n"
            "• Stealth launch detection\n"
            "• Priority signal delivery\n"
            "• Scarcity-driven opportunities\n\n"
            f"☀️ *ALPHA — {ALPHA_PRICE}*\n"
            f"_Future price: $49–79/mo_\n\n"
            "_Limited slots. Access is restricted by design._ ⊙",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_upgrade_alpha(),
        )
        return
    await update.message.reply_text(
        "☀️ *ALPHA FEED — RESTRICTED*\n\n"
        "_Alpha intelligence active. More signals incoming._\n\n"
        "⊙ _Solar Flash Alpha_",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_whales(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_plus(uid):
        await update.message.reply_text(
            "🐋 *Whale Tracking — Solar Flash PLUS*\n\n"
            "Track smart money movements on Solana.\n\n"
            f"_Upgrade: {PLUS_PRICE}_",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb_upgrade_plus(),
        )
        return
    await update.message.reply_text(
        "🐋 *WHALE INTELLIGENCE*\n_Coming in Phase 2B_ ⚡",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_signals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_plus(uid):
        await update.message.reply_text(
            "📡 *Premium Signals — Solar Flash PLUS*\n\n"
            "Access curated trading intelligence.\n\n"
            f"_Upgrade: {PLUS_PRICE}_",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb_upgrade_plus(),
        )
        return
    await update.message.reply_text(
        "📡 *PREMIUM SIGNALS*\n_Signals active in Phase 2B_ ⚡",
        parse_mode=ParseMode.MARKDOWN,
    )


# ── CORE ANALYZE / SCORE ─────────────────────────────────────────────
async def do_analysis(update, mint, full=True):
    uid = update.effective_user.id

    now = time.time()
    if now - COOLDOWN.get(uid, 0) < 6:
        await update.message.reply_text("⏳ Please wait a few seconds.")
        return
    COOLDOWN[uid] = now

    ok, limit = check_scan_limit(uid)
    if not ok:
        await update.message.reply_text(
            f"⏳ *Daily limit reached* ({limit} scans/day on FREE tier).\n\n"
            f"🔥 Upgrade to PLUS for {PLUS_PRICE} — 50 scans/day.\n\n"
            f"_Resets at midnight UTC._",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb_upgrade_plus(),
        )
        return

    msg = await update.message.reply_text(
        "☀️ *Solar Flash scanning...*\n\n"
        "⛓ Fetching on-chain data\n📊 Pulling market data\n"
        "🐋 Analyzing whale activity\n🧠 Generating AI signal",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        d   = await asyncio.wait_for(run_token_analysis(mint), timeout=28)
        consume_scan(uid)
        add_xp(uid, 10)
        text = build_report(d, full=full)
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                            reply_markup=kb_report(d.get("dex_url")),
                            disable_web_page_preview=True)
    except asyncio.TimeoutError:
        await msg.edit_text("⏱ *Timed out.* Try again.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"Analysis error [{mint}]: {e}", exc_info=True)
        await msg.edit_text("❌ *Could not analyze.* Check address.", parse_mode=ParseMode.MARKDOWN)


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/analyze <address>`", parse_mode=ParseMode.MARKDOWN)
        return
    mint = ctx.args[0].strip()
    if not SOL_RE.fullmatch(mint):
        await update.message.reply_text("❌ Invalid Solana address.")
        return
    await do_analysis(update, mint, full=True)


async def cmd_score(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/score <address>`", parse_mode=ParseMode.MARKDOWN)
        return
    await do_analysis(update, ctx.args[0].strip(), full=False)


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text  = (update.message.text or "").strip()
    match = SOL_RE.search(text)
    if match:
        await do_analysis(update, match.group(), full=True)
    else:
        await update.message.reply_text(
            "⊙ Paste a Solana token address to scan instantly.\n\n"
            "Or use /help to see all commands.",
            parse_mode=ParseMode.MARKDOWN,
        )

# ── MAIN ─────────────────────────────────────────────────────────────
def main():
    try:
        log.info("Building application...")
        app = Application.builder().token(BOT_TOKEN).build()

        app.add_handler(CommandHandler("start",   cmd_start))
        app.add_handler(CommandHandler("help",    cmd_help))
        app.add_handler(CommandHandler("about",   cmd_about))
        app.add_handler(CommandHandler("analyze", cmd_analyze))
        app.add_handler(CommandHandler("score",   cmd_score))
        app.add_handler(CommandHandler("pulse",   cmd_pulse))
        app.add_handler(CommandHandler("daily",   cmd_daily))
        app.add_handler(CommandHandler("rank",    cmd_rank))
        app.add_handler(CommandHandler("deep",    cmd_deep))
        app.add_handler(CommandHandler("alpha",   cmd_alpha))
        app.add_handler(CommandHandler("whales",  cmd_whales))
        app.add_handler(CommandHandler("signals", cmd_signals))
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, handle_message
        ))

        log.info("⊙ Solar Flash Phase 2 — LIVE")
        app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

    except Exception:
        log.critical("FATAL STARTUP ERROR:")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
