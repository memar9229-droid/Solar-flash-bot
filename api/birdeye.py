import aiohttp
from config import BIRDEYE_BASE, BIRDEYE_KEY

TIMEOUT = aiohttp.ClientTimeout(total=10)
HEADERS = {"X-API-KEY": BIRDEYE_KEY, "x-chain": "solana"}

async def _get(session, path, params=None):
    if not BIRDEYE_KEY:
        return None
    try:
        async with session.get(
            f"{BIRDEYE_BASE}{path}",
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT
        ) as r:
            if r.status == 200:
                return (await r.json()).get("data")
    except Exception as e:
        print(f"[Birdeye] {path}: {e}")
    return None

async def fetch_overview(session: aiohttp.ClientSession, mint: str) -> dict | None:
    """Token overview — price, volume, unique wallets."""
    return await _get(session, "/defi/token_overview", {"address": mint})

async def fetch_holders(session: aiohttp.ClientSession, mint: str) -> dict | None:
    """Holder count and distribution."""
    return await _get(session, "/defi/v3/token/holder", {"address": mint, "limit": 20})

async def fetch_trades(session: aiohttp.ClientSession, mint: str) -> dict | None:
    """Recent trade history."""
    return await _get(session, "/defi/txs/token", {
        "address": mint, "limit": 50, "tx_type": "swap"
    })

async def fetch_all(session: aiohttp.ClientSession, mint: str) -> dict:
    """Fetch all Birdeye data concurrently."""
    import asyncio
    overview, holders, trades = await asyncio.gather(
        fetch_overview(session, mint),
        fetch_holders(session, mint),
        fetch_trades(session, mint),
    )
    return {
        "overview": overview or {},
        "holders":  holders  or {},
        "trades":   trades   or {},
    }
