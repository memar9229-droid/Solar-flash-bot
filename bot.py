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


def fmt_num(n):
    if n is None:
        return "—"
    if n >= 1e9:
        return f"{n/1e9:.2f}B"
    if n >= 1e6:
        return f"{n/1e6:.2f}M"
    if n >= 1e3:
        return f"{n/1e3:.1f}K"
    return f"{int(n):,}"


def fmt_usd(n):
    if n is None:
        return "—"
    if n >= 1e9:
        return f"${n/1e9:.2f}B"
    if n >= 1e6:
        return f"${n/1e6:.2f}M"
    if n >= 1e3:
        return f"${n/1e3:.1f}K"
    return f"${n:.2f}"


def fmt_price(p):
    if p is None:
        return "—"
    if p == 0:
        return "$0"
    if p >= 1:
        return f"${p:,.4f}"
    if p >= 0.01:
        return f"${p:.6f}"
    s = f"{p:.30f}"
    m = re.match(r"^0\.(0*)(\d{1,8})", s)
    if not m:
        return f"${p:.12f}"
    zeros = len(m.group(1))
    sig = m.group(2).rstrip("0")[:6]
    SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    if zeros < 4:
        return f"$0.{'0'*zeros}{sig}"
    return f"$0.0{str(zeros).translate(SUB)}{sig}"


def sbar(v, w=10):
    f = round(max(0, min(100, v)) / 100 * w)
    return "█" * f + "░" * (w - f)


def rbar(v, w=8):
    f = round(max(0, min(100, v)) / 100 * w)
    return "▓" * f + "░" * (w - f)


def short(a):
    return f"{a[:5]}…{a[-5:]}" if a else "—"


async def rpc(session, method, params):
    try:
        async with session.post(
            HELIUS_RPC,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            headers={"Content-Type": "application/json"},
            timeout=T
        ) as r:
            return (await r.json()).get("result")
    except Exception as e:
        log.warning(f"RPC {method}: {e}")
        return None


