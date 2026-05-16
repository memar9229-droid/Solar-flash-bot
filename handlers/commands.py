"""
Command handlers — /start, /help, /about, /score
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config import REPORT_URL, TG_CHANNEL, X_URL

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Web Scanner", url=REPORT_URL)],
        [InlineKeyboardButton("⚡ Join $FLASH", url=TG_CHANNEL)],
    ])

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "☀️ *SOLAR SIGNAL BOT*\n"
        "_by Solar Flash — Elite Solana Intelligence_\n\n"
        "Paste any Solana token address for a full intelligence report.\n\n"
        "📋 *Commands:*\n"
        "/analyze `<address>` — Full signal report\n"
        "/score `<address>` — Quick score card\n"
        "/help — How to use\n"
        "/about — About Solar Flash\n\n"
        "_Or just paste a token address below_ ↓",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_keyboard()
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "☀️ *HOW TO USE SOLAR SIGNAL BOT*\n\n"
        "*Option 1 — Paste address directly:*\n"
        "`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`\n\n"
        "*Option 2 — Use commands:*\n"
        "/analyze `<address>` — Full intelligence report\n"
        "/score `<address>` — Quick score card\n\n"
        "*What Solar Signal analyzes:*\n"
        "• Mint & Freeze authority (sell restriction proxies)\n"
        "• LP burn status & liquidity risk\n"
        "• Whale concentration & clustering\n"
        "• Dev wallet detection & exposure\n"
        "• Live price, market cap, volume\n"
        "• Buy/sell pressure ratio\n"
        "• Social presence & authenticity\n"
        "• Organic vs artificial hype detection\n"
        "• Meme strength & cult potential\n"
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
        "📡 *Data Sources:*\n"
        "• Helius RPC — on-chain data\n"
        "• DexScreener — market data\n"
        "• RugCheck — contract risk\n"
        "• Birdeye — wallet intelligence\n\n"
        "🚀 *$FLASH Ecosystem:*\n"
        f"• Web Scanner: {REPORT_URL}\n"
        f"• Community: {TG_CHANNEL}\n"
        f"• X: {X_URL}\n\n"
        "_Phase 1 of Solar Flash infrastructure._\n"
        "_Solar Dashboard & Rug Detector coming soon._",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )
