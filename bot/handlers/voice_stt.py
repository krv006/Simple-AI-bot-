# bot/handlers/voice_stt.py
import logging
from datetime import datetime, timezone
from io import BytesIO

from aiogram import Dispatcher, F
from aiogram.enums import ChatType
from aiogram.types import Message

from bot.ai.stt_uzbekvoice import stt_uzbekvoice
from bot.config import Settings
from bot.storage import get_or_create_session
from bot.utils.amounts import extract_amount_from_text  # <<< YANGI
from bot.utils.phones import extract_phones

logger = logging.getLogger(__name__)


def register_voice_handlers(dp: Dispatcher, settings: Settings) -> None:
    @dp.message(
        F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}),  # faqat guruhlar
        F.voice,
    )
    async def handle_voice_message(message: Message):
        if message.from_user is None or message.from_user.is_bot:
            return

        if not settings.uzbekvoice_api_key:
            await message.answer(
                "STT servisi sozlanmagan (UZBEKVOICE_API_KEY). Admin bilan bog‘laning."
            )
            return

        try:
            # 1. Voice faylni olish
            file_info = await message.bot.get_file(message.voice.file_id)
            file_path = file_info.file_path

            bio = BytesIO()
            await message.bot.download_file(file_path, bio)
            bio.seek(0)
            file_bytes = bio.read()

            # 2. Uzbekvoice STT
            text = await stt_uzbekvoice(
                file_bytes=file_bytes,
                api_key=settings.uzbekvoice_api_key,
                language="uz",
            )

            if not text:
                await message.answer(
                    "Golosni matnga o‘girishda xatolik bo‘ldi, keyinroq yana urinib ko‘ring."
                )
                return

            logger.info("STT text: %r", text)
            print(text)

            # 3. Order sessiyasiga ulash
            session = get_or_create_session(settings, message)

            if text:
                session.raw_messages.append(text)

            # Telefonlarni ajratib, session.phones ga qo‘shamiz
            phones_in_msg = extract_phones(text)
            for p in phones_in_msg:
                session.phones.add(p)

            session.updated_at = datetime.now(timezone.utc)

            # 4. SUMMA ni chiqarib olamiz
            amount = extract_amount_from_text(text)
            if amount:
                # Agar session structurasida amount degan maydon bo'lsa, shu yerga qo'yishingiz mumkin:
                # session.amount = amount
                logger.info("Extracted amount from STT: %s", amount)

            # 5. Matn + summa haqida foydalanuvchiga ko'rsatish
            reply_text = f"🎤 Golosdan olingan matn:\n\n{text}"
            if amount:
                reply_text += f"\n\n💰 Summa: {amount:,} so'm"

            await message.answer(reply_text)

            # 6. Summa/telefon bo‘lsa va location yo‘q bo‘lsa – location so‘raymiz
            low = text.lower()
            has_digits = any(ch.isdigit() for ch in text)
            money_kw = [
                "summa",
                "ming",
                "min",
                "мин",
                "минг",
                "сум",
                "сом",
                "тыс",
                "so'm",
                "som",
            ]
            has_money_kw = any(kw in low for kw in money_kw)
            has_amount_candidate = has_digits or has_money_kw or bool(amount)

            logger.info(
                "Voice session updated: phones=%s, location=%s, has_amount_candidate=%s",
                session.phones,
                session.location,
                has_amount_candidate,
            )

            if has_amount_candidate and session.location is None:
                await message.answer(
                    "✅ Zakaz ma'lumotlari qabul qilindi (telefon/summa).\n"
                    "📍 Iltimos, endi manzilni location ko‘rinishida yuboring."
                )

        except Exception as e:
            logger.exception("Error while processing voice message: %s", e)
            await message.answer("Golosni qayta ishlashda kutilmagan xatolik yuz berdi.")
