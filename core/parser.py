"""
Normalize raw API responses into a clean, unified data structure.
"""
from config import BURN_ADDRS

def parse(mint: str, raw: dict) -> dict:
    asset    = raw.get("asset")     or {}
    mint_info= raw.get("mint_info") or {}
    holders  = raw.get("holders")   or []
    dex      = raw.get("dex")       or {}
    rugcheck = raw.get("rugcheck")  or {}
    birdeye  = raw.get("birdeye")   or {}
    social   = raw.get("social")    or {}
    sigs     = raw.get("sigs")      or []

    # ── Identity ─────────────────────────────────────────────────
    meta   = asset.get("content", {}).get("metadata", {})
    ti     = asset.get("token_info", {}) or {}
    name   = meta.get("name") or ti.get("symbol") or "Unknown Token"
    symbol = ti.get("symbol") or "???"
    image  = (asset.get("content", {}).get("links") or {}).get("image")
    desc   = meta.get("description", "")

    # ── Supply / decimals ─────────────────────────────────────────
    decimals   = int(mint_info.get("decimals", 6))
    supply_raw = int(mint_info.get("supply", 0))
    supply     = supply_raw / 10 ** decimals if supply_raw else None

    # ── Authorities ───────────────────────────────────────────────
    mint_auth   = mint_info.get("mintAuthority")
    freeze_auth = mint_info.get("freezeAuthority")

    # ── Holders & Whale Analysis ──────────────────────────────────
    holder_count   = len(holders)
    top_holder_pct = 0.0
    top5_pct       = 0.0
    top10_pct      = 0.0
    lp_burned      = False
    dev_wallet     = None
    dev_pct        = 0.0

    if holders and supply_raw:
        top_amt        = int(holders[0].get("amount", 0))
        top_holder_pct = top_amt / supply_raw * 100

        top5_sum  = sum(int(h.get("amount", 0)) for h in holders[:5])
        top10_sum = sum(int(h.get("amount", 0)) for h in holders[:10])
        top5_pct  = top5_sum  / supply_raw * 100
        top10_pct = top10_sum / supply_raw * 100

        lp_burned = any(
            h.get("address", "") in BURN_ADDRS or
            h.get("address", "").startswith("11111")
            for h in holders
        )

        # Dev wallet heuristic: largest non-burn holder > 5% that
        # isn't a known program/burn address
        for h in holders[:5]:
            addr = h.get("address", "")
            pct  = int(h.get("amount", 0)) / supply_raw * 100
            if addr not in BURN_ADDRS and not addr.startswith("11111") and pct > 3:
                dev_wallet = addr
                dev_pct    = pct
                break

    # ── Honeypot / Sell Restriction Proxies ──────────────────────
    rug_risks  = rugcheck.get("risks") or []
    rug_score  = rugcheck.get("score")           # 0=safe, 1000=danger
    has_freeze = bool(freeze_auth)
    has_mint   = bool(mint_auth)
    lp_risk    = not lp_burned

    # ── DEX Market Data ───────────────────────────────────────────
    def _f(d, key, sub=None):
        v = d.get(key) if not sub else (d.get(key) or {}).get(sub)
        try:
            return float(v) if v not in (None, "", "0") else None
        except:
            return None

    price     = _f(dex, "priceUsd")
    mcap      = _f(dex, "fdv")
    liq       = _f(dex, "liquidity", "usd")
    vol24     = _f(dex, "volume", "h24")
    vol6      = _f(dex, "volume", "h6")
    vol1      = _f(dex, "volume", "h1")
    chg24     = _f(dex, "priceChange", "h24")
    chg6      = _f(dex, "priceChange", "h6")
    chg1      = _f(dex, "priceChange", "h1")
    buys24    = (dex.get("txns") or {}).get("h24", {}).get("buys")
    sells24   = (dex.get("txns") or {}).get("h24", {}).get("sells")
    dex_url   = dex.get("url")
    pair_age  = dex.get("pairCreatedAt")         # timestamp ms

    # Pair age in human form
    age_str = None
    if pair_age:
        import time
        diff = time.time() - pair_age / 1000
        days = int(diff // 86400)
        hrs  = int((diff % 86400) // 3600)
        mins = int((diff % 3600) // 60)
        if days > 0:   age_str = f"{days}d {hrs}h"
        elif hrs > 0:  age_str = f"{hrs}h {mins}m"
        else:          age_str = f"{mins}m"

    # ── Birdeye ───────────────────────────────────────────────────
    be_ov    = birdeye.get("overview") or {}
    be_hold  = birdeye.get("holders")  or {}
    unique_wallets_24h = be_ov.get("uniqueWallet24h")
    holder_count_be    = be_hold.get("total")
    if holder_count_be:
        holder_count = max(holder_count, holder_count_be)

    return {
        # identity
        "mint": mint, "name": name, "symbol": symbol,
        "image": image, "description": desc,
        # authorities & honeypot proxies
        "mintAuthority":   mint_auth,
        "freezeAuthority": freeze_auth,
        "hasMintRisk":     has_mint,
        "hasFreezeRisk":   has_freeze,
        "lpBurned":        lp_burned,
        "lpRisk":          lp_risk,
        # supply & holders
        "supply": supply, "decimals": decimals,
        "holderCount":   holder_count,
        "topHolderPct":  round(top_holder_pct, 2),
        "top5Pct":       round(top5_pct, 2),
        "top10Pct":      round(top10_pct, 2),
        # dev wallet
        "devWallet":     dev_wallet,
        "devPct":        round(dev_pct, 2),
        # market
        "price": price, "marketCap": mcap,
        "liquidity": liq,
        "volume24h": vol24, "volume6h": vol6, "volume1h": vol1,
        "change24h": chg24, "change6h": chg6, "change1h": chg1,
        "buys24h": buys24, "sells24h": sells24,
        "pairAge": age_str, "pairCreatedAt": pair_age,
        "dexUrl": dex_url,
        # rugcheck
        "rugScore": rug_score,
        "rugRisks": rug_risks,
        # birdeye
        "uniqueWallets24h": unique_wallets_24h,
        # social
        "hasTwitter":    social.get("has_twitter", False),
        "hasTelegram":   social.get("has_telegram", False),
        "hasWebsite":    social.get("has_website", False),
        "websiteUrl":    social.get("website_url"),
        "socialCount":   social.get("social_count", 0),
        "organicScore":  social.get("organic_score", 50),
        "memeScore":     social.get("meme_score", 0),
        "cultScore":     social.get("cult_score", 0),
        "narrativeHeat": social.get("narrative", 0),
        # activity
        "recentTxns":    len(sigs),
    }
