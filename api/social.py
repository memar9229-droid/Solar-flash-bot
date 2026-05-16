import aiohttp
import asyncio

TIMEOUT = aiohttp.ClientTimeout(total=8)

async def check_website(session: aiohttp.ClientSession, url: str) -> dict:
    """Check if website is live and gather basic signals."""
    if not url:
        return {"live": False, "has_content": False}
    try:
        async with session.get(url, timeout=TIMEOUT, allow_redirects=True) as r:
            text = await r.text()
            return {
                "live": r.status < 400,
                "has_content": len(text) > 500,
                "has_whitepaper": "whitepaper" in text.lower() or "litepaper" in text.lower(),
                "has_roadmap": "roadmap" in text.lower(),
                "has_tokenomics": "tokenomics" in text.lower() or "supply" in text.lower(),
            }
    except:
        return {"live": False, "has_content": False}

def analyze_social_signals(dex_data: dict, birdeye_data: dict) -> dict:
    """
    Analyze social presence and authenticity signals.
    Returns scoring dict for organic vs artificial hype detection.
    """
    info     = (dex_data.get("info") or {})
    socials  = info.get("socials") or []
    websites = info.get("websites") or []

    has_twitter  = any(s.get("type","").lower() in ("twitter","x") for s in socials)
    has_telegram = any(s.get("type","").lower() == "telegram" for s in socials)
    has_website  = len(websites) > 0
    website_url  = websites[0].get("url") if websites else None

    social_count = sum([has_twitter, has_telegram, has_website])

    # Organic vs Artificial signals from market data
    dex = dex_data or {}
    vol24    = float((dex.get("volume") or {}).get("h24") or 0)
    vol6     = float((dex.get("volume") or {}).get("h6") or 0)
    vol1     = float((dex.get("volume") or {}).get("h1") or 0)
    liq      = float((dex.get("liquidity") or {}).get("usd") or 0)
    buys24   = (dex.get("txns") or {}).get("h24", {}).get("buys") or 0
    sells24  = (dex.get("txns") or {}).get("h24", {}).get("sells") or 0
    txns24   = buys24 + sells24

    # Authenticity signals
    organic_score = 50  # neutral base

    # Volume/liquidity ratio — bot trading inflates this unnaturally
    if liq > 0:
        vol_liq_ratio = vol24 / liq
        if vol_liq_ratio > 50:
            organic_score -= 20  # suspicious — very high volume vs liquidity
        elif vol_liq_ratio > 20:
            organic_score -= 10
        elif 0.5 < vol_liq_ratio < 10:
            organic_score += 15  # healthy ratio

    # Buy/sell balance — bots often create imbalanced patterns
    if txns24 > 0:
        buy_ratio = buys24 / txns24
        if 0.35 < buy_ratio < 0.75:
            organic_score += 15  # balanced = more organic
        elif buy_ratio > 0.9 or buy_ratio < 0.1:
            organic_score -= 20  # extreme imbalance = suspicious

    # Social presence = legitimacy signal
    organic_score += social_count * 8

    # Volume consistency
    if vol6 > 0 and vol24 > 0:
        consistency = vol6 / (vol24 / 4)
        if 0.5 < consistency < 2.0:
            organic_score += 10  # consistent volume = organic
        else:
            organic_score -= 10  # spike pattern = artificial

    organic_score = max(0, min(100, organic_score))

    # Meme potential score
    meme_score = 30
    if has_twitter:  meme_score += 20
    if has_telegram: meme_score += 15
    vol_momentum = min(40, int(vol24 / 10000))
    meme_score += vol_momentum
    meme_score = max(0, min(100, meme_score))

    # Cult potential
    cult_score = 20
    if has_telegram: cult_score += 25
    if txns24 > 200: cult_score += 20
    if has_twitter:  cult_score += 15
    chg24 = float((dex.get("priceChange") or {}).get("h24") or 0)
    if chg24 > 50:   cult_score += 20
    cult_score = max(0, min(100, cult_score))

    # Narrative heat
    narrative = 20
    if chg24 > 200:  narrative += 50
    elif chg24 > 50: narrative += 30
    elif chg24 > 10: narrative += 15
    if vol24 > 1_000_000: narrative += 25
    elif vol24 > 100_000: narrative += 15
    elif vol24 > 10_000:  narrative += 8
    narrative = max(0, min(100, narrative))

    return {
        "has_twitter":   has_twitter,
        "has_telegram":  has_telegram,
        "has_website":   has_website,
        "website_url":   website_url,
        "social_count":  social_count,
        "organic_score": round(organic_score),
        "meme_score":    round(meme_score),
        "cult_score":    round(cult_score),
        "narrative":     round(narrative),
        "vol_liq_ratio": round(vol24/liq, 2) if liq else None,
        "buy_ratio":     round(buys24/txns24*100, 1) if txns24 else None,
    }
