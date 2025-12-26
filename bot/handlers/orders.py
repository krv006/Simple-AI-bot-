# bot/handlers/order.py
import asyncio
import logging
from datetime import datetime, timezone
from io import BytesIO

from aiogram import Dispatcher, F
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from bot.ai.status_intent import is_status_question
from bot.services.stt_uzbekvoice import stt_uzbekvoice
from bot.utils.read_file import read_text_file
from .error_logger import send_non_order_error
from .order_finalize import finalize_and_send_after_delay
from .order_manual import start_manual_order_after_cancel
from .order_reply_update import handle_order_reply_update
from .order_utils import (
    COMMENT_KEYWORDS,
    append_dataset_line,
    make_timestamp,
)
from ..ai.classifier import classify_text_ai
from ..ai.voice_order_structured import (
    extract_order_structured,
    VoiceOrderExtraction,
)
from ..config import Settings
from ..db import cancel_order_row, save_voice_stt_row
from ..storage import (
    get_or_create_session,
    get_session_key,
    is_session_ready,
)
from ..utils.locations import extract_location_from_message
# MUHIM: phones util'lar
from ..utils.phones import (
    extract_phones,  # voice/fallback uchun qolsin
    normalize_phone_list_strict,  # LLM phones -> +998 format
)

logger = logging.getLogger(__name__)


