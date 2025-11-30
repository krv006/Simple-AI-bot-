# bot/handlers/order.py
import asyncio
import logging
from datetime import datetime, timezone

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

from .order_finalize import finalize_and_send_after_delay, auto_remove_cancel_keyboard
from .order_utils import (
    COMMENT_KEYWORDS,
    append_dataset_line,
    parse_order_message_text,
)
from ..ai.classifier import classify_text_ai
from ..config import Settings
from ..db import cancel_order_row, save_order_row
from ..storage import (
    get_or_create_session,
    get_session_key,
    is_session_ready,
)
from ..utils.locations import extract_location_from_message
from ..utils.phones import extract_phones

logger = logging.getLogger(__name__)


def register_order_handlers(dp: Dispatcher, settings: Settings) -> None:
    async def handle_order_reply_update(message: Message) -> bool:
        """
        Buyurtma xabariga reply qilingan xabarni qayta ishlash.
        Hozircha:
        - lokatsiya o'zgarsa
        - telefon raqam(lar) o'zgarsa
        eski buyurtmani BEKOR qilamiz va yangisini yaratamiz.
        """
        reply_msg = message.reply_to_message
        if not reply_msg or not reply_msg.text:
            return False

        # Faqat zakaz xabarlariga ishlasin:
        if not reply_msg.text.startswith("🆕 Yangi zakaz"):
            return False

        parsed = parse_order_message_text(reply_msg.text)
        if not parsed:
            return False

        order_id = parsed["order_id"]
        if not order_id:
            return False

        old_phones = parsed["phones"] or []
        old_location_text = parsed.get("location_text")

        # Reply xabardan yangi lokatsiya va yangi telefonlarni o'qiymiz
        new_loc = extract_location_from_message(message)
        reply_text = message.text or message.caption or ""
        reply_phones = extract_phones(reply_text)

        # Telefon farqini aniqlash
        old_phones_set = set(old_phones)
        reply_phones_set = set(reply_phones)

        phones_changed = bool(reply_phones_set) and (reply_phones_set != old_phones_set)
        has_new_loc = bool(new_loc)

        # Agar na lokatsiya, na telefon o'zgarmasa – update logika ishlamaydi
        if not has_new_loc and not phones_changed:
            return False

        logger.info(
            "Order reply update detected: order_id=%s, new_loc=%s, phones_changed=%s",
            order_id,
            new_loc,
            phones_changed,
        )

        # 1) Eski orderni DB da bekor qilish
        try:
            cancelled = cancel_order_row(settings=settings, order_id=order_id)
        except Exception as e:
            logger.error("Failed to cancel order_id=%s on update: %s", order_id, e)
            await message.reply(
                "Eski buyurtmani bekor qilishda xatolik yuz berdi."
            )
            return True

        if not cancelled:
            await message.reply(
                "Eski buyurtma topilmadi yoki allaqachon bekor qilingan."
            )
            return True

        # Eski xabarni vizual belgilab qo'yamiz
        reason_parts = []
        if has_new_loc:
            reason_parts.append("lokatsiya o‘zgartirildi")
        if phones_changed:
            reason_parts.append("telefon raqami(lar) o‘zgartirildi")

        reason_text = ", ".join(reason_parts) if reason_parts else "ma'lumotlar yangilandi"

        try:
            await reply_msg.edit_text(
                reply_msg.text
                + f"\n\n❌ Buyurtma bekor qilingan ({reason_text})."
            )
        except TelegramBadRequest:
            pass

        # 2) Eski xabardan product/comment va boshqa maydonlarni olib qolamiz
        products_str = parsed["products"] or ""
        comments_str = parsed["comments"] or ""
        chat_title = parsed["chat_title"]
        client_name = parsed["client_name"]
        client_id = parsed["client_id"]

        # Yangi telefonlar: agar replyda farqli ro'yxat bo'lsa – shuni olamiz
        if phones_changed:
            phones = sorted(reply_phones_set)
        else:
            phones = old_phones

        phones_str = ", ".join(phones) if phones else "—"
        comment_str = comments_str or "—"

        # 3) Yangi lokatsiya matni va DB ga tushadigan location dict
        if has_new_loc:
            loc = new_loc
            if loc["type"] == "telegram":
                lat = loc["lat"]
                lon = loc["lon"]
                loc_str = f"Telegram location\nhttps://maps.google.com/?q={lat},{lon}"
            else:
                raw_loc = loc["raw"] or ""
                loc_str = f"{loc['type']} location: {raw_loc}"
        else:
            # Eski matndagi manzilni qayta ishlatamiz (tekst ko‘rinishida)
            if old_location_text and old_location_text != "—":
                loc_str = old_location_text
                loc = {
                    "type": "text",
                    "raw": old_location_text,
                }
            else:
                loc_str = "—"
                loc = None

        # 4) Yangi buyurtmani DB ga yozamiz
        new_order_id = None
        try:
            new_order_id = save_order_row(
                settings=settings,
                message=message,  # update so'ragan foydalanuvchi sifatida yozamiz
                phones=phones,
                order_text=products_str,
                location=loc,
            )
        except Exception as e:
            logger.error("Failed to save updated order to Postgres: %s", e)
            await message.reply(
                "Yangilangan ma'lumotlar bilan buyurtmani saqlashda xato bo‘ldi."
            )
            return True

        header_line = "🆕 Yangi zakaz (yangilangan)"
        if new_order_id is not None:
            header_line += f" (ID: {new_order_id})"

        # Agar eski xabardan mijozni o‘qib olgan bo‘lsak – o‘shanini ishlatamiz
        if client_name and client_id:
            client_line = f"👤 Mijoz: {client_name} (id: {client_id})"
        else:
            user = message.from_user
            full_name = (
                user.full_name if user and user.full_name else f"id={user.id}"
            )
            client_line = f"👤 Mijoz: {full_name} (id: {user.id})"

        msg_text = (
            f"{header_line}\n"
            f"👥 Guruhdan: {chat_title or (message.chat.title or "Noma'lum guruh")}\n"
            f"{client_line}\n\n"
            f"📞 Telefon(lar): {phones_str}\n"
            f"📍 Manzil: {loc_str}\n"
            f"💬 Izoh/comment:\n{comment_str}\n\n"
            f"☕️ Mahsulot/zakaz matni:\n{products_str}"
        )

        reply_markup = None
        if new_order_id is not None:
            reply_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="❌ Buyurtmani bekor qilish",
                            callback_data=f"cancel_order:{new_order_id}",
                        )
                    ]
                ]
            )

        target_chat_id = settings.send_group_id or message.chat.id

        try:
            sent_msg = await message.bot.send_message(
                target_chat_id,
                msg_text,
                reply_markup=reply_markup,
            )
        except TelegramBadRequest as e:
            logger.error(
                "Failed to send updated order to target chat=%s: %s",
                target_chat_id,
                e,
            )
            sent_msg = await message.answer(msg_text, reply_markup=reply_markup)

        if reply_markup is not None:
            asyncio.create_task(
                auto_remove_cancel_keyboard(sent_msg, delay=30)
            )

        # Dataset uchun ham yozib qo'yamiz
        append_dataset_line(
            "order_updates.txt",
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "order_update",
                "old_order_id": order_id,
                "new_order_id": new_order_id,
                "chat_id": message.chat.id,
                "user_id": message.from_user.id if message.from_user else None,
                "location": loc,
                "phones_old": old_phones,
                "phones_new": phones,
                "location_updated": has_new_loc,
                "phones_updated": phones_changed,
            },
        )

        return True

    # /start
    @dp.message(CommandStart())
    async def cmd_start(message: Message):
        await message.answer(
            "Assalomu alaykum!\n"
            "Men AI asosida zakaz xabarlarini yig'ib beradigan botman.\n"
            "Meni guruhga qo'shing va mijoz xabarlarini yuboring."
        )

    # GROUP MESSAGE handler
    @dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
    async def handle_group_message(message: Message):
        if message.from_user is None or message.from_user.is_bot:
            return

        # 0) Avval: agar eski zakaz xabariga reply bo'lsa – update logika (loc + phone)
        if message.reply_to_message:
            handled = await handle_order_reply_update(message)
            if handled:
                return

        text = message.text or message.caption or ""

        logger.info(
            "New group msg chat=%s(%s) from=%s(%s) text=%r location=%s",
            message.chat.id,
            message.chat.title,
            message.from_user.id,
            message.from_user.full_name,
            text,
            bool(message.location),
        )
        print(
            f"[MSG] chat={message.chat.id}({message.chat.title}) "
            f"from={message.from_user.id}({message.from_user.full_name}) "
            f"text={text!r} location={bool(message.location)}"
        )

        session = get_or_create_session(settings, message)
        key = get_session_key(message)

        if session.is_completed:
            logger.info("Session already completed for key=%s, skipping.", key)
            return

        if text:
            session.raw_messages.append(text)

        had_phones_before = bool(session.phones)
        phones_in_msg = extract_phones(text)
        for p in phones_in_msg:
            session.phones.add(p)
        phones_new = bool(session.phones) and not had_phones_before

        had_location_before = session.location is not None
        loc = extract_location_from_message(message)
        just_got_location = False
        if loc:
            session.location = loc
            if not had_location_before:
                just_got_location = True

        logger.info("Current session phones=%s", session.phones)
        logger.info("Current session location=%s", session.location)

        # === AI klassifikatsiya ===
        ai_result = await classify_text_ai(settings, text, session.raw_messages)
        role = ai_result.get("role", "UNKNOWN")
        has_addr_kw = ai_result.get("has_address_keywords", False)
        is_order_related = ai_result.get("is_order_related", False)
        reason = ai_result.get("reason") or ""
        order_prob = ai_result.get("order_probability", None)
        source = ai_result.get("source", "UNKNOWN")

        logger.info("AI result=%s", ai_result)

        # === AI_CHECK GURUHIGA LOG ===
        if settings.ai_check_group_id:
            src_chat_title = message.chat.title or str(message.chat.id)
            user = message.from_user
            full_name = (
                user.full_name if (user and user.full_name) else f"id={user.id}"
            )

            is_order_txt = "Ha" if is_order_related else "Yo'q"
            has_addr_txt = "Ha" if has_addr_kw else "Yo'q"

            debug_text = (
                "🤖 AI CHECK\n"
                f"👥 Guruh: {src_chat_title}\n"
                f"👤 User: {full_name} (id: {user.id})\n\n"
                f"📩 Xabar:\n{text}\n\n"
                "AI natijasi:\n"
                f"- orderga aloqador: {is_order_txt}\n"
                f"- role: {role}\n"
                f"- manzil kalit so'zlari: {has_addr_txt}\n"
                f"- manba: {source}\n"
            )

            if isinstance(order_prob, (int, float)):
                debug_text += f"- order ehtimoli: {order_prob:.2f}\n"

            if reason:
                debug_text += f"\nSabab:\n{reason}"

            try:
                await message.bot.send_message(
                    settings.ai_check_group_id, debug_text
                )
            except TelegramBadRequest as e:
                logger.error(
                    "Failed to send AI_CHECK log to ai_check_group_id=%s: %s",
                    settings.ai_check_group_id,
                    e,
                )

            append_dataset_line(
                "ai_check.txt",
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "chat_id": message.chat.id,
                    "chat_title": src_chat_title,
                    "user_id": user.id,
                    "user_name": full_name,
                    "text": text,
                    "ai": {
                        "is_order_related": is_order_related,
                        "role": role,
                        "has_address_keywords": has_addr_kw,
                        "reason": reason,
                        "order_probability": order_prob,
                        "source": source,
                    },
                },
            )

        # === Eski fallback PRODUCT/COMMENT ===
        low = text.lower()
        has_digits = any(ch.isdigit() for ch in text)
        money_kw = ["summa", "ming", "min", "мин", "минг", "сум", "сом", "тыс"]

        has_product_candidate = bool(
            has_digits or any(kw in low for kw in money_kw)
        )

        if role == "UNKNOWN":
            if has_product_candidate:
                role = "PRODUCT"
            if any(kw in low for kw in COMMENT_KEYWORDS):
                role = "COMMENT"

        # === NON-ORDER error_group ===
        if (
                settings.error_group_id
                and not is_order_related
                and not phones_in_msg
                and not message.location
                and text.strip()
        ):
            src_chat_title = message.chat.title or str(message.chat.id)
            user = message.from_user
            full_name = (
                user.full_name if user and user.full_name else f"id={user.id}"
            )

            error_text = (
                f"👥 Guruh: {src_chat_title}\n"
                f"👤 User: {full_name} (id: {user.id})\n\n"
                f"📩 Xabar:\n{text}"
            )

            append_dataset_line(
                "errors.txt",
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "error",
                    "chat_id": message.chat.id,
                    "chat_title": src_chat_title,
                    "user_id": user.id,
                    "user_name": full_name,
                    "text": text,
                },
            )

            try:
                await message.bot.send_message(
                    settings.error_group_id, error_text
                )
            except TelegramBadRequest as e:
                logger.error(
                    "Failed to send non-order message to error_group_id=%s: %s",
                    settings.error_group_id,
                    e,
                )
            return

        # === Session update ===
        session.updated_at = datetime.now(timezone.utc)

        ready = is_session_ready(session)
        logger.info(
            "Session ready=%s | is_completed=%s | just_got_location=%s | "
            "phones_new=%s | has_product_candidate=%s",
            ready,
            session.is_completed,
            just_got_location,
            phones_new,
            has_product_candidate,
        )

        if not ready or session.is_completed:
            return

        should_finalize = (
                just_got_location
                or role == "PRODUCT"
                or has_addr_kw
                or phones_new
                or has_product_candidate
        )

        if not should_finalize:
            logger.info(
                "Session is ready, but current message is not a finalize trigger."
            )
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

        try:
            await callback.message.reply("❌ Buyurtmangiz bekor qilindi.")
        except TelegramBadRequest:
            pass

        await callback.answer()
