# main.py
import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import load_settings
from bot.handlers import register_all_handlers


async def main():
    # Terminal uchun loglar
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = load_settings()

    bot = Bot(token=settings.tg_bot_token)
    dp = Dispatcher()

    register_all_handlers(dp, settings)

    logging.info("Bot ishga tushyapti...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
