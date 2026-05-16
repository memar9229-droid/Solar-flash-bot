import aiohttp
from config import RUGCHECK

TIMEOUT = aiohttp.ClientTimeout(total=10)

async def fetch(session: aiohttp.ClientSession, mint: str) -> dict | None:
    try:
        async with session.get(
            f"{RUGCHECK}/{mint}/report/summary", timeout=TIMEOUT
        ) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        print(f"[RugCheck] {e}")
    return None

async def fetch_full(session: aiohttp.ClientSession, mint: str) -> dict | None:
    try:
        async with session.get(
            f"{RUGCHECK}/{mint}/report", timeout=TIMEOUT
        ) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        print(f"[RugCheck Full] {e}")
    return None
