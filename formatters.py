"""
Premium Telegram message formatter.
Dark intelligence aesthetic — Bloomberg Terminal meets crypto.
"""
from config import REPORT_URL, TG_CHANNEL
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# ── NUMBER FORMATTERS ────────────────────────────────────────────────
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
    import re
    s = f"{p:.30f}"
    m = re.match(r"^0\.(0*)(\d{1,8})", s)
    if not m: return f"${p:.12f}"
    zeros = len(m.group(1))
    sig   = m.group(2).rstrip("0")[:6]
    SUB   = str.maketrans("0123456789","₀₁₂₃₄₅₆₇₈₉")
    if zeros < 4: return f"$0.{'0'*zeros}{sig}"
    return f"$0.0{str(zeros).translate(SUB)}{sig}"

def fmt_pct(n, always_sign=True):
    if n is None: return "—"
    sign = "+" if n >= 0 and always_sign else ""
    return f"{sign}{n:.1f}%"

def short(a):
    if not a: return "—"
    return f"{a[:5]}…{a[-5:]}"

def score_bar(val, width=10):
    """ASCII progress bar."""
    filled = round(val / 100 * width)
    return "█" * filled + "░" * (width - filled)

def risk_bar(val, width=8):
    """Inverted bar — high value = more danger."""
    filled = round(val / 100 * width)
    return "▓" * filled + "░" * (width - filled)

def chg_arrow(chg):
    if chg is None: return ""
    if chg >= 0: return f"📈 +{chg:.1f}%"
    return f"📉 {chg:.1f}%"

# ── FULL REPORT ──────────────────────────────────────────────────────
def build_full_report(data: dict, scores: dict) -> str:
    d = data
    s = scores

    # Buy/sell bar
    buys  = d.get("buys24h") or 0
    sells = d.get("sells24h") or 0
    total = buys + sells
    if total > 0:
        buy_pct  = buys  / total * 100
        sell_pct = sells / total * 100
        blen     = round(buy_pct  / 100 * 10)
        slen     = 10 - blen
        bs_bar   = f"`{'🟢'*blen}{'🔴'*slen}` {buy_pct:.0f}% buy"
        bs_line  = f"\n🔀 Pressure:  {bs_bar}\n         {buys} buys  /  {sells} sells"
    else:
        bs_line = ""

    # Social presence
    socials = []
    if d.get("hasTwitter"):  socials.append("𝕏")
    if d.get("hasTelegram"): socials.append("TG")
    if d.get("hasWebsite"):  socials.append("WEB")
    social_str = "  ".join(socials) if socials else "None detected"

    # Flags (top 4 only to keep message clean)
    flag_lines = ""
    for icon, text, *_ in s["flags"][:4]:
        flag_lines += f"{icon} {text}\n"
    if not flag_lines: flag_lines = "No critical flags detected\n"

    # Goods (top 3)
    good_lines = ""
    for icon, text in s["goods"][:3]:
        good_lines += f"{icon} {text}\n"

    # Score bars
    safety_bar = score_bar(s["safety_score"])
    whale_bar  = risk_bar(s["whale_risk"])
    comm_bar   = score_bar(s["community_strength"])
    heat_bar   = score_bar(s["narrative_heat"])
    scam_bar   = risk_bar(s["scam_risk"])

    report = (
f"""☀️ *SOLAR SIGNAL REPORT — ${d['symbol']}*
━━━━━━━━━━━━━━━━━━━━━━━━
🪙 *{d['name']}*
📋 `{short(d['mint'])}`

{s['grade_emoji']} *Solar Signal Score: {s['solar_score']}/100* — *{s['verdict']}*
`{score_bar(s['solar_score'], 14)}`

━━━━━━━━━━━━━━━━━━━━━━━━
📊 *SUB-SCORES*

🛡 Safety:      `{safety_bar}` {s['safety_score']}/100
🐋 Whale Risk:  `{whale_bar}` {s['whale_risk']}/100
👥 Community:  `{comm_bar}` {s['community_strength']}/100
🔥 Narrative:  `{heat_bar}` {s['narrative_heat']}/100
☠️ Scam Risk:   `{scam_bar}` {s['scam_risk']}/100

━━━━━━━━━━━━━━━━━━━━━━━━
💰 *MARKET DATA*

💲 Price:       `{fmt_price(d['price'])}` {chg_arrow(d.get('change24h'))}
📦 Market Cap:  `{fmt_usd(d['marketCap'])}`
💧 Liquidity:   `{fmt_usd(d['liquidity'])}`
📊 Volume 24h:  `{fmt_usd(d['volume24h'])}`
🪙 Supply:      `{fmt_num(d['supply'])}`
👥 Holders:     `{fmt_num(d['holderCount'])}`
🐳 Top Wallet:  `{d['topHolderPct']:.1f}%`
📊 Top 10:      `{d['top10Pct']:.1f}%`
🔥 LP Burned:   `{'YES ✅' if d['lpBurned'] else 'NO 🚨'}`
🌐 Social:      `{social_str}`{bs_line}

━━━━━━━━━━━━━━━━━━━━━━━━
⚡ *KEY FINDINGS*

{flag_lines}{good_lines}
━━━━━━━━━━━━━━━━━━━━━━━━
🧠 *AI SIGNAL*

_{s['ai_summary']}_

━━━━━━━━━━━━━━━━━━━━━━━━
⊙ *Solar Signal Bot* by $FLASH
_{REPORT_URL}_"""
    )
    return report

# ── SCORE ONLY (quick) ───────────────────────────────────────────────
def build_score_card(data: dict, scores: dict) -> str:
    d, s = data, scores
    return (
f"""☀️ *QUICK SCORE — ${d['symbol']}*

{s['grade_emoji']} *{s['solar_score']}/100 — {s['verdict']}*

🛡 Safety:     {s['safety_score']}/100
🐋 Whale Risk: {s['whale_risk']}/100
👥 Community:  {s['community_strength']}/100
🔥 Narrative:  {s['narrative_heat']}/100

_{s['ai_summary'][:180]}..._

⊙ Use /analyze for full report"""
    )

# ── KEYBOARD BUILDERS ────────────────────────────────────────────────
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Web Scanner", url=REPORT_URL)],
        [InlineKeyboardButton("⚡ Join $FLASH", url=TG_CHANNEL)],
    ])

def report_keyboard(dex_url=None):
    rows = []
    if dex_url:
        rows.append([InlineKeyboardButton("📈 DexScreener", url=dex_url)])
    rows.append([
        InlineKeyboardButton("🌐 Full Scanner", url=REPORT_URL),
        InlineKeyboardButton("⚡ $FLASH",       url=TG_CHANNEL),
    ])
    return InlineKeyboardMarkup(rows)
