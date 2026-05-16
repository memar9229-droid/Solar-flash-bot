import aiohttp
from config import HELIUS_RPC

TIMEOUT = aiohttp.ClientTimeout(total=12)

async def _rpc(session: aiohttp.ClientSession, method: str, params: list) -> dict | None:
    try:
        async with session.post(
            HELIUS_RPC,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT
        ) as r:
            return (await r.json()).get("result")
    except Exception as e:
        print(f"[Helius] {method}: {e}")
        return None

async def fetch_asset(session, mint):
    return await _rpc(session, "getAsset", {
        "id": mint,
        "displayOptions": {"showFungible": True}
    })

async def fetch_mint_info(session, mint):
    result = await _rpc(session, "getAccountInfo", [mint, {"encoding": "jsonParsed"}])
    if not result:
        return {}
    return ((result.get("value") or {}).get("data") or {}).get("parsed", {}).get("info", {})

async def fetch_largest_holders(session, mint):
    result = await _rpc(session, "getTokenLargestAccounts", [mint])
    return (result or {}).get("value") or []

async def fetch_signatures(session, mint, limit=30):
    result = await _rpc(session, "getSignaturesForAddress", [mint, {"limit": limit}])
    return result or []

async def fetch_token_accounts(session, mint):
    """Get all token accounts for supply distribution."""
    result = await _rpc(session, "getTokenSupply", [mint])
    return result or {}
