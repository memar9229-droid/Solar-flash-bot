"""
⊙ SOLAR SIGNAL BOT — by Solar Flash
Single-file implementation using only requests library.
Compatible with Python 3.14+
"""
import os
import re
import time
import logging
import threading
import asyncio
import aiohttp

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ── CONFIG ───────────────────────────────────────────────────────────
BOT_TOKEN  = os.getenv("BOT_TOKEN",  "8609897160:AAG-bhw2pLlyHoF8mQiSXvHhOxBpRIRtFok")
HELIUS_KEY = os.getenv("HELIUS_KEY", "3ef572d9-b813-4361-bf5b-3f7a4bff3985")
HELIUS_RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
TG_API     = f"https://api.telegram.org/bot{BOT_TOKEN}"
REPORT_URL = "https://solar-flash-web.vercel.app/report"
TG_CHANNEL = "https://t.me/SolarFlash_Sol"
SOL_RE     = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")
BURN_ADDRS = {"1nc1nerator11111111111111111111111111111111","11111111111111111111111111111111"}
_rate: dict = {}

# ── TELEGRAM API ──────────────────────────────────────────────────────
import requests as req

def tg(method, **data):
    try:
        r = req.post(f"{TG_API}/{method}", json=data, timeout=10)
        return r.json()
    except Exception as e:
        log.error(f"TG error: {e}")
        return {}

def send(chat_id, text, parse_mode="Markdown", reply_markup=None, disable_preview=True):
    data = dict(chat_id=chat_id, text=text, parse_mode=parse_mode,
                disable_web_page_preview=disable_preview)
    if reply_markup:
        data["reply_markup"] = reply_markup
    return tg("sendMessage", **data)

def edit(chat_id, msg_id, text, parse_mode="Markdown", reply_markup=None):
    data = dict(chat_id=chat_id, message_id=msg_id, text=text,
                parse_mode=parse_mode, disable_web_page_preview=True)
    if reply_markup:
        data["reply_markup"] = reply_markup
    return tg("editMessageText", **data)

def inline_kb(*rows):
    return {"inline_keyboard": [[{"text":t,"url":u} for t,u in row] for row in rows]}

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
    if p == 0: return "$0"
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

def score_bar(v, w=10):
    f = round(v/100*w)
    return "█"*f + "░"*(w-f)

def risk_bar(v, w=8):
    f = round(v/100*w)
    return "▓"*f + "░"*(w-f)

# ── ASYNC DATA FETCHERS ───────────────────────────────────────────────
async def rpc(session, method, params):
    try:
        async with session.post(HELIUS_RPC,
            json={"jsonrpc":"2.0","id":1,"method":method,"params":params},
            headers={"Content-Type":"application/json"},
            timeout=aiohttp.ClientTimeout(total=10)) as r:
            return (await r.json()).get("result")
    except:
        return None

