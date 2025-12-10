# bot/handlers/admin_prompt.py
import html
import json
import logging

from aiogram import Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from ..ai.prompt_optimizer_from_dataset import optimize_prompt_from_dataset
from ..config import Settings

logger = logging.getLogger(__name__)

ADMIN_IDS = {1305675046}
PROMPT_DEBUG_CHAT_ID = -5030824970


def register_admin_prompt_handlers(dp: Dispatcher, settings: Settings) -> None:
    @dp.message(Command("optimize_prompt"), F.from_user.id.in_(ADMIN_IDS))
    async def cmd_optimize_prompt(message: Message):
        logger.info(
            "Admin optimize_prompt: chat=%s from=%s(%s)",
            message.chat.id,
            message.from_user.id,
            message.from_user.username,
        )

        await message.answer("♻️ Prompt optimizatsiya qilinyapti...")

        try:
            # 1) Yangi configni olish
            new_config = optimize_prompt_from_dataset(
                settings=settings,
                limit=300,
            )

            await message.answer("✅ prompt_config.json yangilandi.")

            # 2) Yangi configni debug guruhga yuborish
            try:
                config_str = json.dumps(new_config, ensure_ascii=False, indent=2)

                # Telegram limitidan chiqmaslik uchun biroz kesamiz
                if len(config_str) > 3500:
                    config_str_short = config_str[:3400] + "\n...\n(truncated)"
                else:
                    config_str_short = config_str

                text = (
                        "<b>🧠 Yangi prompt_config.json</b>\n"
                        "<i>(optimizer orqali yangilandi)</i>\n"
                        "<pre>" + html.escape(config_str_short) + "</pre>"
                )

                await message.bot.send_message(
                    chat_id=PROMPT_DEBUG_CHAT_ID,
                    text=text,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.exception("Yangi prompt configni guruhga yuborishda xatolik: %s", e)

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