def register_order_handlers(dp: Dispatcher, settings: Settings) -> None:
    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        await message.answer(
            "Assalomu alaykum!\n"
            "Men AI asosida zakaz xabarlarini yig'ib beradigan botman.\n"
            "Meni guruhga qo'shing va mijoz xabarlarini yuboring."
        )

    @dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
    async def handle_group_message(message: Message):
        if message.from_user is None or message.from_user.is_bot:
            return

        # 1) Reply update logika
        if message.reply_to_message:
            handled = await handle_order_reply_update(message, settings)
            if handled:
                return

        text: str = ""
        stt_text_for_dataset: str | None = None
        voice_ai_result: VoiceOrderExtraction | None = None

        # =========================
        # VOICE (qolsin) / TEXT
        # =========================
        if message.voice:
            if not settings.uzbekvoice_api_key:
                await message.reply(
                    "Golosni o‘qish servisi sozlanmagan (UZBEKVOICE_API_KEY). Admin bilan bog‘laning."
                )
                return

            try:
                file_info = await message.bot.get_file(message.voice.file_id)
                file_path = file_info.file_path

                bio = BytesIO()
                await message.bot.download_file(file_path, bio)
                bio.seek(0)
                file_bytes = bio.read()

                stt_text = await stt_uzbekvoice(
                    file_bytes=file_bytes,
                    api_key=settings.uzbekvoice_api_key,
                    language="uz",
                )

                if stt_text:
                    text = stt_text
                    stt_text_for_dataset = stt_text
                else:
                    text = message.caption or ""
                    if not text.strip():
                        await message.reply(
                            "Golosni matnga o‘girishda xatolik bo‘ldi, keyinroq qayta urinib ko‘ring."
                        )
                        return

                # Voice structured (hozircha rule-based candidates bilan)
                try:
                    raw_phones_voice = extract_phones(text)
                    raw_amount_candidates: list[int] = []

                    voice_ai_result = extract_order_structured(
                        settings,
                        text=text,
                        raw_phone_candidates=raw_phones_voice,
                        raw_amount_candidates=raw_amount_candidates,
                    )
                    logger.info("Voice structured AI result: %s", voice_ai_result)
                except Exception as e:
                    logger.exception("Voice structured extraction error: %s", e)
                    voice_ai_result = None

            except Exception as e:
                logger.exception("Error while processing voice STT: %s", e)
                await message.reply("Golosni qayta ishlashda kutilmagan xatolik yuz berdi.")
                return
        else:
            text = message.text or message.caption or ""

        logger.info(
            "New group msg chat=%s(%s) from=%s(%s) text=%r location=%s voice=%s",
            message.chat.id,
            message.chat.title,
            message.from_user.id,
            message.from_user.full_name,
            text,
            bool(message.location),
            bool(message.voice),
        )

        # Session
        session = get_or_create_session(settings, message)
        key = get_session_key(message)

        if session.is_completed:
            logger.info("Session already completed for key=%s, skipping.", key)
            return

        if text:
            session.raw_messages.append(text)

        # =========================
        # PHONES/AMOUNT: TEXT => PROMPT FIRST
        # =========================
        had_phones_before = bool(session.phones)

        if not message.voice:
            # TEXT pipeline: phones/amount faqat LLM/prompt orqali
            try:
                text_for_ai = "\n".join(session.raw_messages).strip()
                struct = extract_order_structured(
                    settings,
                    text=text_for_ai,
                    raw_phone_candidates=[],  # MUHIM: bo'sh
                    raw_amount_candidates=[],  # MUHIM: bo'sh
                )

                if struct is not None and getattr(struct, "is_order", False):
                    # phones
                    if getattr(struct, "phone_numbers", None):
                        normalized = normalize_phone_list_strict(struct.phone_numbers)
                        for p in normalized:
                            session.phones.add(p)

                    # amount
                    if getattr(struct, "amount", None) is not None:
                        if getattr(session, "amount", None) in (None, 0):
                            session.amount = int(struct.amount)

                logger.info("TEXT structured result: %s", getattr(struct, "json", lambda: struct)())

            except Exception as e:
                # TEXT'da prompt ishlamasa: sessiyani buzmaymiz, faqat log
                logger.exception("TEXT structured extraction failed: %s", e)

        else:
            # Voice oqimi (qolsin): siz hozir text dediysiz, lekin buzmaymiz
            phones_in_msg = extract_phones(text)
            for p in phones_in_msg:
                session.phones.add(p)

            if voice_ai_result is not None and voice_ai_result.phone_numbers:
                # voice_ai_result ham LLM bo'lishi mumkin, normalize qilamiz
                normalized = normalize_phone_list_strict(voice_ai_result.phone_numbers)
                for p in normalized:
                    session.phones.add(p)

            if voice_ai_result is not None and voice_ai_result.amount is not None:
                if getattr(session, "amount", None) in (None, 0):
                    session.amount = int(voice_ai_result.amount)

        phones_new = bool(session.phones) and not had_phones_before

        # =========================
        # LOCATION
        # =========================
        had_location_before = session.location is not None
        loc = extract_location_from_message(message)
        just_got_location = False
        if loc:
            session.location = loc
            if not had_location_before:
                just_got_location = True

        logger.info("Current session phones=%s", session.phones)
        logger.info("Current session location=%s", session.location)

        # Voice’dan keyin location so‘rash (qolsin)
        if message.voice and session.phones and session.location is None:
            try:
                await message.reply(
                    "✅ Zakaz ma'lumotlari qabul qilindi.\n"
                    "📍 Iltimos, endi manzilni location ko‘rinishida yuboring."
                )
            except TelegramBadRequest:
                pass

        # =========================
        # CLASSIFIER (qolsin)
        # =========================
        ai_result = await classify_text_ai(settings, text, session.raw_messages)

        role = ai_result.get("role", "UNKNOWN")
        has_addr_kw = ai_result.get("has_address_keywords", False)
        is_order_related = ai_result.get("is_order_related", False)

        logger.info("AI result (classifier)=%s", ai_result)

        # Voice STT DB (qolsin)
        if message.voice:
            try:
                save_voice_stt_row(
                    settings=settings,
                    message=message,
                    text=text,
                    phones=list(session.phones) if session.phones else None,
                    amount=getattr(session, "amount", None),
                )
            except Exception as e:
                logger.error("Failed to save voice STT row: %s", e)

            try:
                append_dataset_line(
                    "data/voice_orders_dataset.jsonl",
                    {
                        "ts": make_timestamp(),
                        "source": "voice",
                        "chat_id": message.chat.id,
                        "user_id": message.from_user.id if message.from_user else None,
                        "raw_text": stt_text_for_dataset or text,
                        "true_phones": list(session.phones),
                        "true_amount": getattr(session, "amount", None),
                        "true_address": None,
                        "comment": getattr(voice_ai_result, "comment", None) if voice_ai_result else None,
                    },
                )
            except Exception as e:
                logger.error("Failed to append voice dataset line: %s", e)

        # =========================
        # STATUS question
        # =========================
        if not message.location and (text or "").strip():
            is_status = await is_status_question(settings, text, session.raw_messages)
            logger.info("Status intent: text=%r -> is_status=%s", text, is_status)
            if is_status:
                status_text = read_text_file("bot/a.txt")
                await message.reply(status_text)
                return

        # =========================
        # Old fallback role hints (qolsin)
        # =========================
        low = (text or "").lower()
        has_digits = any(ch.isdigit() for ch in (text or ""))
        money_kw = ["summa", "ming", "min", "мин", "минг", "сум", "сом", "тыс"]
        has_product_candidate = bool(has_digits or any(kw in low for kw in money_kw))

        if role == "UNKNOWN":
            if has_product_candidate:
                role = "PRODUCT"
            if any(kw in low for kw in COMMENT_KEYWORDS):
                role = "COMMENT"

        # NON-ORDER log
        if (not is_order_related and not message.location and (text or "").strip()):
            # Eslatma: endi phones_in_msg yo'q (textda), shuning uchun bu shart yengillashadi
            await send_non_order_error(settings=settings, message=message, text=text)
            return

        session.updated_at = datetime.now(timezone.utc)

        # Sessiya bo‘yicha summa kandidati bor-yo‘qligi
        all_text = " ".join(session.raw_messages).lower()
        has_digits_all = any(ch.isdigit() for ch in all_text)
        money_kw_all = ["summa", "ming", "min", "мин", "минг", "сум", "сом", "тыс", "so'm", "som"]
        has_money_kw_all = any(kw in all_text for kw in money_kw_all)
        has_amount_candidate_all = has_digits_all or has_money_kw_all or (
                    getattr(session, "amount", None) not in (None, 0))

        ready_base = is_session_ready(session)
        ready = ready_base or (session.location is not None and has_amount_candidate_all)

        logger.info(
            "Session ready=%s (base=%s) | is_completed=%s | just_got_location=%s | "
            "phones_new=%s | has_product_candidate=%s | has_amount_candidate_all=%s",
            ready,
            ready_base,
            session.is_completed,
            just_got_location,
            phones_new,
            has_product_candidate,
            has_amount_candidate_all,
        )

        if not ready or session.is_completed:
            return

        should_finalize = (
                just_got_location
                or role == "PRODUCT"
                or has_addr_kw
                or phones_new
                or has_product_candidate
                or has_amount_candidate_all
        )

        if not should_finalize:
            logger.info("Session is ready, but current message is not a finalize trigger.")
            return

        asyncio.create_task(
            finalize_and_send_after_delay(
                key=key,
                base_message=message,
                settings=settings,
            )
        )
        logger.info("Finalize scheduled with 5s delay for key=%s", key)
        return

    @dp.callback_query(F.data.startswith("cancel_order:"))
    async def handle_cancel_order(callback: CallbackQuery):
        data = callback.data or ""
        try:
            _, raw_id = data.split(":", 1)
            order_id = int(raw_id)
        except Exception:
            await callback.answer("Noto'g'ri buyurtma ID.", show_alert=True)
            return

        try:
            cancelled = cancel_order_row(settings=settings, order_id=order_id)
        except Exception as e:
            logger.error("Failed to cancel order_id=%s: %s", order_id, e)
            await callback.answer("Bekor qilishda xatolik yuz berdi.", show_alert=True)
            return

        if not cancelled:
            await callback.answer(
                "Bu buyurtma allaqachon bekor qilingan yoki topilmadi.",
                show_alert=True,
            )
            return

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            pass

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Ha, yangi zakaz",
                        callback_data=f"new_after_cancel_yes:{order_id}",
                    ),
                    InlineKeyboardButton(
                        text="❌ Yo'q",
                        callback_data=f"new_after_cancel_no:{order_id}",
                    ),
                ]
            ]
        )

        try:
            await callback.message.reply(
                "❌ Buyurtma bekor qilindi.\nYangi buyurtma yaratishni xohlaysizmi?",
                reply_markup=kb,
            )
        except TelegramBadRequest:
            pass

        await callback.answer()

    @dp.callback_query(F.data.startswith("new_after_cancel_no:"))
    async def handle_new_after_cancel_no(callback: CallbackQuery):
        await callback.answer()
        try:
            await callback.message.reply("Yaxshi, ishlaringizga omad!")
        except TelegramBadRequest:
            pass

    @dp.callback_query(F.data.startswith("new_after_cancel_yes:"))
    async def handle_new_after_cancel_yes(callback: CallbackQuery):
        data = callback.data or ""
        try:
            _, raw_id = data.split(":", 1)
            from_order_id = int(raw_id)
        except Exception:
            from_order_id = None

        await callback.answer()
        await start_manual_order_after_cancel(callback, from_order_id)
