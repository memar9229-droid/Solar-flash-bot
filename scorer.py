"""
⊙ SOLAR SIGNAL SCORE ENGINE
Produces the branded score + sub-scores + AI narrative summary.
"""

def score(data: dict) -> dict:
    """
    Returns full scoring dict including:
    - solar_score (0-100)
    - safety_score
    - narrative_heat
    - whale_risk
    - community_strength
    - scam_risk
    - grade (A/B/C/D)
    - verdict
    - flags (list)
    - goods (list)
    - ai_summary (string)
    """
    flags = []
    goods = []

    # ════════════════════════════════════════════
    # 1. SAFETY SCORE (0-100, higher = safer)
    # ════════════════════════════════════════════
    safety = 100

    if data.get("mintAuthority"):
        safety -= 30
        flags.append(("⚠️", "Mint authority NOT revoked — dev can print tokens", "high"))
    else:
        goods.append(("✅", "Mint authority revoked — supply is fixed"))

    if data.get("freezeAuthority"):
        safety -= 20
        flags.append(("⚠️", "Freeze authority active — wallets can be frozen", "high"))
    else:
        goods.append(("✅", "Freeze authority revoked"))

    if data.get("lpBurned"):
        goods.append(("🔥", "Liquidity burned — rug pull impossible"))
    else:
        safety -= 35
        flags.append(("🚨", "Liquidity NOT secured — HIGH rug pull risk", "critical"))

    rug = data.get("rugScore")
    if rug is not None:
        if rug >= 700:
            safety -= 20
            flags.append(("🚨", f"RugCheck risk score: {rug}/1000 — DANGEROUS", "critical"))
        elif rug >= 400:
            safety -= 10
            flags.append(("⚠️", f"RugCheck risk score: {rug}/1000 — elevated risk", "medium"))
        else:
            goods.append(("✅", f"RugCheck score: {rug}/1000 — acceptable"))

    safety = max(0, min(100, safety))

    # ════════════════════════════════════════════
    # 2. WHALE RISK (0-100, higher = more risky)
    # ════════════════════════════════════════════
    whale_risk = 0
    top1 = data.get("topHolderPct", 0)
    top10 = data.get("top10Pct", 0)

    if top1 > 50:
        whale_risk += 60
        flags.append(("🚨", f"Top wallet owns {top1:.1f}% — extreme concentration", "critical"))
    elif top1 > 25:
        whale_risk += 35
        flags.append(("⚠️", f"Top wallet owns {top1:.1f}% — high whale risk", "high"))
    elif top1 > 10:
        whale_risk += 15
        flags.append(("⚠️", f"Top wallet owns {top1:.1f}% — moderate risk", "medium"))
    else:
        goods.append(("✅", f"Top wallet owns {top1:.1f}% — healthy distribution"))

    if top10 > 70:
        whale_risk += 30
        flags.append(("🚨", f"Top 10 wallets hold {top10:.1f}% — severe concentration", "high"))
    elif top10 > 40:
        whale_risk += 15
        flags.append(("⚠️", f"Top 10 wallets hold {top10:.1f}%", "medium"))
    else:
        goods.append(("✅", f"Top 10 wallets hold {top10:.1f}% — distributed"))

    whale_risk = min(100, whale_risk)

    # ════════════════════════════════════════════
    # 3. COMMUNITY STRENGTH (0-100)
    # ════════════════════════════════════════════
    community = 30  # base

    holders = data.get("holderCount", 0)
    if holders >= 2000:
        community += 40
        goods.append(("✅", f"{holders:,} holders — strong community"))
    elif holders >= 500:
        community += 25
        goods.append(("✅", f"{holders:,} holders — growing community"))
    elif holders >= 100:
        community += 10
    else:
        community -= 10
        flags.append(("⚠️", f"Only {holders} holders — very early stage", "low"))

    social = data.get("socialCount", 0)
    if data.get("hasTwitter"):
        community += 12
        goods.append(("✅", "X/Twitter presence confirmed"))
    if data.get("hasTelegram"):
        community += 10
        goods.append(("✅", "Telegram community exists"))
    if data.get("hasWebsite"):
        community += 8
        goods.append(("✅", "Official website linked"))
    if social == 0:
        flags.append(("⚠️", "No social presence detected — anonymous dev", "medium"))

    community = max(0, min(100, community))

    # ════════════════════════════════════════════
    # 4. NARRATIVE HEAT (0-100)
    # ════════════════════════════════════════════
    heat = 20

    chg = data.get("change24h")
    if chg is not None:
        if chg > 200:   heat += 40
        elif chg > 50:  heat += 25
        elif chg > 10:  heat += 12
        elif chg < -50: heat -= 15

    vol = data.get("volume24h") or 0
    liq = data.get("liquidity") or 0
    if vol > 500_000:  heat += 25
    elif vol > 100_000: heat += 15
    elif vol > 10_000:  heat += 8

    buys  = data.get("buys24h") or 0
    sells = data.get("sells24h") or 0
    total_txns = buys + sells
    if total_txns > 500:  heat += 20
    elif total_txns > 100: heat += 10
    if total_txns > 0 and buys > sells * 1.5:
        heat += 10
        goods.append(("📈", f"Buy pressure dominant: {buys} buys vs {sells} sells"))

    heat = max(0, min(100, heat))

    # ════════════════════════════════════════════
    # 5. SCAM RISK (0-100, higher = more scammy)
    # ════════════════════════════════════════════
    scam = 0

    if data.get("mintAuthority"):   scam += 25
    if data.get("freezeAuthority"): scam += 20
    if not data.get("lpBurned"):    scam += 30
    if top1 > 30:                   scam += 15
    if social == 0:                 scam += 10

    rug_risks = data.get("rugRisks") or []
    scam += min(20, len(rug_risks) * 5)

    scam = min(100, scam)

    # ════════════════════════════════════════════
    # SOLAR SIGNAL SCORE (composite)
    # ════════════════════════════════════════════
    solar = (
        safety       * 0.35 +
        (100 - whale_risk) * 0.25 +
        community    * 0.20 +
        heat         * 0.10 +
        (100 - scam) * 0.10
    )
    solar = round(max(0, min(100, solar)))

    # Grade
    if   solar >= 80: grade, verdict, gem = "A", "STRONG SIGNAL",        "🟢"
    elif solar >= 65: grade, verdict, gem = "B", "MODERATE SIGNAL",      "🟡"
    elif solar >= 45: grade, verdict, gem = "C", "WEAK SIGNAL",          "🟠"
    else:             grade, verdict, gem = "D", "DANGER — AVOID",       "🔴"

    # ════════════════════════════════════════════
    # AI SUMMARY
    # ════════════════════════════════════════════
    ai_summary = _build_summary(data, solar, safety, whale_risk, community, heat, scam)

    return {
        "solar_score":        solar,
        "safety_score":       round(safety),
        "whale_risk":         round(whale_risk),
        "community_strength": round(community),
        "narrative_heat":     round(heat),
        "scam_risk":          round(scam),
        "grade":              grade,
        "verdict":            verdict,
        "grade_emoji":        gem,
        "flags":              flags,
        "goods":              goods,
        "ai_summary":         ai_summary,
    }


