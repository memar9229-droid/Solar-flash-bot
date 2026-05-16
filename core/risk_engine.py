"""
Risk Engine — honeypot proxies, rug pull vectors, whale analysis.
"""

def analyze_honeypot_proxies(d: dict) -> dict:
    """
    Solana doesn't have classic ETH honeypots, but we can detect
    sell restriction proxies and liquidity withdrawal risk.
    """
    risks  = []
    score  = 0  # higher = more dangerous

    if d.get("hasMintRisk"):
        score += 30
        risks.append({
            "type": "MINT_AUTHORITY",
            "severity": "HIGH",
            "msg": "Mint authority active — unlimited token printing possible"
        })

    if d.get("hasFreezeRisk"):
        score += 25
        risks.append({
            "type": "FREEZE_AUTHORITY",
            "severity": "HIGH",
            "msg": "Freeze authority active — accounts can be frozen (sell blocked)"
        })

    if d.get("lpRisk"):
        score += 35
        risks.append({
            "type": "LP_NOT_BURNED",
            "severity": "CRITICAL",
            "msg": "Liquidity not burned — developer can remove LP at any time"
        })

    rug_risks = d.get("rugRisks") or []
    for r in rug_risks[:3]:
        name  = r.get("name", "Unknown risk")
        level = r.get("level", "warn")
        score += 15 if level == "danger" else 8
        risks.append({
            "type": "RUGCHECK",
            "severity": "HIGH" if level == "danger" else "MEDIUM",
            "msg": f"RugCheck: {name}"
        })

    # Dev wallet concentration
    dev_pct = d.get("devPct", 0)
    if dev_pct > 15:
        score += 20
        risks.append({
            "type": "DEV_WALLET",
            "severity": "HIGH",
            "msg": f"Dev wallet holds {dev_pct:.1f}% — significant dump risk"
        })
    elif dev_pct > 5:
        score += 10
        risks.append({
            "type": "DEV_WALLET",
            "severity": "MEDIUM",
            "msg": f"Dev wallet holds {dev_pct:.1f}% — moderate exposure"
        })

    score = min(100, score)
    return {
        "honeypot_score": score,
        "risks": risks,
        "is_critical": score >= 60,
        "sellability": "RESTRICTED" if score >= 60 else "CAUTION" if score >= 30 else "LIKELY_OK"
    }


def analyze_whale_intelligence(d: dict) -> dict:
    """
    Advanced whale analysis — concentration, accumulation/distribution,
    suspicious clustering patterns.
    """
    top1   = d.get("topHolderPct",  0)
    top5   = d.get("top5Pct",       0)
    top10  = d.get("top10Pct",      0)
    dev    = d.get("devPct",         0)
    buys   = d.get("buys24h")  or 0
    sells  = d.get("sells24h") or 0
    chg24  = d.get("change24h") or 0

    flags = []
    risk  = 0  # 0=low, 100=extreme

    # Top wallet concentration
    if top1 > 50:
        risk += 60
        flags.append(f"🚨 Single wallet controls {top1:.1f}% — extreme danger")
    elif top1 > 25:
        risk += 40
        flags.append(f"⚠️ Top wallet: {top1:.1f}% — high concentration")
    elif top1 > 10:
        risk += 20
        flags.append(f"⚠️ Top wallet: {top1:.1f}% — moderate concentration")
    else:
        flags.append(f"✅ Top wallet: {top1:.1f}% — healthy distribution")

    # Top 5/10 clustering
    if top5 > 80:
        risk += 30
        flags.append(f"🚨 Top 5 wallets hold {top5:.1f}% — cartel-level clustering")
    elif top5 > 60:
        risk += 15
        flags.append(f"⚠️ Top 5 hold {top5:.1f}% — significant clustering")

    if top10 > 70:
        risk += 15
        flags.append(f"⚠️ Top 10 hold {top10:.1f}% — high concentration")
    else:
        flags.append(f"✅ Top 10 hold {top10:.1f}% — distributed")

    # Accumulation vs distribution signal
    total_txns = buys + sells
    if total_txns > 0:
        buy_pct = buys / total_txns * 100
        if buy_pct > 75 and chg24 > 20:
            flags.append(f"📈 Strong accumulation: {buy_pct:.0f}% buys — whales loading")
        elif buy_pct < 25 and chg24 < -20:
            risk += 20
            flags.append(f"📉 Distribution detected: {buy_pct:.0f}% buys — whales exiting")
        elif 40 < buy_pct < 65:
            flags.append(f"⚖️ Balanced flow: {buy_pct:.0f}% buys — healthy activity")

    # Dev wallet signal
    if dev > 0:
        if dev > 15:
            flags.append(f"🚨 Dev wallet: {dev:.1f}% — major dump risk")
        elif dev > 5:
            flags.append(f"⚠️ Dev wallet: {dev:.1f}% — monitor closely")
        else:
            flags.append(f"✅ Dev wallet: {dev:.1f}% — low exposure")

    risk = min(100, risk)

    # Whale threat label
    if risk >= 70:   threat = "EXTREME"
    elif risk >= 45: threat = "HIGH"
    elif risk >= 25: threat = "MEDIUM"
    else:            threat = "LOW"

    return {
        "whale_risk":  risk,
        "threat":      threat,
        "flags":       flags,
        "top1_pct":    top1,
        "top5_pct":    top5,
        "top10_pct":   top10,
        "dev_pct":     dev,
        "buy_pressure": round(buys/total_txns*100, 1) if total_txns else None,
    }
