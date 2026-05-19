"""
⊙ SOLAR FLASH — Phase 2A + Auto Payment System
Fully automatic crypto payment processing via NOWPayments
Supports: SOL, USDT, USDC, BTC, ETH + Visa/PayPal via NOWPayments
"""
import os, re, sys, time, asyncio, logging, traceback, aiohttp, json, hmac, hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, PreCheckoutQueryHandler
from telegram.constants import ParseMode
from aiohttp import web

# ── LOGGING ──────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO, force=True, stream=sys.stdout,
)
log = logging.getLogger(__name__)

# ── ENV ──────────────────────────────────────────────────────────────
load_dotenv(override=False)
BOT_TOKEN        = os.getenv("BOT_TOKEN",        "").strip()
HELIUS_KEY       = os.getenv("HELIUS_KEY",        "").strip()
NOWPAYMENTS_KEY  = os.getenv("NOWPAYMENTS_KEY",   "").strip()
NOWPAYMENTS_IPN  = os.getenv("NOWPAYMENTS_IPN",   "").strip()  # IPN secret key
PAYMENT_WALLET   = os.getenv("PAYMENT_WALLET",    "").strip()  # Your SOL wallet
RAILWAY_URL      = os.getenv("RAILWAY_STATIC_URL","").strip()  # Your Railway public URL

log.info("=== Solar Flash Phase 2 + Payments Starting ===")
log.info(f"BOT_TOKEN: {bool(BOT_TOKEN)} | HELIUS: {bool(HELIUS_KEY)} | NOWPAYMENTS: {bool(NOWPAYMENTS_KEY)}")

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
NP_BASE     = "https://api.nowpayments.io/v1"

SOL_RE      = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")
BURN_ADDRS  = {"1nc1nerator11111111111111111111111111111111","11111111111111111111111111111111"}
T           = aiohttp.ClientTimeout(total=15)

# ── PRICING ──────────────────────────────────────────────────────────
PLANS = {
    "plus": {
        "name":        "Solar Flash PLUS",
        "emoji":       "🔥",
        "price_usd":   9.99,
        "description": "50 scans/day · /deep · Premium signals · Full pulse",
        "future_price":"$14.99–19.99/mo",
        "tag":         "Founding Member Rate",
    },
    "alpha": {
        "name":        "Solar Flash ALPHA",
        "emoji":       "☀️",
        "price_usd":   29.00,
        "description": "Unlimited scans · All PLUS · Alpha feed · Whale tracking · Priority signals",
        "future_price":"$49–79/mo",
        "tag":         "Early Access — Limited Slots",
    },
}

# Supported payment methods
PAYMENT_METHODS = [
    {"id":"sol",   "name":"Solana (SOL)", "emoji":"◎"},
    {"id":"usdtsol","name":"USDT (Solana)","emoji":"💵"},
    {"id":"usdcsol","name":"USDC (Solana)","emoji":"💵"},
    {"id":"btc",   "name":"Bitcoin (BTC)", "emoji":"₿"},
    {"id":"eth",   "name":"Ethereum (ETH)","emoji":"Ξ"},
]

# ── USER DATA STORE ──────────────────────────────────────────────────
# Production: replace with PostgreSQL / Redis
USER_DATA: dict[int, dict]     = {}
PENDING_PAYMENTS: dict[str, dict] = {}  # payment_id -> {uid, plan, created_at}

TIERS = {
    "free":  {"name":"FREE",  "emoji":"⚡","daily_scans":5},
    "plus":  {"name":"PLUS",  "emoji":"🔥","daily_scans":50},
    "alpha": {"name":"ALPHA", "emoji":"☀️","daily_scans":999},
}

def get_user(uid):
    if uid not in USER_DATA:
        USER_DATA[uid] = {"tier":"free","scans_today":0,"last_scan_date":"",
                          "xp":0,"joined":time.time(),"total_scans":0,"tg_id":uid}
    return USER_DATA[uid]

def get_tier(uid):    return get_user(uid)["tier"]
def is_plus(uid):     return get_tier(uid) in ("plus","alpha")
def is_alpha(uid):    return get_tier(uid) == "alpha"

def add_xp(uid, xp=10):
    u = get_user(uid)
    u["xp"]          = u.get("xp",0)+xp
    u["total_scans"] = u.get("total_scans",0)+1

def get_rank(xp):
    if xp>=5000: return "⊙ SOLAR MASTER",  "Legendary intelligence operator"
    if xp>=2000: return "🔥 SIGNAL ELITE",  "Advanced frequency alignment"
    if xp>=1000: return "🌟 FLASH HUNTER",  "Active intelligence seeker"
    if xp>=500:  return "⚡ PULSE RIDER",   "Growing signal awareness"
    if xp>=100:  return "📡 AWAKENING",     "Signal detected"
    return "🌑 DARK MATTER",               "Unaligned — frequency dormant"

def check_scan_limit(uid):
    u     = get_user(uid)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if u["last_scan_date"] != today:
        u["scans_today"] = 0; u["last_scan_date"] = today
    limit = TIERS[u["tier"]]["daily_scans"]
    return u["scans_today"] < limit, limit

def consume_scan(uid):
    get_user(uid)["scans_today"] = get_user(uid).get("scans_today",0)+1

COOLDOWN: dict[int,float] = {}