def _build_summary(d, solar, safety, whale, community, heat, scam) -> str:
    """
    Generate a Bloomberg-style AI intelligence summary.
    Rule-based but feels like a premium analyst report.
    """
    parts = []
    name = d.get("name","This token")
    sym  = d.get("symbol","???")

    # Opening — overall assessment
    if solar >= 80:
        parts.append(f"Solar Signal detects strong structural integrity and positive momentum for ${sym}.")
    elif solar >= 65:
        parts.append(f"Solar Signal identifies moderate opportunity with manageable risk profile for ${sym}.")
    elif solar >= 45:
        parts.append(f"Solar Signal flags elevated risk across multiple vectors for ${sym}. Proceed with strict caution.")
    else:
        parts.append(f"Solar Signal issues a HIGH RISK alert for ${sym}. Multiple critical red flags detected.")

    # Safety assessment
    if safety >= 80:
        parts.append("Contract architecture appears clean — mint and freeze authorities secured.")
    elif safety >= 50:
        parts.append("Partial safety measures in place, however liquidity exposure remains a concern.")
    else:
        parts.append("Structural safety is critically compromised. Rug pull vectors are open.")

    # Whale analysis
    top1 = d.get("topHolderPct", 0)
    if whale <= 20:
        parts.append(f"Whale concentration is minimal with no dominant single wallet detected.")
    elif whale <= 50:
        parts.append(f"Moderate whale presence observed — top wallet controls {top1:.1f}%. Monitor for sudden dumps.")
    else:
        parts.append(f"Severe whale concentration at {top1:.1f}%. Coordinated exit risk is elevated.")

    # Community / narrative
    if community >= 70 and heat >= 60:
        parts.append("Community momentum and narrative heat are both strong — organic growth pattern detected.")
    elif heat >= 60:
        parts.append("Price momentum is active but community infrastructure remains underdeveloped.")
    elif community >= 60:
        parts.append("Community base appears solid, though market momentum is currently subdued.")
    else:
        parts.append("Social presence and narrative strength are weak. Relies on speculation over fundamentals.")

    # Final signal
    chg = d.get("change24h")
    if chg is not None and chg > 50:
        parts.append(f"24h price action shows +{chg:.0f}% — elevated FOMO risk. Entry timing is critical.")
    elif chg is not None and chg < -30:
        parts.append(f"Significant 24h decline of {chg:.0f}% — possible distribution or panic selling.")

    return " ".join(parts)
