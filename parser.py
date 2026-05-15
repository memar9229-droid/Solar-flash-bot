"""
Parse raw API responses into a clean normalized dict.
"""

BURN_ADDRS = {
    "1nc1nerator11111111111111111111111111111111",
    "11111111111111111111111111111111",
}

def parse(mint: str, raw: dict) -> dict:
    asset     = raw.get("asset") or {}
    mint_info = raw.get("mint_info") or {}
    holders   = raw.get("holders") or []
    dex       = raw.get("dex") or {}
    rugcheck  = raw.get("rugcheck") or {}
    birdeye   = raw.get("birdeye") or {}

    # ── Identity ────────────────────────────────────────────────────
    meta   = asset.get("content",{}).get("metadata",{})
    ti     = asset.get("token_info",{}) or {}
    name   = meta.get("name") or ti.get("symbol") or "Unknown Token"
    symbol = ti.get("symbol") or "???"
    image  = (asset.get("content",{}).get("links",{}) or {}).get("image")

    # ── Supply / decimals ────────────────────────────────────────────
    decimals   = int(mint_info.get("decimals", 6))
    supply_raw = int(mint_info.get("supply", 0))
    supply     = supply_raw / 10**decimals if supply_raw else None

    # ── Authorities ──────────────────────────────────────────────────
    mint_auth   = mint_info.get("mintAuthority")
    freeze_auth = mint_info.get("freezeAuthority")

    # ── Holders ──────────────────────────────────────────────────────
    holder_count  = len(holders)
    top_holder_pct = 0.0
    top10_pct      = 0.0
    lp_burned      = False

    if holders and supply_raw:
        top_amt = int(holders[0]["amount"]) if holders else 0
        top_holder_pct = top_amt / supply_raw * 100

        top10_sum = sum(int(h["amount"]) for h in holders[:10])
        top10_pct = top10_sum / supply_raw * 100

        lp_burned = any(
            h.get("address","") in BURN_ADDRS
            or h.get("address","").startswith("11111")
            for h in holders
        )

    # ── DEX data ─────────────────────────────────────────────────────
    def _f(key, sub=None):
        v = dex.get(key) if not sub else (dex.get(key) or {}).get(sub)
        return float(v) if v not in (None, "", "0") else None

    price     = _f("priceUsd")
    mcap      = _f("fdv")
    liq       = _f("liquidity", "usd")
    vol24     = _f("volume", "h24")
    chg24     = _f("priceChange", "h24")
    buys24    = (dex.get("txns",{}).get("h24",{}) or {}).get("buys")
    sells24   = (dex.get("txns",{}).get("h24",{}) or {}).get("sells")
    dex_url   = dex.get("url")
    pair_age  = dex.get("pairCreatedAt")

    # Social from DEX
    info      = dex.get("info",{}) or {}
    socials   = info.get("socials") or []
    websites  = info.get("websites") or []
    has_twitter  = any(s.get("type","").lower() in ("twitter","x") for s in socials)
    has_telegram = any(s.get("type","").lower() == "telegram" for s in socials)
    has_website  = len(websites) > 0

    # ── RugCheck ─────────────────────────────────────────────────────
    rug_score = rugcheck.get("score")           # 0=good, 100=bad
    rug_risks = rugcheck.get("risks") or []

    # ── Birdeye ──────────────────────────────────────────────────────
    unique_wallets = birdeye.get("uniqueWallet24h")
    trade_history  = birdeye.get("trade24h")

    # ── Activity ─────────────────────────────────────────────────────
    recent_txns = len(raw.get("sigs", []))

    return {
        # identity
        "mint": mint, "name": name, "symbol": symbol, "image": image,
        # authorities
        "mintAuthority": mint_auth, "freezeAuthority": freeze_auth,
        # supply / holders
        "supply": supply, "decimals": decimals,
        "holderCount": holder_count,
        "topHolderPct": top_holder_pct,
        "top10Pct": top10_pct,
        "lpBurned": lp_burned,
        # market
        "price": price, "marketCap": mcap,
        "liquidity": liq, "volume24h": vol24,
        "change24h": chg24,
        "buys24h": buys24, "sells24h": sells24,
        "pairAge": pair_age, "dexUrl": dex_url,
        # social
        "hasTwitter": has_twitter,
        "hasTelegram": has_telegram,
        "hasWebsite": has_website,
        "socialCount": sum([has_twitter, has_telegram, has_website]),
        # rugcheck
        "rugScore": rug_score,
        "rugRisks": rug_risks,
        # birdeye
        "uniqueWallets24h": unique_wallets,
        "trades24h": trade_history,
        # activity
        "recentTxns": recent_txns,
    }