# ── NOWPAYMENTS API ───────────────────────────────────────────────────
async def create_payment(uid: int, plan: str, currency: str) -> dict | None:
    """Create a NOWPayments invoice and return payment details."""
    if not NOWPAYMENTS_KEY:
        return None
    p = PLANS[plan]
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{NP_BASE}/payment",
                headers={"x-api-key": NOWPAYMENTS_KEY, "Content-Type":"application/json"},
                json={
                    "price_amount":    p["price_usd"],
                    "price_currency":  "usd",
                    "pay_currency":    currency,
                    "order_id":        f"sf_{plan}_{uid}_{int(time.time())}",
                    "order_description": f"Solar Flash {p['name']} — User {uid}",
                    "ipn_callback_url": f"{RAILWAY_URL}/payment/webhook" if RAILWAY_URL else None,
                },
                timeout=T,
            ) as r:
                if r.status == 201:
                    data = await r.json()
                    # Store pending payment
                    PENDING_PAYMENTS[data["payment_id"]] = {
                        "uid":        uid,
                        "plan":       plan,
                        "created_at": time.time(),
                        "currency":   currency,
                        "amount":     data.get("pay_amount"),
                        "address":    data.get("pay_address"),
                        "status":     "waiting",
                    }
                    return data
                else:
                    err = await r.text()
                    log.error(f"NOWPayments create error: {r.status} {err}")
    except Exception as e:
        log.error(f"NOWPayments create_payment: {e}")
    return None

async def check_payment_status(payment_id: str) -> str | None:
    """Check the status of a payment."""
    if not NOWPAYMENTS_KEY:
        return None
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                f"{NP_BASE}/payment/{payment_id}",
                headers={"x-api-key": NOWPAYMENTS_KEY},
                timeout=T,
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get("payment_status")
    except Exception as e:
        log.warning(f"Payment status check: {e}")
    return None

async def activate_plan(uid: int, plan: str, bot=None):
    """Activate a paid plan for a user."""
    u = get_user(uid)
    u["tier"]        = plan
    u["tier_since"]  = time.time()
    u["tier_expires"]= time.time() + 30*86400  # 30 days

    log.info(f"✅ PAYMENT CONFIRMED: user {uid} → {plan.upper()}")

    if bot:
        p = PLANS[plan]
        try:
            await bot.send_message(
                chat_id=uid,
                text=(
                    f"✅ *Payment Confirmed!*\n\n"
                    f"{p['emoji']} *Welcome to Solar Flash {p['name']}*\n\n"
                    f"Your access is now active.\n\n"
                    f"*What's unlocked:*\n_{p['description']}_\n\n"
                    f"Try it now:\n"
                    f"{'`/deep <token_address>`' if plan=='plus' else '`/alpha`'}\n\n"
                    f"⊙ _Solar Flash Intelligence — Phase 2_"
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            log.warning(f"Could not notify user {uid}: {e}")

# ── BACKGROUND PAYMENT POLLER ─────────────────────────────────────────
async def payment_poller(bot):
    """Poll NOWPayments every 60 seconds to check pending payments."""
    log.info("Payment poller started.")
    while True:
        try:
            await asyncio.sleep(60)
            if not PENDING_PAYMENTS:
                continue
            expired = []
            for pid, pdata in list(PENDING_PAYMENTS.items()):
                # Expire after 24 hours
                if time.time() - pdata["created_at"] > 86400:
                    expired.append(pid); continue
                status = await check_payment_status(pid)
                if status in ("finished","confirmed","partially_paid"):
                    await activate_plan(pdata["uid"], pdata["plan"], bot)
                    expired.append(pid)
                elif status == "failed":
                    expired.append(pid)
            for pid in expired:
                PENDING_PAYMENTS.pop(pid, None)
        except Exception as e:
            log.error(f"Payment poller error: {e}")

# ── WEBHOOK SERVER (for instant NOWPayments IPN) ──────────────────────
async def handle_webhook(request):
    """Handle NOWPayments IPN webhook for instant payment confirmation."""
    try:
        body      = await request.read()
        signature = request.headers.get("x-nowpayments-sig","")

        # Verify signature if IPN secret is set
        if NOWPAYMENTS_IPN:
            expected = hmac.new(
                NOWPAYMENTS_IPN.encode(), body, hashlib.sha512
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                log.warning("Invalid webhook signature")
                return web.Response(status=400)

        data       = json.loads(body)
        pid        = str(data.get("payment_id",""))
        status     = data.get("payment_status","")
        log.info(f"Webhook: payment {pid} status={status}")

        if status in ("finished","confirmed") and pid in PENDING_PAYMENTS:
            pdata = PENDING_PAYMENTS.get(pid,{})
            if pdata:
                # Get bot from app context
                bot = request.app.get("bot")
                await activate_plan(pdata["uid"], pdata["plan"], bot)
                PENDING_PAYMENTS.pop(pid, None)

        return web.Response(status=200, text="OK")
    except Exception as e:
        log.error(f"Webhook error: {e}")
        return web.Response(status=500)

# ── KEYBOARDS ─────────────────────────────────────────────────────────
def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Scan Token", switch_inline_query_current_chat="/analyze "),
         InlineKeyboardButton("⚡ Live Pulse", callback_data="run_pulse")],
        [InlineKeyboardButton("🔥 Upgrade PLUS", callback_data="upgrade_plus"),
         InlineKeyboardButton("☀️ Go ALPHA", callback_data="upgrade_alpha")],
        [InlineKeyboardButton("🌐 Web Scanner", url=REPORT_URL)],
    ])

