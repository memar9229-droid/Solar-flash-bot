import re
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

from config import BOT_TOKEN
from handlers.commands import cmd_start, cmd_help, cmd_about
from handlers.analyze import run_analysis

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

SOL_RE = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")

async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "Usage: `/analyze <token_address>`",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    mint = ctx.args[0].strip()
    if not SOL_RE.fullmatch(mint):
        await update.message.reply_text("Invalid address.")
        return
    await run_analysis(mint, full=True, update=update)

async def cmd_score(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: `/score <token_address>`")
        return
    mint = ctx.args[0].strip()
    await run_analysis(mint, full=False, update=update)

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    match = SOL_RE.search(text)
    if match:
        await run_analysis(match.group(), full=True, update=update)
    else:
        await update.message.reply_text(
            "Paste a Solana token address to scan.\n\n"
            "Example:\n`DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`",
            parse_mode=ParseMode.MARKDOWN
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CommandHandler("about",   cmd_about))
    app.add_handler(CommandHandler("analyze", cmd_analyze))
    app.add_handler(CommandHandler("score",   cmd_score))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_message
    ))
    log.info("Solar Signal Bot is live...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
