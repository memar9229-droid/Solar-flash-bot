"""
/analyze and address paste handler — full intelligence report.
"""
import asyncio
import time
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import ANALYSIS_TIMEOUT, SCAN_COOLDOWN_SEC
from core.formatter import build_full_report, build_score_card, report_keyboard
from core.scorer import score
from core.parser import parse
from api import helius, dexscreener, rugcheck, birdeye, social as social_api
import aiohttp

log = logging.getLogger(__name__)
_rate: dict[int, float] = {}

async def fetch_all(mint: str) -> dict:
    async with aiohttp.ClientSession() as session:
        asset, mint_info, holders, sigs, dex, rug, be = await asyncio.gather(
            helius.fetch_asset(session, mint),
            helius.fetch_mint_info(session, mint),
            helius.fetch_largest_holders(session, mint),
            helius.fetch_signatures(session, mint),
            dexscreener.fetch(session, mint),
            rugcheck.fetch(session, mint),
            birdeye.fetch_all(session, mint),
        )
    social_signals = social_api.analyze_social_signals(dex or {}, be or {})
    return {
        "asset": asset, "mint_info": mint_info, "holders": holders,
        "sigs": sigs, "dex": dex, "rugcheck": rug,
        "birdeye": be, "social": social_signals,
    }

async def run_analysis(mint: str, full: bool, update: Update):
    chat_id = update.effective_chat.id
    uid     = update.effective_user.id

    # Rate limit
    now = time.time()
    if now - _rate.get(uid, 0) < SCAN_COOLDOWN_SEC:
        await update.message.reply_text(
            "⏳ Please wait a few seconds before scanning again."
        )
        return
    _rate[uid] = now

    msg = await update.message.reply_text(
        "☀️ *Solar Signal scanning...*\n\n"
        "⛓ Querying on-chain data\n"
        "📊 Pulling market intelligence\n"
        "🐋 Running whale analysis\n"
        "🧠 Generating AI signal",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        raw    = await asyncio.wait_for(fetch_all(mint), timeout=ANALYSIS_TIMEOUT)
        data   = parse(mint, raw)
        scores = score(data)
        text   = build_full_report(data, scores) if full else build_score_card(data, scores)
        kb     = report_keyboard(data.get("dexUrl"))
        await msg.edit_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb, disable_web_page_preview=True
        )
    except asyncio.TimeoutError:
        await msg.edit_text(
            "⏱ *Analysis timed out.* Network is slow — please try again.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        log.error(f"Analysis error [{mint}]: {e}", exc_info=True)
        await msg.edit_text(
            "❌ *Could not analyze this token.*\n\n"
            "• Check the address is correct\n"
            "• Token may not be on DexScreener yet\n"
            "• Try again in a moment",
            parse_mode=ParseMode.MARKDOWN
        )
