"""
All Telegram handlers — commands and messages.
"""
import re
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from config import TG_CHANNEL, X_URL, BOT_USERNAME, REPORT_URL
from fetchers import fetch_all
from parser import parse
from scorer import score
from formatters import (
    build_full_report, build_score_card,
    main_keyboard, report_keyboard
)

log = logging.getLogger(__name__)
SOL_RE = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")

# ── RATE LIMITER ─────────────────────────────────────────────────────
_last_request: dict[int, float] = {}

def _is_rate_limited(user_id: int) -> bool:
    import time
    now = time.time()
    last = _last_request.get(user_id, 0)
    if now - last < 8:   # 8 sec cooldown per user
        return True
    _last_request[user_id] = now
    return False

# ── CORE ANALYSIS ────────────────────────────────────────────────────
async def run_analysis(mint: str) -> tuple[dict, dict]:
    raw    = await fetch_all(mint)
    data   = parse(mint, raw)
    scores = score(data)
    return data, scores

# ── HANDLERS ─────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "☀️ *SOLAR SIGNAL BOT*\n"
        "_by Solar Flash — Elite Solana Intelligence_\n\n"
        "Built to detect signal before noise.\n\n"
        "📋 *Commands:*\n"
        "/analyze `<address>` — Full intelligence report\n"
        "/score `<address>` — Quick signal score\n"
        "/help — How to use\n"
        "/about — About Solar Flash\n\n"
        "_Or just paste any Solana token address_ ↓",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "☀️ *HOW TO USE SOLAR SIGNAL BOT*\n\n"
        "*Option 1 — Just paste an address:*\n"
        "`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`\n\n"
        "*Option 2 — Use commands:*\n"
        "/analyze `<address>` — Full report with AI summary\n"
        "/score `<address>` — Quick score card\n\n"
        "*What we analyze:*\n"
        "• Mint & Freeze authority status\n"
        "• LP burn / lock detection\n"
        "• Whale & holder concentration\n"
        "• Live price, market cap & volume\n"
        "• Buy/sell pressure ratio\n"
        "• Social presence\n"
        "• RugCheck risk scan\n"
        "• AI-powered intelligence summary\n\n"
        "_Accuracy > Hype. Signal > Speculation._ ⊙",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_about(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⊙ *SOLAR SIGNAL BOT — by Solar Flash*\n\n"
        "_Built to detect signal before noise._\n"
        "_AI-powered Solana memecoin intelligence._\n\n"
        "📡 Data Sources:\n"
        "• Helius RPC — on-chain data\n"
        "• DexScreener — market data\n"
        "• RugCheck — contract risk\n\n"
        "🚀 Part of the $FLASH ecosystem:\n"
        f"• Web Scanner: {REPORT_URL}\n"
        f"• Community: {TG_CHANNEL}\n"
        f"• X: {X_URL}\n\n"
        "_Phase 1 of the Solar Flash infrastructure._\n"
        "_Solar Dashboard & Whale Watch coming soon._",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )

async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "⚠️ Usage: `/analyze <token_address>`\n\n"
            "Example:\n`/analyze DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    await _do_analyze(update, ctx.args[0].strip(), full=True)

async def cmd_score(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "⚠️ Usage: `/score <token_address>`\n\n"
            "Example:\n`/score DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    await _do_analyze(update, ctx.args[0].strip(), full=False)

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text  = (update.message.text or "").strip()
    match = SOL_RE.search(text)
    if match:
        await _do_analyze(update, match.group(), full=True)
    else:
        await update.message.reply_text(
            "⊙ Paste a Solana token address to scan.\n\n"
            "Example:\n"
            "`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263` _(BONK)_",
            parse_mode=ParseMode.MARKDOWN
        )

# ── CORE FLOW ────────────────────────────────────────────────────────
async def _do_analyze(update: Update, mint: str, full: bool):
    uid = update.effective_user.id

    if _is_rate_limited(uid):
        await update.message.reply_text(
            "⏳ Please wait a few seconds before scanning again.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Validate address format
    if not SOL_RE.fullmatch(mint):
        await update.message.reply_text(
            "❌ *Invalid address format.*\n"
            "Please paste a valid Solana token contract address.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Show scanning message
    msg = await update.message.reply_text(
        "☀️ *Solar Signal scanning...*\n\n"
        "⛓ Fetching on-chain data\n"
        "📊 Pulling market intelligence\n"
        "🧠 Running risk analysis\n"
        "⊙ Generating AI signal",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        data, scores = await asyncio.wait_for(
            run_analysis(mint), timeout=25
        )

        if full:
            text = build_full_report(data, scores)
        else:
            text = build_score_card(data, scores)

        kb = report_keyboard(data.get("dexUrl"))
        await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                            reply_markup=kb,
                            disable_web_page_preview=True)

    except asyncio.TimeoutError:
        await msg.edit_text(
            "⏱ *Analysis timed out.*\n"
            "The network is slow. Please try again in a moment.",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        log.error(f"Analysis error for {mint}: {e}", exc_info=True)
        await msg.edit_text(
            "❌ *Could not analyze this token.*\n\n"
            "Possible reasons:\n"
            "• Invalid or unrecognized contract\n"
            "• Token not yet on DexScreener\n"
            "• Network timeout\n\n"
            f"`{mint[:20]}...`",
            parse_mode=ParseMode.MARKDOWN
        )
