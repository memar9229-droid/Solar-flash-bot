"""
AI Summary Generator — Bloomberg Terminal meets crypto intelligence.
Rule-based but feels like a premium analyst report.
"""

def generate(data: dict, scores: dict) -> str:
    sym    = data.get("symbol", "???")
    solar  = scores["solar_score"]
    safety = scores["safety_score"]
    whale  = scores["whale_risk"]
    comm   = scores["community"]
    heat   = scores["narrative_heat"]
    organic= scores["organic_score"]
    meme   = scores["meme_score"]
    cult   = scores["cult_score"]
    top1   = data.get("topHolderPct", 0)
    chg24  = data.get("change24h") or 0
    holders= data.get("holderCount", 0)

    parts = []

    # ── Opening assessment ────────────────────────────────────────
    if solar >= 80:
        parts.append(
            f"Solar Signal detects strong structural integrity and favorable "
            f"market positioning for ${sym}."
        )
    elif solar >= 65:
        parts.append(
            f"Solar Signal identifies moderate opportunity in ${sym} "
            f"with manageable risk profile across key vectors."
        )
    elif solar >= 45:
        parts.append(
            f"Solar Signal flags elevated risk across multiple critical vectors "
            f"for ${sym}. Selective entry only — strict risk management required."
        )
    else:
        parts.append(
            f"Solar Signal issues a HIGH RISK alert for ${sym}. "
            f"Multiple critical red flags detected. Capital protection is priority."
        )

    # ── Safety layer ──────────────────────────────────────────────
    if safety >= 85:
        parts.append(
            "Contract architecture is clean — mint and freeze authorities are "
            "secured, and liquidity infrastructure shows no withdrawal vectors."
        )
    elif safety >= 60:
        parts.append(
            "Partial safety measures detected. Core contract risks are partially "
            "mitigated, however liquidity exposure warrants monitoring."
        )
    else:
        parts.append(
            "Structural safety is critically compromised. "
            "One or more rug pull vectors remain open."
        )

    # ── Whale intelligence ─────────────────────────────────────────
    if whale <= 20:
        parts.append(
            "Whale concentration is minimal — token distribution appears healthy "
            "with no dominant single wallet detected."
        )
    elif whale <= 45:
        parts.append(
            f"Moderate whale presence observed. Top wallet controls {top1:.1f}% — "
            f"monitor for coordinated distribution events."
        )
    else:
        parts.append(
            f"Severe whale concentration at {top1:.1f}%. "
            f"Coordinated exit risk is elevated — treat with extreme caution."
        )

    # ── Community & narrative ──────────────────────────────────────
    if comm >= 70 and heat >= 60:
        parts.append(
            "Community momentum and narrative heat are both strong — "
            "organic growth pattern with active engagement detected."
        )
    elif heat >= 60 and comm < 50:
        parts.append(
            "Price momentum is running hot, but community infrastructure "
            "remains underdeveloped. Momentum-driven, not fundamentals-driven."
        )
    elif comm >= 60:
        parts.append(
            "Community base is solid with active social presence, "
            "though market momentum is currently subdued."
        )
    else:
        parts.append(
            "Community depth and narrative strength are insufficient. "
            "Token relies on speculation over structural legitimacy."
        )

    # ── Organic vs artificial ──────────────────────────────────────
    if organic < 30:
        parts.append(
            "Growth pattern analysis suggests artificial hype amplification — "
            "exercise extreme caution around entry timing."
        )
    elif organic > 70:
        parts.append(
            "Growth pattern appears largely organic with healthy buy/sell ratio "
            "and consistent volume distribution."
        )

    # ── Meme & cult potential ──────────────────────────────────────
    if meme >= 70:
        parts.append(
            f"Meme potential is high — strong virality indicators detected. "
            f"Cult formation probability: {'strong' if cult >= 60 else 'moderate'}."
        )
    elif meme >= 40:
        parts.append("Moderate meme potential — narrative requires further catalyst.")

    # ── 24h momentum ──────────────────────────────────────────────
    if chg24 > 100:
        parts.append(
            f"24h price surge of +{chg24:.0f}% detected — "
            f"FOMO risk is elevated. Entry timing is critical."
        )
    elif chg24 < -40:
        parts.append(
            f"Significant 24h decline of {chg24:.0f}% — "
            f"distribution or panic selling in progress."
        )

    return " ".join(parts)