async def fetch_dex(session, mint):
    try:
        async with session.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{mint}", timeout=T
        ) as r:
            j = await r.json()
            pairs = j.get("pairs") or []
            if not pairs:
                return None
            return sorted(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd", 0) or 0), reverse=True)[0]
    except Exception as e:
        log.warning(f"DexScreener: {e}")
        return None


async def fetch_rug(session, mint):
    try:
        async with session.get(
            f"https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary", timeout=T
        ) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        log.warning(f"RugCheck: {e}")
    return None


async def fetch_birdeye(session, mint):
    if not BIRDEYE_KEY:
        return {}
    try:
        async with session.get(
            f"https://public-api.birdeye.so/defi/token_overview",
            params={"address": mint},
            headers={"X-API-KEY": BIRDEYE_KEY, "x-chain": "solana"},
            timeout=T
        ) as r:
            if r.status == 200:
                return (await r.json()).get("data") or {}
    except Exception as e:
        log.warning(f"Birdeye: {e}")
    return {}


async def analyze(mint):
    async with aiohttp.ClientSession() as s:
        asset, mint_info_raw, holders_raw, dex, rug, be = await asyncio.gather(
            rpc(s, "getAsset", {"id": mint, "displayOptions": {"showFungible": True}}),
            rpc(s, "getAccountInfo", [mint, {"encoding": "jsonParsed"}]),
            rpc(s, "getTokenLargestAccounts", [mint]),
            fetch_dex(s, mint),
            fetch_rug(s, mint),
            fetch_birdeye(s, mint),
        )

    mint_info = {}
    if mint_info_raw:
        mint_info = ((mint_info_raw.get("value") or {}).get("data") or {}).get("parsed", {}).get("info", {})
    holders = (holders_raw or {}).get("value") or []

    meta = (asset or {}).get("content", {}).get("metadata", {})
    ti = (asset or {}).get("token_info", {}) or {}
    name = meta.get("name") or ti.get("symbol") or "Unknown"
    symbol = ti.get("symbol") or "???"

    decimals = int(mint_info.get("decimals", 6))
    supply_raw = int(mint_info.get("supply", 0))
    supply = supply_raw / 10 ** decimals if supply_raw else None
    top1 = int(holders[0]["amount"]) / supply_raw * 100 if holders and supply_raw else 0
    top5 = sum(int(h["amount"]) for h in holders[:5]) / supply_raw * 100 if holders and supply_raw else 0
    top10 = sum(int(h["amount"]) for h in holders[:10]) / supply_raw * 100 if holders and supply_raw else 0
    lp_burned = any(h.get("address", "") in BURN_ADDRS for h in holders)

    dev_wallet = None
    dev_pct = 0.0
    for h in holders[:5]:
        addr = h.get("address", "")
        pct = int(h.get("amount", 0)) / supply_raw * 100 if supply_raw else 0
        if addr not in BURN_ADDRS and not addr.startswith("11111") and pct > 3:
            dev_wallet = addr
            dev_pct = pct
            break

    mint_auth = mint_info.get("mintAuthority")
    freeze_auth = mint_info.get("freezeAuthority")

    dx = dex or {}

    def _f(d, k, sub=None):
        v = d.get(k) if not sub else (d.get(k) or {}).get(sub)
        try:
            return float(v) if v not in (None, "", "0") else None
        except Exception:
            return None

    price = _f(dx, "priceUsd")
    mcap = _f(dx, "fdv")
    liq = _f(dx, "liquidity", "usd")
    vol24 = _f(dx, "volume", "h24")
    chg24 = _f(dx, "priceChange", "h24")
    buys = (dx.get("txns") or {}).get("h24", {}).get("buys") or 0
    sells = (dx.get("txns") or {}).get("h24", {}).get("sells") or 0
    dex_url = dx.get("url")

    socials = (dx.get("info") or {}).get("socials") or []
    has_tw = any(s.get("type", "").lower() in ("twitter", "x") for s in socials)
    has_tg = any(s.get("type", "").lower() == "telegram" for s in socials)
    has_web = len((dx.get("info") or {}).get("websites") or []) > 0

    pair_age = dx.get("pairCreatedAt")
    age_str = "—"
    if pair_age:
        diff = time.time() - pair_age / 1000
        d2 = int(diff // 86400)
        h2 = int((diff % 86400) // 3600)
        m2 = int((diff % 3600) // 60)
        age_str = f"{d2}d {h2}h" if d2 > 0 else f"{h2}h {m2}m" if h2 > 0 else f"{m2}m"

    rug_score = (rug or {}).get("score")
    unique_w = be.get("uniqueWallet24h")

    safety = 100
    if mint_auth:
        safety -= 30
    if freeze_auth:
        safety -= 20
    if not lp_burned:
        safety -= 35
    if rug_score and rug_score >= 700:
        safety -= 20
    elif rug_score and rug_score >= 400:
        safety -= 10
    safety = max(0, min(100, safety))

    whale = 0
    if top1 > 50:
        whale += 60
    elif top1 > 25:
        whale += 35
    elif top1 > 10:
        whale += 15
    if top10 > 70:
        whale += 30
    elif top10 > 40:
        whale += 15
    whale = min(100, whale)

    community = 30
    h_count = len(holders)
    if h_count >= 2000:
        community += 40
    elif h_count >= 500:
        community += 25
    elif h_count >= 100:
        community += 10
    else:
        community -= 10
    if has_tw:
        community += 10
    if has_tg:
        community += 12
    if has_web:
        community += 8
    community = max(0, min(100, community))

    heat = 20
    if chg24:
        if chg24 > 200:
            heat += 40
        elif chg24 > 50:
            heat += 25
        elif chg24 > 10:
            heat += 12
        elif chg24 < -50:
            heat -= 15
    if vol24:
        if vol24 > 500000:
            heat += 25
        elif vol24 > 100000:
            heat += 15
        elif vol24 > 10000:
            heat += 8
    total_tx = buys + sells
    if total_tx > 0 and buys > sells * 1.5:
        heat += 10
    heat = max(0, min(100, heat))

    scam = 0
    if mint_auth:
        scam += 25
    if freeze_auth:
        scam += 20
    if not lp_burned:
        scam += 30
    if top1 > 30:
        scam += 15
    scam = min(100, scam)

    meme = min(100, 20 + (20 if has_tw else 0) + (15 if has_tg else 0) + min(40, int((vol24 or 0) / 10000)))
    cult = min(100, 20 + (25 if has_tg else 0) + (20 if total_tx > 200 else 0) + (15 if has_tw else 0) + (20 if (chg24 or 0) > 50 else 0))

    solar = round(safety * 0.30 + (100 - whale) * 0.25 + community * 0.20 + heat * 0.12 + (100 - scam) * 0.08 + 50 * 0.05)
    solar = max(0, min(100, solar))

    if solar >= 80:
        grade, verdict, gem = "A", "STRONG SIGNAL", "🟢"
    elif solar >= 65:
        grade, verdict, gem = "B", "MODERATE SIGNAL", "🟡"
    elif solar >= 45:
        grade, verdict, gem = "C", "WEAK SIGNAL", "🟠"
    else:
        grade, verdict, gem = "D", "DANGER — AVOID", "🔴"

    flags = []
    goods = []
    if mint_auth:
        flags.append("⚠️ Mint authority NOT revoked — supply can be inflated")
    else:
        goods.append("✅ Mint authority revoked — supply fixed")
    if freeze_auth:
        flags.append("⚠️ Freeze authority active — wallets can be frozen")
    else:
        goods.append("✅ Freeze authority revoked")
    if lp_burned:
        goods.append("🔥 Liquidity BURNED — rug pull impossible")
    else:
        flags.append("🚨 Liquidity NOT secured — rug pull risk OPEN")
    if top1 > 50:
        flags.append(f"🚨 Top wallet: {top1:.1f}% — extreme concentration")
    elif top1 > 25:
        flags.append(f"⚠️ Top wallet: {top1:.1f}% — high whale risk")
    else:
        goods.append(f"✅ Top wallet: {top1:.1f}% — healthy distribution")
    if top10 > 70:
        flags.append(f"🚨 Top 10 hold {top10:.1f}% — cartel clustering")
    else:
        goods.append(f"✅ Top 10 hold {top10:.1f}% — distributed")
    if has_tw:
        goods.append("✅ X/Twitter confirmed")
    if has_tg:
        goods.append("✅ Telegram community active")
    if has_web:
        goods.append("✅ Website present")
    if not has_tw and not has_tg and not has_web:
        flags.append("⚠️ No social presence detected")

    if solar >= 80:
        ai = f"Solar Signal detects strong structural integrity for ${symbol}. Contract architecture is secure and community signals are positive."
    elif solar >= 65:
        ai = f"Solar Signal identifies moderate opportunity for ${symbol} with manageable risk profile. Monitor whale movements closely."
    elif solar >= 45:
        ai = f"Solar Signal flags elevated risk for ${symbol}. Structural safety is compromised. Proceed with strict caution and small position sizing."
    else:
        ai = f"Solar Signal issues HIGH RISK alert for ${symbol}. Multiple critical red flags detected. Capital protection is priority."

    bs_row = ""
    if total_tx > 0:
        bp = buys / total_tx * 100
        blen = round(bp / 100 * 10)
        bs_row = f"\n🔀 B/S:         `{'🟢'*blen}{'🔴'*(10-blen)}` {bp:.0f}% buy\n               {buys} buys / {sells} sells"

    soc = []
    if has_tw:
        soc.append("𝕏")
    if has_tg:
        soc.append("TG")
    if has_web:
        soc.append("🌐")

    chg_str = ""
    if chg24 is not None:
        arrow = "📈" if chg24 >= 0 else "📉"
        sign = "+" if chg24 >= 0 else ""
        chg_str = f" {arrow} {sign}{chg24:.1f}%"

    dev_line = f"\n👨‍💻 Dev Wallet:  `{short(dev_wallet)}` ({dev_pct:.1f}%)" if dev_wallet else ""
    uw_line = f"\n👛 Unique W 24h:`{fmt_num(unique_w)}`" if unique_w else ""

    flag_txt = "\n".join(flags[:5]) if flags else "No critical flags"
    good_txt = "\n".join(goods[:4]) if goods else ""

    sell_s = "RESTRICTED" if scam >= 60 else "CAUTION" if scam >= 30 else "LIKELY OK"
    sell_e = "🚨" if scam >= 60 else "⚠️" if scam >= 30 else "✅"

    report = (
        f"☀️ *SOLAR SIGNAL REPORT*\n"
        f"${symbol} — {name}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 `{short(mint)}`\n"
        f"🕐 Pair Age: `{age_str}`\n"
        f"🌐 Social:   `{' · '.join(soc) or 'None'}`\n\n"
        f"{gem} *Solar Signal: {solar}/100 — {verdict}*\n"
        f"`{sbar(solar, 14)}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *SUB-SCORES*\n"
        f"🛡 Safety:        `{sbar(safety)}` {safety}/100\n"
        f"🐋 Whale Risk:    `{rbar(whale)}` {whale}/100\n"
        f"👥 Community:    `{sbar(community)}` {community}/100\n"
        f"🔥 Narrative:    `{sbar(heat)}` {heat}/100\n"
        f"☠️ Scam Risk:     `{rbar(scam)}` {scam}/100\n"
        f"🎭 Meme Strength: `{sbar(meme)}` {meme}/100\n"
        f"⛪ Cult Potential:`{sbar(cult)}` {cult}/100\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *MARKET DATA*\n"
        f"💲 Price:      `{fmt_price(price)}`{chg_str}\n"
        f"📦 Mkt Cap:    `{fmt_usd(mcap)}`\n"
        f"💧 Liquidity:  `{fmt_usd(liq)}`\n"
        f"📊 Vol 24h:    `{fmt_usd(vol24)}`\n"
        f"🪙 Supply:     `{fmt_num(supply)}`\n"
        f"👥 Holders:    `{fmt_num(h_count)}`{uw_line}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🐋 *WHALE INTELLIGENCE*\n"
        f"🥇 Top Wallet: `{top1:.1f}%`\n"
        f"🏆 Top 5:      `{top5:.1f}%`\n"
        f"📊 Top 10:     `{top10:.1f}%`{dev_line}\n"
        f"🔥 LP Burned:  `{'YES ✅' if lp_burned else 'NO 🚨'}`{bs_row}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔒 *SELL RISK*\n"
        f"Sellability:   {sell_e} `{sell_s}`\n"
        f"Mint Auth:     `{'ACTIVE ⚠️' if mint_auth else 'REVOKED ✅'}`\n"
        f"Freeze Auth:   `{'ACTIVE ⚠️' if freeze_auth else 'REVOKED ✅'}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *KEY FINDINGS*\n"
        f"{flag_txt}\n"
        f"{good_txt}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🧠 *AI SIGNAL*\n"
        f"_{ai}_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⊙ *Solar Signal Bot* by $FLASH\n"
        f"_Not financial advice. DYOR._"
    )

    quick = (
        f"☀️ *QUICK SCORE — ${symbol}*\n\n"
        f"{gem} *{solar}/100 — {verdict}*\n"
        f"`{sbar(solar, 12)}`\n\n"
        f"🛡 Safety:    {safety}/100\n"
        f"🐋 Whale:     {whale}/100\n"
        f"👥 Community: {community}/100\n"
        f"🔥 Narrative: {heat}/100\n"
        f"🎭 Meme:      {meme}/100\n"
        f"☠️ Scam Risk:  {scam}/100\n\n"
        f"🔥 LP Burned: `{'YES ✅' if lp_burned else 'NO 🚨'}`\n\n"
        f"🧠 _{ai}_\n\n"
        f"⊙ Use /analyze for full report"
    )

    kb_rows = []
    if dex_url:
        kb_rows.append([InlineKeyboardButton("📈 DexScreener", url=dex_url)])
    kb_rows.append([
        InlineKeyboardButton("🌐 Web Scanner", url=REPORT_URL),
        InlineKeyboardButton("⚡ $FLASH", url=TG_CHANNEL),
    ])

    return report, quick, InlineKeyboardMarkup(kb_rows)


async def run_analysis(mint, full, update):
    uid = update.effective_user.id
    now = time.time()
    if now - COOLDOWN.get(uid, 0) < 8:
        await update.message.reply_text("⏳ Please wait a few seconds.")
        return
    COOLDOWN[uid] = now

    msg = await update.message.reply_text(
        "☀️ *Solar Signal scanning...*\n\n"
        "⛓ Fetching on-chain data\n"
        "📊 Pulling market data\n"
        "🐋 Analyzing whale activity\n"
        "🧠 Generating AI signal",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        report, quick, kb = await asyncio.wait_for(analyze(mint), timeout=28)
        text = report if full else quick
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb, disable_web_page_preview=True)
    except asyncio.TimeoutError:
        await msg.edit_text("⏱ *Timed out.* Please try again.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"Error [{mint}]: {e}", exc_info=True)
        await msg.edit_text("❌ *Could not analyze.* Check the address and try again.", parse_mode=ParseMode.MARKDOWN)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Web Scanner", url=REPORT_URL)],
        [InlineKeyboardButton("⚡ Join $FLASH", url=TG_CHANNEL)],
    ])
    await update.message.reply_text(
        "☀️ *SOLAR SIGNAL BOT*\n"
        "_by Solar Flash — Elite Solana Intelligence_\n\n"
        "Paste any Solana token address for a full risk report.\n\n"
        "/analyze `<address>` — Full report\n"
        "/score `<address>` — Quick score\n"
        "/help — How to use\n"
        "/about — About $FLASH",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "☀️ *HOW TO USE*\n\n"
        "Paste any Solana token address:\n"
        "`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`\n\n"
        "/analyze `<address>` — Full intelligence report\n"
        "/score `<address>` — Quick score card\n\n"
        "*What we analyze:*\n"
        "• Mint & Freeze authority\n"
        "• LP burn status\n"
        "• Whale concentration\n"
        "• Dev wallet detection\n"
        "• Price, market cap, volume\n"
        "• Buy/sell pressure\n"
        "• Social presence\n"
        "• Meme & cult potential\n"
        "• RugCheck risk scan\n"
        "• AI intelligence summary",
        parse_mode=ParseMode.MARKDOWN
    )


async def cmd_about(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⊙ *SOLAR SIGNAL BOT — by Solar Flash*\n\n"
        "_Built to detect signal before noise._\n\n"
        f"🌐 {REPORT_URL}\n"
        f"⚡ {TG_CHANNEL}\n"
        f"𝕏 {X_URL}",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/analyze <address>`", parse_mode=ParseMode.MARKDOWN)
        return
    mint = ctx.args[0].strip()
    if not SOL_RE.fullmatch(mint):
        await update.message.reply_text("❌ Invalid Solana address.")
        return
    await run_analysis(mint, full=True, update=update)


async def cmd_score(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/score <address>`", parse_mode=ParseMode.MARKDOWN)
        return
    await run_analysis(ctx.args[0].strip(), full=False, update=update)


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    match = SOL_RE.search(text)
    if match:
        await run_analysis(match.group(), full=True, update=update)
    else:
        await update.message.reply_text(
            "⊙ Paste a Solana token address to scan.\n\n"
            "Example:\n`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`",
            parse_mode=ParseMode.MARKDOWN
        )


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is required")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("about",   cmd_about))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("score",   cmd_score))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("⊙ Solar Signal Bot is live...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

    
