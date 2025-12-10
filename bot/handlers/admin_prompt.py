# bot/handlers/admin_prompt.py
import logging

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from ..ai.prompt_optimizer_from_dataset import optimize_prompt_from_dataset
from ..config import Settings

logger = logging.getLogger(__name__)

ADMIN_IDS = {1305675046}  # o'zingizni telegram id


def register_admin_prompt_handlers(dp: Dispatcher, settings: Settings) -> None:
    @dp.message(Command("optimize_prompt"), F.from_user.id.in_(ADMIN_IDS))
    async def cmd_optimize_prompt(message: Message):
        await message.answer("♻️ Prompt optimizatsiya qilinyapti...")
        try:
            optimize_prompt_from_dataset(
                settings=settings,
                limit=300)

            await message.answer("✅ prompt_config.json yangilandi.")
        except Exception as e:
            logger.exception("Prompt optimizatsiyada xatolik: %s", e)
            short_err = str(e)
            if len(short_err) > 500:
                short_err = short_err[:500] + " ..."
            await message.answer(
                "❌ Prompt optimizatsiyada xatolik yuz berdi.\n"
                "Detal uchun server logini ko'ring.\n\n"
                f"{short_err}"
            )
