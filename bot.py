import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from config import BOT_TOKEN
from handlers_aiogram import register_handlers

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp  = Dispatcher()
    register_handlers(dp)
    print("⊙ Solar Signal Bot is live...")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
