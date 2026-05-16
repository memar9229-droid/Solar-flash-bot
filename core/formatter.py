"""
Premium output formatter — Bloomberg Terminal meets crypto intelligence.
"""
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import REPORT_URL, TG_CHANNEL
from core.ai_summary import generate

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
    SUB   = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    if zeros < 4: return f"$0.{'0'*zeros}{sig}"
    return f"$0.0{str(zeros).translate(SUB)}{sig}"

def fmt_pct(n):
    if n is None: return "—"
    sign = "+" if n >= 0 else ""
    return f"{sign}{n:.1f}%"

def bar(v, w=10, char="█", empty="░"):
    f = round(max(0, min(100, v)) / 100 * w)
    return char * f + empty * (w - f)

def rbar(v, w=8):
    return bar(v, w, "▓", "░")

def short(a):
    return f"{a[:5]}…{a[-5:]}" if a else "—"

def build_full_report(data: dict, scores: dict) -> str:
    d, s = data, scores
    ai = generate(data, scores)

    # Buy/sell bar
    buys   = d.get("buys24h")  or 0
    sells  = d.get("sells24h") or 0
    total  = buys + sells
    if total > 0:
        bp     = buys / total * 100
        blen   = round(bp / 100 * 10)
        bs_row = (
            f"\n🔀 B/S Ratio:  `{'🟢'*blen}{'🔴'*(10-blen)}` {bp:.0f}% buy"
            f"\n              {buys} buys  /  {sells} sells"
        )
    else:
        bs_row = ""

    # Social
    soc = []
    if d.get("hasTwitter"):  soc.append("𝕏 Twitter")
    if d.get("hasTelegram"): soc.append("TG")
    if d.get("hasWebsite"):  soc.append("🌐 Web")

    # Change arrows
    chg24 = d.get("change24h")
    chg_str = ""
    if chg24 is not None:
        arrow = "📈" if chg24 >= 0 else "📉"
        chg_str = f" {arrow} {fmt_pct(chg24)}"

    # Flags & goods (top items only)
    flag_lines = "\n".join(s["flags"][:5]) if s["flags"] else "No critical flags detected"
    good_lines = "\n".join(s["goods"][:4]) if s["goods"] else ""

    # Honeypot summary
    honey  = s.get("honeypot", {})
    sell_s = honey.get("sellability", "UNKNOWN")
    sell_e = {"LIKELY_OK": "✅", "CAUTION": "⚠️", "RESTRICTED": "🚨"}.get(sell_s, "❓")

    # Dev wallet
    dev_line = ""
    if d.get("devWallet"):
        dev_line = f"\n👨‍💻 Dev Wallet:  `{short(d['devWallet'])}` ({d['devPct']:.1f}%)"

    # Unique wallets
    uw_line = ""
    if d.get("uniqueWallets24h"):
        uw_line = f"\n👛 Unique Wallets 24h: `{fmt_num(d['uniqueWallets24h'])}`"

    return (
f"""☀️ *SOLAR SIGNAL REPORT*
${d['symbol']} — {d['name']}
━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 `{short(d['mint'])}`
🕐 Pair Age: `{d.get('pairAge') or '—'}`
🌐 Social: `{' · '.join(soc) or 'None detected'}`

{s['gem']} *Solar Signal Score: {s['solar_score']}/100*
`{bar(s['solar_score'], 14)}` — *{s['verdict']}*

━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 *SUB-SCORES*
🛡 Safety:        `{bar(s['safety_score'])}` {s['safety_score']}/100
🐋 Whale Risk:    `{rbar(s['whale_risk'])}` {s['whale_risk']}/100 [{s['whale_threat']}]
👥 Community:    `{bar(s['community'])}` {s['community']}/100
🔥 Narrative:    `{bar(s['narrative_heat'])}` {s['narrative_heat']}/100
☠️ Scam Risk:     `{rbar(s['scam_risk'])}` {s['scam_risk']}/100
🎭 Meme Strength: `{bar(s['meme_score'])}` {s['meme_score']}/100
⛪ Cult Potential:`{bar(s['cult_score'])}` {s['cult_score']}/100
🔍 Organic Score: `{bar(s['organic_score'])}` {s['organic_score']}/100

━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *MARKET DATA*
💲 Price:      `{fmt_price(d.get('price'))}`{chg_str}
📦 Mkt Cap:    `{fmt_usd(d.get('marketCap'))}`
💧 Liquidity:  `{fmt_usd(d.get('liquidity'))}`
📊 Vol 24h:    `{fmt_usd(d.get('volume24h'))}`
📊 Vol 6h:     `{fmt_usd(d.get('volume6h'))}`
🪙 Supply:     `{fmt_num(d.get('supply'))}`
👥 Holders:    `{fmt_num(d.get('holderCount'))}`{uw_line}

━━━━━━━━━━━━━━━━━━━━━━━━━━
🐋 *WHALE INTELLIGENCE*
🥇 Top Wallet:  `{d.get('topHolderPct',0):.1f}%`
🏆 Top 5:       `{d.get('top5Pct',0):.1f}%`
📊 Top 10:      `{d.get('top10Pct',0):.1f}%`{dev_line}
🔥 LP Burned:   `{'YES ✅' if d.get('lpBurned') else 'NO 🚨'}`{bs_row}

━━━━━━━━━━━━━━━━━━━━━━━━━━
🔒 *SELL RISK ANALYSIS*
Sellability:    {sell_e} `{sell_s}`
Mint Authority: `{'ACTIVE ⚠️' if d.get('hasMintRisk') else 'REVOKED ✅'}`
Freeze Auth:    `{'ACTIVE ⚠️' if d.get('hasFreezeRisk') else 'REVOKED ✅'}`

━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ *KEY FINDINGS*
{flag_lines}
{good_lines}
━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 *AI SIGNAL*
_{ai}_

━━━━━━━━━━━━━━━━━━━━━━━━━━
⊙ *Solar Signal Bot* by $FLASH
_Not financial advice. DYOR._"""
    )

def build_score_card(data: dict, scores: dict) -> str:
    d, s = data, scores
    ai = generate(data, scores)
    return (
f"""☀️ *QUICK SCORE — ${d['symbol']}*

{s['gem']} *{s['solar_score']}/100 — {s['verdict']}*
`{bar(s['solar_score'], 12)}`

🛡 Safety:     {s['safety_score']}/100
🐋 Whale Risk: {s['whale_risk']}/100
👥 Community:  {s['community']}/100
🔥 Narrative:  {s['narrative_heat']}/100
🎭 Meme:       {s['meme_score']}/100
☠️ Scam Risk:   {s['scam_risk']}/100

🔒 Sellability: `{s['honeypot'].get('sellability','—')}`
🔥 LP Burned:   `{'YES ✅' if data.get('lpBurned') else 'NO 🚨'}`

🧠 _{ai[:220]}..._

⊙ Use /analyze for full intelligence report"""
    )

def report_keyboard(dex_url=None):
    rows = []
    if dex_url:
        rows.append([InlineKeyboardButton("📈 DexScreener", url=dex_url)])
    rows.append([
        InlineKeyboardButton("🌐 Web Scanner", url=REPORT_URL),
        InlineKeyboardButton("⚡ $FLASH",       url=TG_CHANNEL),
    ])
    return InlineKeyboardMarkup(rows)

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Web Scanner", url=REPORT_URL)],
        [InlineKeyboardButton("⚡ Join $FLASH", url=TG_CHANNEL)],
    ])