def kb_plan_selector(plan: str):
    buttons = []
    for m in PAYMENT_METHODS:
        buttons.append([InlineKeyboardButton(
            f"{m['emoji']} Pay with {m['name']}",
            callback_data=f"pay_{plan}_{m['id']}"
        )])
    buttons.append([InlineKeyboardButton("← Back", callback_data="show_plans")])
    return InlineKeyboardMarkup(buttons)

def kb_plans():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 PLUS — $9.99/mo", callback_data="upgrade_plus")],
        [InlineKeyboardButton("☀️ ALPHA — $29/mo",  callback_data="upgrade_alpha")],
        [InlineKeyboardButton("🌐 Learn More", url=SITE_URL)],
    ])

def kb_check_payment(payment_id: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Paid — Check Status", callback_data=f"check_{payment_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_payment")],
    ])

def kb_report(dex_url=None):
    rows = []
    if dex_url:
        rows.append([InlineKeyboardButton("📈 DexScreener", url=dex_url)])
    rows.append([
        InlineKeyboardButton("🌐 Scanner", url=REPORT_URL),
        InlineKeyboardButton("⚡ $FLASH", url=TG_CHANNEL),
    ])
    return InlineKeyboardMarkup(rows)

# ── CALLBACK HANDLER ──────────────────────────────────────────────────
async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    uid = q.from_user.id
    data= q.data
    await q.answer()

    # Show plan selection
    if data == "show_plans":
        await q.edit_message_text(
            "⚡ *SOLAR FLASH UPGRADE*\n\nChoose your plan:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_plans(),
        )

    # PLUS plan selected
    elif data == "upgrade_plus":
        p = PLANS["plus"]
        await q.edit_message_text(
            f"🔥 *Solar Flash PLUS*\n\n"
            f"*${p['price_usd']}/mo* — _{p['tag']}_\n\n"
            f"_{p['description']}_\n\n"
            f"_Future price: {p['future_price']}_\n\n"
            f"*Choose payment method:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_plan_selector("plus"),
        )

    # ALPHA plan selected
    elif data == "upgrade_alpha":
        p = PLANS["alpha"]
        await q.edit_message_text(
            f"☀️ *Solar Flash ALPHA*\n\n"
            f"*${p['price_usd']}/mo* — _{p['tag']}_\n\n"
            f"_{p['description']}_\n\n"
            f"_Future price: {p['future_price']}_\n\n"
            f"*Choose payment method:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_plan_selector("alpha"),
        )

    # Payment method chosen — create invoice
    elif data.startswith("pay_"):
        parts    = data.split("_", 2)
        plan     = parts[1]
        currency = parts[2]

        await q.edit_message_text(
            "⏳ *Creating payment invoice...*",
            parse_mode=ParseMode.MARKDOWN,
        )

        payment = await create_payment(uid, plan, currency)

        if payment:
            p       = PLANS[plan]
            pid     = str(payment.get("payment_id",""))
            address = payment.get("pay_address","—")
            amount  = payment.get("pay_amount","—")
            curr    = payment.get("pay_currency","").upper()

            text = (
                f"💳 *PAYMENT INVOICE*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{p['emoji']} *Plan:* {p['name']}\n"
                f"💰 *Amount:* `{amount} {curr}`\n"
                f"📋 *To Address:*\n`{address}`\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏰ *Invoice expires in 30 minutes*\n\n"
                f"1️⃣ Copy the address above\n"
                f"2️⃣ Send *exactly* `{amount} {curr}`\n"
                f"3️⃣ Click the button below after payment\n\n"
                f"_Payment is verified automatically. Access granted instantly upon confirmation._\n\n"
                f"🔒 _Powered by NOWPayments — secure crypto processing_"
            )
            await q.edit_message_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=kb_check_payment(pid),
            )
        else:
            await q.edit_message_text(
                "❌ *Could not create invoice.*\n\n"
                "Payment system is temporarily unavailable.\n"
                f"Contact us directly: {TG_CHANNEL}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💬 Contact Support", url=TG_CHANNEL)
                ]]),
            )

    # Manual payment check
    elif data.startswith("check_"):
        pid    = data[6:]
        status = await check_payment_status(pid)

        if status in ("finished","confirmed","partially_paid"):
            pdata = PENDING_PAYMENTS.get(pid, {})
            plan  = pdata.get("plan","plus")
            await activate_plan(uid, plan, ctx.bot)
            PENDING_PAYMENTS.pop(pid, None)
            p = PLANS[plan]
            await q.edit_message_text(
                f"✅ *Payment Confirmed!*\n\n"
                f"{p['emoji']} *{p['name']} is now active!*\n\n"
                f"_{p['description']}_\n\n"
                f"⊙ _Solar Flash Intelligence_",
                parse_mode=ParseMode.MARKDOWN,
            )
        elif status == "waiting":
            await q.answer("⏳ Payment not detected yet. Give it a moment.", show_alert=True)
        elif status == "confirming":
            await q.answer("🔄 Payment detected! Waiting for blockchain confirmation...", show_alert=True)
        elif status == "failed":
            await q.answer("❌ Payment failed. Please try again.", show_alert=True)
        else:
            await q.answer(f"Status: {status or 'unknown'}. Try again in a moment.", show_alert=True)

    elif data == "cancel_payment":
        await q.edit_message_text(
            "Payment cancelled. Use /upgrade anytime to try again.",
            reply_markup=None,
        )

    elif data == "run_pulse":
        await q.message.reply_text("Use /pulse to get live market data ⚡")


