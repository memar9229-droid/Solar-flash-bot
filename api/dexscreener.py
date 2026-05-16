import aiohttp
from config import DEXSCREENER

TIMEOUT = aiohttp.ClientTimeout(total=10)

async def fetch(session: aiohttp.ClientSession, mint: str) -> dict | None:
    try:
        async with session.get(f"{DEXSCREENER}/{mint}", timeout=TIMEOUT) as r:
            j = await r.json()
            pairs = j.get("pairs") or []
            if not pairs:
                return None
            # Pick highest liquidity pair
            return sorted(
                pairs,
                key=lambda p: float((p.get("liquidity") or {}).get("usd", 0) or 0),
                reverse=True
            )[0]
    except Exception as e:
        print(f"[DexScreener] {e}")
        return None
