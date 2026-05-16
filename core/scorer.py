"""
⊙ SOLAR SIGNAL SCORE ENGINE
Full composite scoring with all sub-scores.
"""
from core.risk_engine import analyze_honeypot_proxies, analyze_whale_intelligence

def score(data: dict) -> dict:
    honey  = analyze_honeypot_proxies(data)
    whale  = analyze_whale_intelligence(data)

    flags = []
    goods = []

    # ── 1. SAFETY SCORE (0-100) ────────────────────────────────────
    safety = 100

    if data.get("hasMintRisk"):
        safety -= 30
        flags.append("⚠️ Mint authority NOT revoked — unlimited supply risk")
    else:
        goods.append("✅ Mint authority revoked — supply is fixed")

    if data.get("hasFreezeRisk"):
        safety -= 20
        flags.append("⚠️ Freeze authority active — sell may be blocked")
    else:
        goods.append("✅ Freeze authority revoked")

    if data.get("lpBurned"):
        goods.append("🔥 Liquidity BURNED — rug pull impossible")
    else:
        safety -= 35
        flags.append("🚨 Liquidity NOT secured — rug pull risk is OPEN")

    rug = data.get("rugScore")
    if rug is not None:
        if rug >= 700:
            safety -= 20
            flags.append(f"🚨 RugCheck: {rug}/1000 — DANGEROUS contract")
        elif rug >= 400:
            safety -= 10
            flags.append(f"⚠️ RugCheck: {rug}/1000 — elevated risk")
        else:
            goods.append(f"✅ RugCheck: {rug}/1000 — acceptable")

    safety = max(0, min(100, safety))

    # ── 2. WHALE RISK (0-100, higher = worse) ─────────────────────
    whale_risk = whale["whale_risk"]
    for f in whale["flags"]:
        if any(x in f for x in ["🚨", "⚠️", "📉"]):
            flags.append(f)
        else:
            goods.append(f)

    # ── 3. COMMUNITY STRENGTH (0-100) ─────────────────────────────
    community = 20
    h = data.get("holderCount", 0)
    if h >= 5000:   community += 50; goods.append(f"✅ {h:,} holders — massive community")
    elif h >= 2000: community += 40; goods.append(f"✅ {h:,} holders — strong community")
    elif h >= 500:  community += 25; goods.append(f"✅ {h:,} holders — growing")
    elif h >= 100:  community += 10
    else:           community -= 10; flags.append(f"⚠️ Only {h} holders — very early stage")

    if data.get("hasTwitter"):  community += 10; goods.append("✅ X/Twitter confirmed")
    if data.get("hasTelegram"): community += 12; goods.append("✅ Telegram community active")
    if data.get("hasWebsite"):  community += 8;  goods.append("✅ Website present")

    unique_w = data.get("uniqueWallets24h")
    if unique_w and unique_w > 200: community += 10; goods.append(f"✅ {unique_w:,} unique wallets today")

    community = max(0, min(100, community))

    # ── 4. NARRATIVE HEAT (0-100) ──────────────────────────────────
    heat = data.get("narrativeHeat", 20)

    # ── 5. SCAM RISK (0-100) ──────────────────────────────────────
    scam = honey["honeypot_score"]

    # Add organic/artificial signals
    organic = data.get("organicScore", 50)
    if organic < 30:
        scam += 15
        flags.append("⚠️ Hype pattern appears artificial — bot activity suspected")
    elif organic > 70:
        goods.append("✅ Growth pattern appears organic")

    scam = min(100, scam)

    # ── 6. MEME & CULT SCORES ─────────────────────────────────────
    meme_score = data.get("memeScore", 0)
    cult_score = data.get("cultScore", 0)

    # ── 7. SOLAR SIGNAL SCORE (composite) ─────────────────────────
    solar = round(
        safety       * 0.30 +
        (100-whale_risk) * 0.25 +
        community    * 0.20 +
        heat         * 0.12 +
        (100-scam)   * 0.08 +
        organic      * 0.05
    )
    solar = max(0, min(100, solar))

    if   solar >= 80: grade, verdict, gem = "A", "STRONG SIGNAL",   "🟢"
    elif solar >= 65: grade, verdict, gem = "B", "MODERATE SIGNAL", "🟡"
    elif solar >= 45: grade, verdict, gem = "C", "WEAK SIGNAL",     "🟠"
    else:             grade, verdict, gem = "D", "DANGER — AVOID",  "🔴"

    return {
        "solar_score":    solar,
        "safety_score":   round(safety),
        "whale_risk":     round(whale_risk),
        "whale_threat":   whale["threat"],
        "community":      round(community),
        "narrative_heat": round(heat),
        "scam_risk":      round(scam),
        "meme_score":     round(meme_score),
        "cult_score":     round(cult_score),
        "organic_score":  round(organic),
        "honeypot":       honey,
        "grade":          grade,
        "verdict":        verdict,
        "gem":            gem,
        "flags":          flags,
        "goods":          goods,
    }