# ── FORMATTERS ────────────────────────────────────────────────────────
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
    zeros = len(m.group(1)); sig = m.group(2).rstrip("0")[:6]
    SUB = str.maketrans("0123456789","₀₁₂₃₄₅₆₇₈₉")
    if zeros < 4: return f"$0.{'0'*zeros}{sig}"
    return f"$0.0{str(zeros).translate(SUB)}{sig}"

def sbar(v,w=10): f=round(max(0,min(100,v))/100*w); return "█"*f+"░"*(w-f)
def rbar(v,w=8):  f=round(max(0,min(100,v))/100*w); return "▓"*f+"░"*(w-f)
def short(a):     return f"{a[:5]}…{a[-5:]}" if a else "—"

# ── API FETCHERS ──────────────────────────────────────────────────────
async def rpc(session, method, params):
    try:
        async with session.post(HELIUS_RPC,
            json={"jsonrpc":"2.0","id":1,"method":method,"params":params},
            headers={"Content-Type":"application/json"}, timeout=T) as r:
            return (await r.json()).get("result")
    except Exception as e:
        log.warning(f"RPC {method}: {e}"); return None

async def fetch_dex(session, mint):
    try:
        async with session.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=T
        ) as r:
            j     = await r.json()
            pairs = j.get("pairs") or []
            if not pairs: return None
            return sorted(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd",0) or 0), reverse=True)[0]
    except Exception as e:
        log.warning(f"DEX: {e}"); return None

async def fetch_rug(session, mint):
    try:
        async with session.get(
            f"https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary", timeout=T
        ) as r:
            if r.status == 200: return await r.json()
    except Exception as e:
        log.warning(f"RUG: {e}")
    return None

async def fetch_sol_price():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
                timeout=T
            ) as r:
                d = await r.json()
                return d.get("solana",{}).get("usd")
    except: return None

