"""
Data fetching layer — all external API calls.
Each function returns None on failure (never raises).
"""
import asyncio
import aiohttp
from config import HELIUS_RPC, DEXSCREENER, RUGCHECK, BIRDEYE_BASE, BIRDEYE_KEY

TIMEOUT = aiohttp.ClientTimeout(total=12)

# ── HELIUS RPC ───────────────────────────────────────────────────────
async def _rpc(session, method, params):
    try:
        async with session.post(
            HELIUS_RPC,
            json={"jsonrpc":"2.0","id":1,"method":method,"params":params},
            headers={"Content-Type":"application/json"},
            timeout=TIMEOUT
        ) as r:
            return (await r.json()).get("result")
    except Exception as e:
        print(f"[RPC] {method} failed: {e}")
        return None

async def fetch_asset(session, mint):
    return await _rpc(session, "getAsset",
        {"id": mint, "displayOptions": {"showFungible": True}})

async def fetch_mint_info(session, mint):
    result = await _rpc(session, "getAccountInfo",
        [mint, {"encoding": "jsonParsed"}])
    if not result: return {}
    return (result.get("value") or {}).get("data",{}).get("parsed",{}).get("info",{})

async def fetch_holders(session, mint):
    result = await _rpc(session, "getTokenLargestAccounts", [mint])
    if not result: return []
    return result.get("value", [])

async def fetch_signatures(session, mint):
    """Recent transactions — used for activity detection."""
    result = await _rpc(session, "getSignaturesForAddress",
        [mint, {"limit": 20}])
    return result or []

# ── DEXSCREENER ──────────────────────────────────────────────────────
async def fetch_dex(session, mint):
    try:
        async with session.get(
            f"{DEXSCREENER}/{mint}", timeout=TIMEOUT
        ) as r:
            j = await r.json()
            pairs = j.get("pairs") or []
            if not pairs: return None
            # Pick highest liquidity pair
            return sorted(pairs, key=lambda p: float(p.get("liquidity",{}).get("usd",0) or 0), reverse=True)[0]
    except Exception as e:
        print(f"[DEX] failed: {e}")
        return None

# ── RUGCHECK ─────────────────────────────────────────────────────────
async def fetch_rugcheck(session, mint):
    try:
        async with session.get(
            f"{RUGCHECK}/{mint}/report/summary", timeout=TIMEOUT
        ) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        print(f"[RUGCHECK] failed: {e}")
    return None

# ── BIRDEYE (optional) ───────────────────────────────────────────────
async def fetch_birdeye(session, mint):
    if not BIRDEYE_KEY: return None
    try:
        async with session.get(
            f"{BIRDEYE_BASE}/defi/token_overview",
            params={"address": mint},
            headers={"X-API-KEY": BIRDEYE_KEY, "x-chain": "solana"},
            timeout=TIMEOUT
        ) as r:
            if r.status == 200:
                return (await r.json()).get("data")
    except Exception as e:
        print(f"[BIRDEYE] failed: {e}")
    return None

# ── COMBINED FETCH ───────────────────────────────────────────────────
async def fetch_all(mint: str) -> dict:
    """Fetch all data sources concurrently."""
    async with aiohttp.ClientSession() as session:
        asset, mint_info, holders, sigs, dex, rugcheck, birdeye = await asyncio.gather(
            fetch_asset(session, mint),
            fetch_mint_info(session, mint),
            fetch_holders(session, mint),
            fetch_signatures(session, mint),
            fetch_dex(session, mint),
            fetch_rugcheck(session, mint),
            fetch_birdeye(session, mint),
        )
    return {
        "asset":     asset,
        "mint_info": mint_info or {},
        "holders":   holders or [],
        "sigs":      sigs or [],
        "dex":       dex,
        "rugcheck":  rugcheck,
        "birdeye":   birdeye,
    }