async def fetch_dex(session, mint):
    try:
        async with session.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{mint}",
            timeout=aiohttp.ClientTimeout(total=10)) as r:
            j = await r.json()
            pairs = j.get("pairs") or []
            if not pairs: return None
            return sorted(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd",0) or 0), reverse=True)[0]
    except:
        return None

async def fetch_rugcheck(session, mint):
    try:
        async with session.get(
            f"https://api.rugcheck.xyz/v1/tokens/{mint}/report/summary",
            timeout=aiohttp.ClientTimeout(total=8)) as r:
            if r.status == 200:
                return await r.json()
    except:
        pass
    return None

async def fetch_all(mint):
    async with aiohttp.ClientSession() as s:
        asset, mint_info_raw, holders_raw, dex, rugcheck = await asyncio.gather(
            rpc(s,"getAsset",{"id":mint,"displayOptions":{"showFungible":True}}),
            rpc(s,"getAccountInfo",[mint,{"encoding":"jsonParsed"}]),
            rpc(s,"getTokenLargestAccounts",[mint]),
            fetch_dex(s, mint),
            fetch_rugcheck(s, mint),
        )

    mint_info = {}
    if mint_info_raw:
        mint_info = ((mint_info_raw.get("value") or {}).get("data") or {}).get("parsed",{}).get("info",{})
    holders = (holders_raw or {}).get("value") or []

    meta   = (asset or {}).get("content",{}).get("metadata",{})
    ti     = (asset or {}).get("token_info",{}) or {}
    name   = meta.get("name") or ti.get("symbol","Unknown Token")
    symbol = ti.get("symbol","???")

    decimals   = int(mint_info.get("decimals",6))
    supply_raw = int(mint_info.get("supply",0))
    supply     = supply_raw/10**decimals if supply_raw else None
    top_pct    = int(holders[0]["amount"])/supply_raw*100 if holders and supply_raw else 0
    top10_pct  = sum(int(h["amount"]) for h in holders[:10])/supply_raw*100 if holders and supply_raw else 0
    lp_burned  = any(h.get("address","") in BURN_ADDRS or h.get("address","").startswith("11111") for h in holders)

    def _f(d, k, sub=None):
        v = d.get(k) if not sub else (d.get(k) or {}).get(sub)
        try: return float(v) if v not in (None,"","0") else None
        except: return None

    dx = dex or {}
    socials  = (dx.get("info") or {}).get("socials") or []
    websites = (dx.get("info") or {}).get("websites") or []

    return {
        "name":name,"symbol":symbol,
        "mintAuthority":mint_info.get("mintAuthority"),
        "freezeAuthority":mint_info.get("freezeAuthority"),
        "supply":supply,"holderCount":len(holders),
        "topHolderPct":top_pct,"top10Pct":top10_pct,"lpBurned":lp_burned,
        "price":_f(dx,"priceUsd"),"marketCap":_f(dx,"fdv"),
        "liquidity":_f(dx,"liquidity","usd"),"volume24h":_f(dx,"volume","h24"),
        "change24h":_f(dx,"priceChange","h24"),
        "buys24h":(dx.get("txns",{}).get("h24",{}) or {}).get("buys"),
        "sells24h":(dx.get("txns",{}).get("h24",{}) or {}).get("sells"),
        "dexUrl":dx.get("url"),
        "hasTwitter":any(s.get("type","").lower() in("twitter","x") for s in socials),
        "hasTelegram":any(s.get("type","").lower()=="telegram" for s in socials),
        "hasWebsite":len(websites)>0,
        "rugScore":(rugcheck or {}).get("score"),
    }

# ── SCORE ENGINE ──────────────────────────────────────────────────────
def calc_score(d):
    flags,goods = [],[]
    safety = 100

    if d.get("mintAuthority"):
        safety -= 30; flags.append("⚠️ Mint authority NOT revoked — dev can print tokens")
    else: goods.append("✅ Mint authority revoked")

    if d.get("freezeAuthority"):
        safety -= 20; flags.append("⚠️ Freeze authority active — wallets can be frozen")
    else: goods.append("✅ Freeze authority revoked")

    if d.get("lpBurned"):   goods.append("🔥 Liquidity BURNED — rug pull impossible")
    else: safety -= 35;     flags.append("🚨 Liquidity NOT secured — HIGH rug risk")

    rug = d.get("rugScore")
    if rug and rug >= 700:  safety -= 20; flags.append(f"🚨 RugCheck: {rug}/1000 — DANGEROUS")
    elif rug and rug >= 400: safety -= 10; flags.append(f"⚠️ RugCheck: {rug}/1000 — elevated")
    safety = max(0, min(100, safety))

    whale = 0
    top1 = d.get("topHolderPct",0)
    top10 = d.get("top10Pct",0)
    if top1>50:   whale+=60; flags.append(f"🚨 Top wallet owns {top1:.1f}% — extreme concentration")
    elif top1>25: whale+=35; flags.append(f"⚠️ Top wallet owns {top1:.1f}% — high whale risk")
    elif top1>10: whale+=15; flags.append(f"⚠️ Top wallet owns {top1:.1f}% — moderate risk")
    else: goods.append(f"✅ Top wallet owns {top1:.1f}% — healthy distribution")
    if top10>70:  whale+=30; flags.append(f"🚨 Top 10 hold {top10:.1f}% — severe concentration")
    elif top10>40: whale+=15
    else: goods.append(f"✅ Top 10 hold {top10:.1f}% — distributed")
    whale = min(100, whale)

    community = 30
    h = d.get("holderCount",0)
    if h>=2000:   community+=40; goods.append(f"✅ {h:,} holders — strong community")
    elif h>=500:  community+=25; goods.append(f"✅ {h:,} holders — growing")
    elif h>=100:  community+=10
    else:         community-=10; flags.append(f"⚠️ Only {h} holders — very early")
    if d.get("hasTwitter"):  community+=12; goods.append("✅ X/Twitter confirmed")
    if d.get("hasTelegram"): community+=10; goods.append("✅ Telegram community exists")
    if d.get("hasWebsite"):  community+=8;  goods.append("✅ Website linked")
    if not any([d.get("hasTwitter"),d.get("hasTelegram"),d.get("hasWebsite")]):
        flags.append("⚠️ No social presence detected")
    community = max(0, min(100, community))

    heat = 20
    chg = d.get("change24h")
    if chg:
        if chg>200: heat+=40
        elif chg>50: heat+=25
        elif chg>10: heat+=12
        elif chg<-50: heat-=15
    vol = d.get("volume24h") or 0
    if vol>500000: heat+=25
    elif vol>100000: heat+=15
    elif vol>10000: heat+=8
    buys  = d.get("buys24h") or 0
    sells = d.get("sells24h") or 0
    if buys+sells>500: heat+=20
    elif buys+sells>100: heat+=10
    if buys+sells>0 and buys>sells*1.5:
        heat+=10; goods.append(f"📈 Buy pressure: {buys} buys vs {sells} sells")
    heat = max(0, min(100, heat))

    scam = 0
    if d.get("mintAuthority"):   scam+=25
    if d.get("freezeAuthority"): scam+=20
    if not d.get("lpBurned"):    scam+=30
    if top1>30:                   scam+=15
    scam = min(100, scam)

    solar = round(safety*0.35 + (100-whale)*0.25 + community*0.20 + heat*0.10 + (100-scam)*0.10)
    solar = max(0, min(100, solar))

    if   solar>=80: grade,verdict,gem = "A","STRONG SIGNAL","🟢"
    elif solar>=65: grade,verdict,gem = "B","MODERATE SIGNAL","🟡"
    elif solar>=45: grade,verdict,gem = "C","WEAK SIGNAL","🟠"
    else:           grade,verdict,gem = "D","DANGER — AVOID","🔴"

    # AI Summary
    summary_parts = []
    if solar>=80:   summary_parts.append(f"Solar Signal detects strong structural integrity for ${d['symbol']}.")
    elif solar>=65: summary_parts.append(f"Solar Signal identifies moderate opportunity with manageable risk for ${d['symbol']}.")
    elif solar>=45: summary_parts.append(f"Solar Signal flags elevated risk for ${d['symbol']}. Proceed with strict caution.")
    else:           summary_parts.append(f"Solar Signal issues a HIGH RISK alert for ${d['symbol']}. Multiple critical red flags.")
    if safety>=80:  summary_parts.append("Contract architecture appears clean.")
    elif safety>=50: summary_parts.append("Partial safety — liquidity exposure remains a concern.")
    else:           summary_parts.append("Structural safety is critically compromised.")
    if whale<=20:   summary_parts.append("Whale concentration is minimal.")
    elif whale<=50: summary_parts.append(f"Moderate whale presence — top wallet at {top1:.1f}%. Monitor for dumps.")
    else:           summary_parts.append(f"Severe whale concentration at {top1:.1f}%. Exit risk is elevated.")
    ai_summary = " ".join(summary_parts)

    return {
        "solar":solar,"safety":round(safety),"whale":round(whale),
        "community":round(community),"heat":round(heat),"scam":round(scam),
        "grade":grade,"verdict":verdict,"gem":gem,
        "flags":flags,"goods":goods,"ai":ai_summary
    }

# ── REPORT BUILDER ────────────────────────────────────────────────────
def build_report(mint, d, s):
    buys  = d.get("buys24h") or 0
    sells = d.get("sells24h") or 0
    total = buys+sells
    if total>0:
        bp   = buys/total*100
        blen = round(bp/100*10)
        bs   = f"`{'🟢'*blen}{'🔴'*(10-blen)}` {bp:.0f}% buy\n         {buys} buys / {sells} sells"
        bs_line = f"\n🔀 Pressure:  {bs}"
    else: bs_line = ""

    socials = []
    if d.get("hasTwitter"):  socials.append("𝕏")
    if d.get("hasTelegram"): socials.append("TG")
    if d.get("hasWebsite"):  socials.append("WEB")

    chg = d.get("change24h")
    chg_str = ""
    if chg is not None:
        arrow = "📈" if chg>=0 else "📉"
        sign  = "+" if chg>=0 else ""
        chg_str = f" {arrow} {sign}{chg:.1f}%"

    flags_txt = "\n".join(s["flags"][:4]) or "No critical flags"
    goods_txt = "\n".join(s["goods"][:3]) or ""

    return (
f"""☀️ *SOLAR SIGNAL REPORT — ${d['symbol']}*
━━━━━━━━━━━━━━━━━━━━━━━━
🪙 *{d['name']}*
📋 `{mint[:5]}…{mint[-5:]}`

{s['gem']} *Solar Signal Score: {s['solar']}/100 — {s['verdict']}*
`{score_bar(s['solar'],14)}`

━━━━━━━━━━━━━━━━━━━━━━━━
📊 *SUB-SCORES*
🛡 Safety:     `{score_bar(s['safety'])}` {s['safety']}/100
🐋 Whale Risk: `{risk_bar(s['whale'])}` {s['whale']}/100
👥 Community:  `{score_bar(s['community'])}` {s['community']}/100
🔥 Narrative:  `{score_bar(s['heat'])}` {s['heat']}/100
☠️ Scam Risk:   `{risk_bar(s['scam'])}` {s['scam']}/100

━━━━━━━━━━━━━━━━━━━━━━━━
💰 *MARKET DATA*
💲 Price:      `{fmt_price(d.get('price'))}`{chg_str}
📦 Market Cap: `{fmt_usd(d.get('marketCap'))}`
💧 Liquidity:  `{fmt_usd(d.get('liquidity'))}`
📊 Volume 24h: `{fmt_usd(d.get('volume24h'))}`
🪙 Supply:     `{fmt_num(d.get('supply'))}`
👥 Holders:    `{fmt_num(d.get('holderCount'))}`
🐳 Top Wallet: `{d.get('topHolderPct',0):.1f}%`
📊 Top 10:     `{d.get('top10Pct',0):.1f}%`
🔥 LP Burned:  `{'YES ✅' if d.get('lpBurned') else 'NO 🚨'}`
🌐 Social:     `{' '.join(socials) or 'None'}`{bs_line}

━━━━━━━━━━━━━━━━━━━━━━━━
⚡ *KEY FINDINGS*
{flags_txt}
{goods_txt}
━━━━━━━━━━━━━━━━━━━━━━━━
🧠 *AI SIGNAL*
_{s['ai']}_

━━━━━━━━━━━━━━━━━━━━━━━━
⊙ *Solar Signal Bot* by $FLASH"""
    )

# ── HANDLERS ──────────────────────────────────────────────────────────
def handle_start(chat_id):
    kb = inline_kb(
        [("🌐 Web Scanner", REPORT_URL)],
        [("⚡ Join $FLASH", TG_CHANNEL)]
    )
    send(chat_id,
        "☀️ *SOLAR SIGNAL BOT*\n"
        "_by Solar Flash — Elite Solana Intelligence_\n\n"
        "Paste any Solana token address for a full risk report.\n\n"
        "/analyze `<address>` — Full report\n"
        "/score `<address>` — Quick score\n"
        "/help — How to use\n"
        "/about — About $FLASH",
        reply_markup=kb
    )

def handle_help(chat_id):
    send(chat_id,
        "☀️ *HOW TO USE*\n\n"
        "Just paste a Solana token address:\n"
        "`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`\n\n"
        "Or use commands:\n"
        "/analyze `<address>` — Full intelligence report\n"
        "/score `<address>` — Quick score card\n\n"
        "_Accuracy > Hype. Signal > Speculation._ ⊙"
    )

def handle_about(chat_id):
    send(chat_id,
        "⊙ *SOLAR SIGNAL BOT — by Solar Flash*\n\n"
        "_Built to detect signal before noise._\n\n"
        "📡 Data: Helius · DexScreener · RugCheck\n"
        f"🌐 {REPORT_URL}\n"
        f"⚡ {TG_CHANNEL}"
    )

def do_scan(chat_id, mint, full=True):
    if not SOL_RE.fullmatch(mint):
        send(chat_id, "❌ *Invalid address.* Please paste a valid Solana token contract.")
        return

    uid = chat_id
    now = time.time()
    if now - _rate.get(uid,0) < 8:
        send(chat_id, "⏳ Please wait a few seconds before scanning again.")
        return
    _rate[uid] = now

    scanning = send(chat_id,
        "☀️ *Solar Signal scanning...*\n\n"
        "⛓ Fetching on-chain data\n"
        "📊 Pulling market intelligence\n"
        "🧠 Running risk analysis\n"
        "⊙ Generating AI signal"
    )
    msg_id = (scanning.get("result") or {}).get("message_id")

    async def _run():
        try:
            d = await asyncio.wait_for(fetch_all(mint), timeout=25)
            s = calc_score(d)
            if full:
                text = build_report(mint, d, s)
            else:
                text = (
                    f"☀️ *QUICK SCORE — ${d['symbol']}*\n\n"
                    f"{s['gem']} *{s['solar']}/100 — {s['verdict']}*\n\n"
                    f"🛡 Safety: {s['safety']}/100\n"
                    f"🐋 Whale:  {s['whale']}/100\n"
                    f"👥 Comm:   {s['community']}/100\n"
                    f"🔥 Heat:   {s['heat']}/100\n\n"
                    f"_{s['ai'][:200]}..._"
                )
            kb_rows = []
            if d.get("dexUrl"):
                kb_rows.append([("📈 DexScreener", d["dexUrl"])])
            kb_rows.append([("🌐 Scanner", REPORT_URL), ("⚡ $FLASH", TG_CHANNEL)])
            kb = inline_kb(*kb_rows)
            if msg_id:
                edit(chat_id, msg_id, text, reply_markup=kb)
            else:
                send(chat_id, text, reply_markup=kb)
        except asyncio.TimeoutError:
            txt = "⏱ *Analysis timed out.* Please try again."
            if msg_id: edit(chat_id, msg_id, txt)
            else: send(chat_id, txt)
        except Exception as e:
            log.error(f"Scan error: {e}")
            txt = "❌ *Could not analyze this token.*\n\nCheck the address and try again."
            if msg_id: edit(chat_id, msg_id, txt)
            else: send(chat_id, txt)

    asyncio.run(_run())

def handle_update(update):
    msg = update.get("message") or update.get("edited_message")
    if not msg: return
    chat_id = msg["chat"]["id"]
    text    = msg.get("text","").strip()
    if not text: return

    if text.startswith("/start"):   return handle_start(chat_id)
    if text.startswith("/help"):    return handle_help(chat_id)
    if text.startswith("/about"):   return handle_about(chat_id)
    if text.startswith("/analyze"):
        parts = text.split()
        if len(parts)<2: return send(chat_id,"⚠️ Usage: `/analyze <address>`")
        return threading.Thread(target=do_scan, args=(chat_id, parts[1], True)).start()
    if text.startswith("/score"):
        parts = text.split()
        if len(parts)<2: return send(chat_id,"⚠️ Usage: `/score <address>`")
        return threading.Thread(target=do_scan, args=(chat_id, parts[1], False)).start()

    m = SOL_RE.search(text)
    if m:
        return threading.Thread(target=do_scan, args=(chat_id, m.group(), True)).start()

    send(chat_id,
        "⊙ Paste a Solana token address to scan.\n\n"
        "Example:\n`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263` _(BONK)_"
    )

# ── POLLING LOOP ──────────────────────────────────────────────────────
def main():
    log.info("⊙ Solar Signal Bot is live...")
    offset = 0
    while True:
        try:
            r = req.get(f"{TG_API}/getUpdates",
                        params={"offset":offset,"timeout":30},
                        timeout=35)
            updates = r.json().get("result",[])
            for u in updates:
                offset = u["update_id"] + 1
                threading.Thread(target=handle_update, args=(u,)).start()
        except Exception as e:
            log.error(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