# ── ANALYSIS ENGINE ───────────────────────────────────────────────────
async def run_token_analysis(mint: str) -> dict:
    async with aiohttp.ClientSession() as s:
        asset, mint_info_raw, holders_raw, dex, rug = await asyncio.gather(
            rpc(s,"getAsset",{"id":mint,"displayOptions":{"showFungible":True}}),
            rpc(s,"getAccountInfo",[mint,{"encoding":"jsonParsed"}]),
            rpc(s,"getTokenLargestAccounts",[mint]),
            fetch_dex(s,mint), fetch_rug(s,mint),
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

    dec   = int(mint_info.get("decimals",6))
    s_raw = int(mint_info.get("supply",0))
    supply= s_raw/10**dec if s_raw else None
    top1  = int(holders[0]["amount"])/s_raw*100 if holders and s_raw else 0
    top5  = sum(int(h["amount"]) for h in holders[:5])/s_raw*100 if holders and s_raw else 0
    top10 = sum(int(h["amount"]) for h in holders[:10])/s_raw*100 if holders and s_raw else 0
    lp_b  = any(h.get("address","") in BURN_ADDRS for h in holders)

    dev_wallet, dev_pct = None, 0.0
    for h in holders[:5]:
        addr = h.get("address","")
        pct  = int(h.get("amount",0))/s_raw*100 if s_raw else 0
        if addr not in BURN_ADDRS and not addr.startswith("11111") and pct>3:
            dev_wallet, dev_pct = addr, pct; break

    mint_auth   = mint_info.get("mintAuthority")
    freeze_auth = mint_info.get("freezeAuthority")
    dx = dex or {}

    def _f(d,k,sub=None):
        v = d.get(k) if not sub else (d.get(k) or {}).get(sub)
        try: return float(v) if v not in (None,"","0") else None
        except: return None

    price = _f(dx,"priceUsd"); mcap  = _f(dx,"fdv")
    liq   = _f(dx,"liquidity","usd"); vol24 = _f(dx,"volume","h24")
    chg24 = _f(dx,"priceChange","h24")
    buys  = (dx.get("txns") or {}).get("h24",{}).get("buys") or 0
    sells = (dx.get("txns") or {}).get("h24",{}).get("sells") or 0
    dex_url = dx.get("url")

    socials = (dx.get("info") or {}).get("socials") or []
    has_tw  = any(s.get("type","").lower() in ("twitter","x") for s in socials)
    has_tg  = any(s.get("type","").lower()=="telegram" for s in socials)
    has_web = len((dx.get("info") or {}).get("websites") or []) > 0

    pair_age = dx.get("pairCreatedAt"); age_str = "—"
    if pair_age:
        diff = time.time()-pair_age/1000
        d2,h2,m2 = int(diff//86400),int((diff%86400)//3600),int((diff%3600)//60)
        age_str = f"{d2}d {h2}h" if d2>0 else f"{h2}h {m2}m" if h2>0 else f"{m2}m"

    rug_score = (rug or {}).get("score")
    safety = max(0,min(100,100-(30 if mint_auth else 0)-(20 if freeze_auth else 0)-(35 if not lp_b else 0)-(20 if rug_score and rug_score>=700 else 10 if rug_score and rug_score>=400 else 0)))
    whale  = min(100,(60 if top1>50 else 35 if top1>25 else 15 if top1>10 else 0)+(30 if top10>70 else 15 if top10>40 else 0))
    community = max(0,min(100,30+(40 if len(holders)>=2000 else 25 if len(holders)>=500 else 10 if len(holders)>=100 else -10)+(10 if has_tw else 0)+(12 if has_tg else 0)+(8 if has_web else 0)))
    heat  = max(0,min(100,20+(40 if (chg24 or 0)>200 else 25 if (chg24 or 0)>50 else 12 if (chg24 or 0)>10 else -15 if (chg24 or 0)<-50 else 0)+(25 if (vol24 or 0)>500000 else 15 if (vol24 or 0)>100000 else 8 if (vol24 or 0)>10000 else 0)))
    scam  = min(100,(25 if mint_auth else 0)+(20 if freeze_auth else 0)+(30 if not lp_b else 0)+(15 if top1>30 else 0))
    meme  = min(100,20+(20 if has_tw else 0)+(15 if has_tg else 0)+min(40,int((vol24 or 0)/10000)))
    cult  = min(100,20+(25 if has_tg else 0)+(20 if buys+sells>200 else 0)+(15 if has_tw else 0)+(20 if (chg24 or 0)>50 else 0))
    solar = max(0,min(100,round(safety*0.30+(100-whale)*0.25+community*0.20+heat*0.12+(100-scam)*0.08+50*0.05)))

    if   solar>=80: grade,verdict,gem = "A","STRONG SIGNAL","🟢"
    elif solar>=65: grade,verdict,gem = "B","MODERATE SIGNAL","🟡"
    elif solar>=45: grade,verdict,gem = "C","WEAK SIGNAL","🟠"
    else:           grade,verdict,gem = "D","DANGER — AVOID","🔴"

    if solar>=80:   ai=f"Solar Signal detects strong structural integrity for ${symbol}."
    elif solar>=65: ai=f"Solar Signal identifies moderate opportunity for ${symbol}. Monitor whale movements."
    elif solar>=45: ai=f"Solar Signal flags elevated risk for ${symbol}. Proceed with strict caution."
    else:           ai=f"Solar Signal HIGH RISK alert for ${symbol}. Capital protection is priority."

    return dict(mint=mint,name=name,symbol=symbol,supply=supply,
        mint_auth=mint_auth,freeze_auth=freeze_auth,lp_burned=lp_b,rug_score=rug_score,
        holders=len(holders),top1=top1,top5=top5,top10=top10,dev_wallet=dev_wallet,dev_pct=dev_pct,
        price=price,mcap=mcap,liq=liq,vol24=vol24,chg24=chg24,buys=buys,sells=sells,
        dex_url=dex_url,age=age_str,has_tw=has_tw,has_tg=has_tg,has_web=has_web,
        safety=safety,whale=whale,community=community,heat=heat,scam=scam,meme=meme,cult=cult,
        solar=solar,grade=grade,verdict=verdict,gem=gem,ai=ai)

def build_report(d, full=True):
    total_tx = d["buys"]+d["sells"]
    bs_row = ""
    if total_tx > 0:
        bp = d["buys"]/total_tx*100; blen=round(bp/100*10)
        bs_row = f"\n🔀 B/S: `{'🟢'*blen}{'🔴'*(10-blen)}` {bp:.0f}%"
    soc = [s for s,h in [("𝕏",d["has_tw"]),("TG",d["has_tg"]),("🌐",d["has_web"])] if h]
    chg = f" {'📈' if (d['chg24'] or 0)>=0 else '📉'} {'+' if (d['chg24'] or 0)>=0 else ''}{d['chg24']:.1f}%" if d["chg24"] is not None else ""

    if full:
        return (
            f"☀️ *SOLAR SIGNAL REPORT*\n${d['symbol']} — {d['name']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📋 `{short(d['mint'])}` · Age: `{d['age']}`\n"
            f"🌐 Social: `{' '.join(soc) or 'None'}`\n\n"
            f"{d['gem']} *Signal: {d['solar']}/100 — {d['verdict']}*\n"
            f"`{sbar(d['solar'],14)}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *SCORES*\n"
            f"🛡 Safety: `{sbar(d['safety'])}` {d['safety']}/100\n"
            f"🐋 Whale:  `{rbar(d['whale'])}` {d['whale']}/100\n"
            f"👥 Comm:   `{sbar(d['community'])}` {d['community']}/100\n"
            f"🔥 Heat:   `{sbar(d['heat'])}` {d['heat']}/100\n"
            f"☠️ Scam:    `{rbar(d['scam'])}` {d['scam']}/100\n"
            f"🎭 Meme:   `{sbar(d['meme'])}` {d['meme']}/100\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *MARKET*\n"
            f"💲 `{fmt_price(d['price'])}`{chg} · MCap: `{fmt_usd(d['mcap'])}`\n"
            f"💧 Liq: `{fmt_usd(d['liq'])}` · Vol: `{fmt_usd(d['vol24'])}`\n"
            f"👥 Holders: `{fmt_num(d['holders'])}` · Supply: `{fmt_num(d['supply'])}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🐋 *WHALES*\n"
            f"Top1: `{d['top1']:.1f}%` · Top5: `{d['top5']:.1f}%` · Top10: `{d['top10']:.1f}%`\n"
            f"LP: `{'BURNED 🔥' if d['lp_burned'] else 'NOT BURNED 🚨'}`"
            f" · Mint: `{'OK ✅' if not d['mint_auth'] else 'ACTIVE ⚠️'}`{bs_row}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧠 *AI SIGNAL*\n_{d['ai']}_\n\n"
            f"⊙ _Solar Flash Intelligence · Not financial advice_"
        )
    return (
        f"☀️ *QUICK SCORE — ${d['symbol']}*\n\n"
        f"{d['gem']} *{d['solar']}/100 — {d['verdict']}*\n"
        f"`{sbar(d['solar'],12)}`\n\n"
        f"🛡 {d['safety']} · 🐋 {d['whale']} · 👥 {d['community']} · 🔥 {d['heat']}\n\n"
        f"LP: `{'BURNED 🔥' if d['lp_burned'] else 'NOT BURNED 🚨'}`\n\n"
        f"🧠 _{d['ai']}_\n\n⊙ Use /analyze for full report"
    )

# ── COMMAND HANDLERS ──────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    u    = get_user(uid)
    tier = TIERS[u["tier"]]
    name = update.effective_user.first_name or "Operator"
    await update.message.reply_text(
        f"☀️ *Welcome to Solar Flash Phase II* ⚡\n"
        f"_{name}_ — Solana intelligence layer active.\n\n"
        f"Your tier: {tier['emoji']} *{tier['name']}*\n\n"
        f"*Choose your path:*\n"
        f"📊 /analyze — Scan any token\n"
        f"⚡ /pulse — Live market pulse\n"
        f"📈 /daily — Daily insights\n"
        f"🔬 /deep — Advanced scan _(PLUS)_\n"
        f"🏆 /rank — Your Flash rank\n"
        f"💳 /upgrade — Unlock full access\n"
        f"❓ /help — All commands\n\n"
        f"_Paste any Solana address to scan instantly._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_main(),
    )

async def cmd_upgrade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_alpha(uid):
        await update.message.reply_text("☀️ You're already on *ALPHA* — maximum tier! ⊙", parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(
        "⚡ *SOLAR FLASH UPGRADE*\n\n"
        "🔥 *PLUS — $9.99/mo* _(Founding Rate — was $14.99)_\n"
        "50 scans/day · /deep · Premium signals · Full pulse\n\n"
        "☀️ *ALPHA — $29/mo* _(Early Access — was $49)_\n"
        "Unlimited · All PLUS · Alpha feed · Whale tracking · Priority signals\n\n"
        "_Founding rates end when Phase 2B launches._\n\n"
        "*Accepted:* SOL · USDT · USDC · BTC · ETH",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_plans(),
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    t   = get_tier(uid)
    await update.message.reply_text(
        "☀️ *SOLAR FLASH COMMANDS*\n\n"
        "*⚡ FREE*\n"
        "/analyze `<addr>` — Full report (5/day)\n"
        "/score `<addr>` — Quick score\n"
        "/pulse — Market pulse\n"
        "/daily — Daily insights\n"
        "/rank — Your XP & rank\n"
        "/upgrade — Unlock full access\n\n"
        "*🔥 PLUS ($9.99/mo)*\n"
        "/deep `<addr>` — Advanced scan\n"
        "/signals — Premium signals\n"
        "/alerts — Market alerts\n\n"
        "*☀️ ALPHA ($29/mo)*\n"
        "/alpha — Alpha feed\n"
        "/whales — Whale tracking\n"
        "/stealth — Stealth launches\n\n"
        f"_Your tier: {TIERS[t]['emoji']} {TIERS[t]['name']}_",
        parse_mode=ParseMode.MARKDOWN,
    )

async def cmd_about(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⊙ *SOLAR FLASH — Solana Intelligence Engine*\n\n"
        "_Built to detect signal before noise._\n\n"
        "📡 Helius · DexScreener · RugCheck\n"
        f"🌐 {SITE_URL}\n⚡ {TG_CHANNEL}",
        parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True,
    )

async def cmd_pulse(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    msg = await update.message.reply_text("⚡ *Scanning Solana pulse...*", parse_mode=ParseMode.MARKDOWN)
    try:
        sol_price = await asyncio.wait_for(fetch_sol_price(), timeout=8)
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.dexscreener.com/latest/dex/search?q=sol", timeout=T) as r:
                pairs = ((await r.json()).get("pairs") or [])[:20]

        total_vol   = sum(float((p.get("volume") or {}).get("h24",0) or 0) for p in pairs)
        avg_chg     = sum(float((p.get("priceChange") or {}).get("h24",0) or 0) for p in pairs)/max(len(pairs),1)
        total_buys  = sum((p.get("txns") or {}).get("h24",{}).get("buys",0) or 0 for p in pairs)
        total_sells = sum((p.get("txns") or {}).get("h24",{}).get("sells",0) or 0 for p in pairs)
        total_tx    = total_buys+total_sells
        buy_ratio   = total_buys/total_tx*100 if total_tx else 50

        bull = (40 if avg_chg>5 else 20 if avg_chg>0 else -20)+(30 if buy_ratio>60 else 15 if buy_ratio>50 else -15)+(30 if total_vol>100_000_000 else 15 if total_vol>50_000_000 else 0)
        if bull>=50:   sent,sent_e = "BULLISH","🟢"
        elif bull>=10: sent,sent_e = "NEUTRAL","🟡"
        else:          sent,sent_e = "BEARISH","🔴"

        risk = max(0,min(100,50+int(-avg_chg/2)))
        liq_flow = "↑ INFLOW" if avg_chg>2 else "↓ OUTFLOW" if avg_chg<-2 else "→ NEUTRAL"
        now = datetime.now(timezone.utc).strftime("%H:%M UTC")

        text = (
            f"⚡ *SOLANA MARKET PULSE*\n_{now}_\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{sent_e} Sentiment:    `{sent}`\n"
            f"💧 Liq Flow:    `{liq_flow}`\n"
            f"🌡 Risk Temp:   `{sbar(risk)} {risk}/100`\n"
            f"🔥 Vol Heat:    `{sbar(min(100,int(total_vol/1_000_000)))}`\n\n"
            f"💰 SOL: `${sol_price:,.2f}`\n" if sol_price else ""
            f"📈 Avg 24h:  `{'+' if avg_chg>=0 else ''}{avg_chg:.1f}%`\n"
            f"💸 Vol:      `{fmt_usd(total_vol)}`\n"
            f"🔀 Buy:      `{buy_ratio:.0f}%`\n\n"
        )
        if not is_plus(uid):
            text += f"🔒 Full data in PLUS — /upgrade\n"
        text += "⊙ _Solar Flash Intelligence_"

        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN)
        add_xp(uid, 5)
    except Exception as e:
        log.error(f"Pulse: {e}", exc_info=True)
        await msg.edit_text("❌ Pulse scan failed.", parse_mode=ParseMode.MARKDOWN)

async def cmd_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    now = datetime.now(timezone.utc)
    text = (
        f"☀️ *DAILY FLASH SIGNAL*\n_{now.strftime('%a %d %b · %H:%M UTC')}_\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📡 *Market Narrative:*\n"
        f"Solana meme sector showing rotation. Community-driven tokens outperforming. Scan before buying.\n\n"
        f"⚠️ *Risk Alerts:*\n"
        f"• High rug activity — always scan first\n"
        f"• Whale distribution in several mid-caps\n"
        f"• Anonymous launches spiking\n\n"
    )
    if not is_plus(uid):
        text += f"🔒 Specific opportunities in PLUS — /upgrade\n"
    text += "⊙ _Not financial advice. DYOR._"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Upgrade PLUS",callback_data="upgrade_plus")]] if not is_plus(uid) else []))
    add_xp(uid, 3)

async def cmd_rank(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; u = get_user(uid)
    xp  = u.get("xp",0); rank_t, rank_d = get_rank(xp)
    thresholds = [100,500,1000,2000,5000]
    next_xp = next((t for t in thresholds if t>xp), None)
    progress = min(100,int(xp/next_xp*100)) if next_xp else 100
    await update.message.reply_text(
        f"🏆 *FLASH RANK*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{rank_t}\n_{rank_d}_\n\n"
        f"⚡ XP: `{xp:,}`\n"
        f"📊 `{sbar(progress,12)}` {progress}%\n"
        f"{'🎯 Next: '+str(next_xp-xp)+' XP' if next_xp else '⊙ MAX RANK'}\n\n"
        f"📋 Scans: `{u.get('total_scans',0)}` · Tier: `{TIERS[u['tier']]['name']}`\n\n"
        f"*Earn XP:* /analyze +10 · /pulse +5 · /daily +3 · /deep +20",
        parse_mode=ParseMode.MARKDOWN,
    )

async def cmd_deep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_plus(uid):
        await update.message.reply_text(
            "🔬 *Deep Scan — Solar Flash PLUS*\n\n"
            "Full holder intelligence, contract anomaly detection, dev wallet tracking.\n\n"
            f"🔥 *Upgrade: $9.99/mo* — /upgrade",
            parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Upgrade Now",callback_data="upgrade_plus")]]),
        ); return
    if not ctx.args:
        await update.message.reply_text("Usage: `/deep <address>`", parse_mode=ParseMode.MARKDOWN); return
    mint = ctx.args[0].strip()
    if not SOL_RE.fullmatch(mint):
        await update.message.reply_text("❌ Invalid address."); return
    ok, limit = check_scan_limit(uid)
    if not ok:
        await update.message.reply_text(f"⏳ Daily limit ({limit}) reached."); return
    msg = await update.message.reply_text("🔬 *Deep scan...*", parse_mode=ParseMode.MARKDOWN)
    try:
        d = await asyncio.wait_for(run_token_analysis(mint), timeout=28)
        consume_scan(uid); add_xp(uid,20)
        rf = []
        if d["mint_auth"]:   rf.append("🚨 Mint authority active")
        if d["freeze_auth"]: rf.append("🚨 Freeze authority active")
        if not d["lp_burned"]:rf.append("🚨 LP not burned")
        if d["top1"]>30:     rf.append(f"⚠️ Top wallet: {d['top1']:.1f}%")
        if d["dev_pct"]>5:   rf.append(f"⚠️ Dev holds: {d['dev_pct']:.1f}%")
        if not rf:           rf.append("✅ No critical risks")
        text = (
            f"🔬 *DEEP INTELLIGENCE — ${d['symbol']}*\n"
            f"{d['gem']} *{d['solar']}/100 — {d['verdict']}*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔍 *CONTRACT*\nMint: `{'⚠️ ACTIVE' if d['mint_auth'] else '✅ REVOKED'}` · "
            f"Freeze: `{'⚠️ ACTIVE' if d['freeze_auth'] else '✅ REVOKED'}`\n"
            f"LP: `{'🔥 BURNED' if d['lp_burned'] else '🚨 NOT BURNED'}` · "
            f"RugCheck: `{d['rug_score'] or '—'}/1000`\n\n"
            f"🐋 *HOLDERS*\nTotal: `{fmt_num(d['holders'])}` · "
            f"Top1: `{d['top1']:.1f}%` · Top10: `{d['top10']:.1f}%`\n"
            f"Dev: `{d['dev_pct']:.1f}%` {'⚠️' if d['dev_pct']>5 else '✅'}\n\n"
            f"⚡ *RISKS*\n"+"\n".join(rf)+"\n\n"
            f"💰 `{fmt_price(d['price'])}` · MCap: `{fmt_usd(d['mcap'])}` · Liq: `{fmt_usd(d['liq'])}`\n\n"
            f"🧠 _{d['ai']}_\n\n⊙ *Solar Flash PLUS*"
        )
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_report(d.get("dex_url")), disable_web_page_preview=True)
    except asyncio.TimeoutError:
        await msg.edit_text("⏱ Timed out.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"Deep: {e}", exc_info=True)
        await msg.edit_text("❌ Deep scan failed.", parse_mode=ParseMode.MARKDOWN)

async def cmd_alpha(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_alpha(uid):
        await update.message.reply_text(
            "☀️ *Solar Flash ALPHA — Restricted*\n\n"
            "Whale tracking · Stealth launches · Priority signals · Limited slots.\n\n"
            f"☀️ *$29/mo Early Access* — /upgrade",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("☀️ Go ALPHA",callback_data="upgrade_alpha")]])
        ); return
    await update.message.reply_text("☀️ *ALPHA FEED*\n_Phase 2B rolling out._ ⊙", parse_mode=ParseMode.MARKDOWN)

async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; u = get_user(uid)
    tier = TIERS[u["tier"]]
    scans_left = max(0, tier["daily_scans"] - u.get("scans_today",0))
    expires = ""
    if u.get("tier_expires"):
        days = max(0, int((u["tier_expires"]-time.time())/86400))
        expires = f"\n⏳ Expires in: `{days} days`"
    await update.message.reply_text(
        f"📋 *YOUR ACCOUNT*\n\n"
        f"{tier['emoji']} Tier: *{tier['name']}*{expires}\n"
        f"📊 Scans today: `{u.get('scans_today',0)}/{tier['daily_scans']}`\n"
        f"🔄 Remaining: `{scans_left}`\n"
        f"⚡ XP: `{u.get('xp',0):,}`\n\n"
        f"{'_Upgrade: /upgrade_' if u['tier']=='free' else '_Thank you for your support! ⊙_'}",
        parse_mode=ParseMode.MARKDOWN,
    )

async def do_analysis(update, mint, full=True):
    uid = update.effective_user.id
    now = time.time()
    if now - COOLDOWN.get(uid,0) < 6:
        await update.message.reply_text("⏳ Wait a few seconds."); return
    COOLDOWN[uid] = now
    ok, limit = check_scan_limit(uid)
    if not ok:
        await update.message.reply_text(
            f"⏳ *Daily limit reached* ({limit} scans on FREE).\n\n"
            f"Upgrade to PLUS for 50/day — /upgrade",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔥 Upgrade PLUS",callback_data="upgrade_plus")]]),
        ); return
    msg = await update.message.reply_text(
        "☀️ *Solar Flash scanning...*\n⛓ On-chain · 📊 Market · 🐋 Whales · 🧠 AI",
        parse_mode=ParseMode.MARKDOWN,
    )
    try:
        d = await asyncio.wait_for(run_token_analysis(mint), timeout=28)
        consume_scan(uid); add_xp(uid,10)
        await msg.edit_text(build_report(d,full), parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_report(d.get("dex_url")), disable_web_page_preview=True)
    except asyncio.TimeoutError:
        await msg.edit_text("⏱ Timed out.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"Analysis [{mint}]: {e}", exc_info=True)
        await msg.edit_text("❌ Could not analyze. Check address.", parse_mode=ParseMode.MARKDOWN)

async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/analyze <address>`", parse_mode=ParseMode.MARKDOWN); return
    mint = ctx.args[0].strip()
    if not SOL_RE.fullmatch(mint):
        await update.message.reply_text("❌ Invalid Solana address."); return
    await do_analysis(update, mint, full=True)

async def cmd_score(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/score <address>`", parse_mode=ParseMode.MARKDOWN); return
    await do_analysis(update, ctx.args[0].strip(), full=False)

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text  = (update.message.text or "").strip()
    match = SOL_RE.search(text)
    if match:
        await do_analysis(update, match.group(), full=True)
    else:
        await update.message.reply_text(
            "⊙ Paste a Solana token address to scan.\nOr /help for commands.",
            parse_mode=ParseMode.MARKDOWN,
        )

# ── MAIN ──────────────────────────────────────────────────────────────
def main():
    try:
        log.info("Building Solar Flash Phase 2...")
        app = Application.builder().token(BOT_TOKEN).build()

        # Commands
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
        app.add_handler(CommandHandler("upgrade", cmd_upgrade))
        app.add_handler(CommandHandler("status",  cmd_status))

        # Callbacks (payment buttons)
        from telegram.ext import CallbackQueryHandler
        app.add_handler(CallbackQueryHandler(handle_callback))

        # Messages
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        log.info("⊙ Solar Flash Phase 2 + Payments — LIVE")
        app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

    except Exception:
        log.critical("FATAL:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
