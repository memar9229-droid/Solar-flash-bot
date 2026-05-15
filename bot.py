"""
⊙ SOLAR SIGNAL BOT — by Solar Flash
Elite Solana memecoin intelligence terminal.
"""
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from config import BOT_TOKEN
from handlers import (
    cmd_start, cmd_help, cmd_about,
    cmd_analyze, cmd_score, handle_message
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

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

    log.info("⊙ Solar Signal Bot is live...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
