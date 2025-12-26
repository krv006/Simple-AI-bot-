# bot/handlers/order_finalize.py
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, List

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

from bot.ai.voice_order_structured import extract_order_structured
from .ai_check_logger import send_ai_check_log
from .order_utils import build_final_texts, append_dataset_line
from ..config import Settings
from ..db import save_order_row
from ..order_dataset_db import save_order_dataset_row
from ..storage import finalize_session, save_order_to_json
# MUHIM: phones output enforce
from ..utils.phones import normalize_phone_list_strict, ensure_phone_suffix

logger = logging.getLogger(__name__)


async def auto_remove_cancel_keyboard(order_message: Message, delay: int = 30):
    await asyncio.sleep(delay)
    try:
        await order_message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest as e:
        logger.warning("Failed to auto-remove inline keyboard: %s", e)


def _clean_products_with_structured(
        raw_lines: List[str],
        phones: List[str],
        amount: Optional[int],
        client_name: Optional[str],
) -> List[str]:
    cleaned: List[str] = []

    phone_suffixes: List[str] = []
    for p in phones:
        digits = "".join(ch for ch in (p or "") if ch.isdigit())
        if len(digits) >= 7:
            phone_suffixes.append(digits[-7:])

    amount_digits = None
    if amount is not None:
        amount_digits = "".join(ch for ch in str(amount) if ch.isdigit())

    for line in raw_lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        digits_in_line = "".join(ch for ch in line_stripped if ch.isdigit())
        skip = False

        if digits_in_line:
            for suf in phone_suffixes:
                if suf and suf in digits_in_line:
                    skip = True
                    break

        if not skip and amount_digits and amount_digits in digits_in_line:
            skip = True

        if (
                not skip
                and client_name
                and line_stripped.lower().startswith(client_name.lower())
        ):
            skip = True

        if skip:
            continue

        cleaned.append(line_stripped)

    return cleaned


async def finalize_and_send_after_delay(
        key: str,
        base_message: Message,
        settings: Settings,
):
    await asyncio.sleep(5)

    finalized = finalize_session(key)
    logger.info("Delayed finalize for key=%s, finalized=%s", key, bool(finalized))
    if not finalized:
        return

    chat_title = base_message.chat.title or "Noma'lum guruh"
    user = base_message.from_user
    full_name = user.full_name if user and user.full_name else f"id={user.id}"

    client_phones, final_products, final_comments = build_final_texts(
        finalized.raw_messages, finalized.phones
    )

    text_for_ai = "\n".join(finalized.raw_messages).strip()

    # candidates (lekin endi prompt-first bo'lsin desangiz bo'sh ham berishingiz mumkin)
    raw_phone_candidates = list(finalized.phones) if finalized.phones else client_phones
    raw_amount_candidates: list[int] = []
    session_amount = getattr(finalized, "amount", None)
    if session_amount is not None:
        raw_amount_candidates.append(session_amount)

    struct = None
    client_name_parsed: Optional[str] = None
    final_amount: Optional[int] = session_amount

    try:
        struct = extract_order_structured(
            settings,
            text=text_for_ai,
            raw_phone_candidates=raw_phone_candidates,
            raw_amount_candidates=raw_amount_candidates,
        )
        logger.info("Structured order result in finalize: %s", struct.json())
    except Exception as e:
        logger.exception("Failed to run structured order extraction in finalize: %s", e)
        struct = None

    # =========================
    # APPLY STRUCTURED RESULT
    # =========================
    if struct is not None and getattr(struct, "is_order", False):
        if getattr(struct, "phone_numbers", None):
            # LLM phones -> strict normalize (+998...) and unique
            normalized = normalize_phone_list_strict(struct.phone_numbers)
            if normalized:
                client_phones = normalized

        if getattr(struct, "amount", None) is not None:
            final_amount = struct.amount

        client_name_parsed = (
                getattr(struct, "customer_name", None)
                or getattr(struct, "client_name", None)
                or None
        )

        if getattr(struct, "comment", None):
            final_comments = [struct.comment]

    # =========================
    # OUTPUT FORMAT ENFORCE
    # phones_out: +998...--
    # =========================
    phones_out = ensure_phone_suffix(client_phones)
    phones_str = ", ".join(phones_out) if phones_out else "—"
    comment_str = "\n".join(final_comments) if final_comments else "—"

    raw_lines = text_for_ai.splitlines()
    cleaned_product_lines = _clean_products_with_structured(
        raw_lines=raw_lines,
        phones=client_phones,  # ichki (suffixsiz) bilan tozalaymiz
        amount=final_amount,
        client_name=client_name_parsed,
    )
    products_str = "\n".join(cleaned_product_lines) if cleaned_product_lines else "—"

    loc = finalized.location
    if loc:
        if loc.get("type") == "telegram":
            lat = loc.get("lat")
            lon = loc.get("lon")
            loc_str = f"Telegram location\nhttps://maps.google.com/?q={lat},{lon}"
        else:
            raw_loc = loc.get("raw") or ""
            loc_type = loc.get("type", "custom")
            loc_str = f"{loc_type} location: {raw_loc}"
    else:
        loc_str = "—"

    amount = final_amount
    if amount is not None:
        amount_str = f"{amount:,}".replace(",", " ")
        amount_line = f"💰 Summa: {amount_str} so'm"
    else:
        amount_line = "💰 Summa: —"

    # AI_CHECK log
    try:
        final_ai_result = {
            "role": "ORDER",
            "has_address_keywords": bool(loc),
            "is_order_related": True,
            "reason": "Finalized order (session ready).",
            "order_probability": 1.0,
            "source": "FINAL",
            "amount": amount,
        }
        await send_ai_check_log(
            settings=settings,
            message=base_message,
            text=text_for_ai,
            ai_result=final_ai_result,
        )
    except Exception as e:
        logger.error("Failed to send AI_CHECK log in finalize: %s", e)

    # ai_orders ga yozish
    order_id: Optional[int] = None
    try:
        # DBga suffixsiz yozamiz (barqarorlik uchun)
        order_id = save_order_row(
            settings=settings,
            message=base_message,
            phones=client_phones,  # suffixsiz
            order_text=products_str,
            location=finalized.location,
            amount=amount,
        )
    except Exception as e:
        logger.error("Failed to save order to Postgres: %s", e)

    # ai_order_dataset ga yozish
    try:
        if order_id is not None:
            messages = list(finalized.raw_messages) if finalized.raw_messages else []
            save_order_dataset_row(
                settings=settings,
                order_id=order_id,
                base_message=base_message,
                messages=messages,
                phones=client_phones,  # suffixsiz
                location=finalized.location,
                amount=amount,
            )
            logger.info("Order dataset saved: order_id=%s, messages_count=%s", order_id, len(messages))
    except Exception as e:
        logger.error("Failed to save order dataset row for order_id=%s: %s", order_id, e)

    header_line = "🆕 Yangi zakaz"
    if order_id is not None:
        header_line += f" (ID: {order_id})"

    if client_name_parsed:
        client_line = f"👤 Mijoz: {client_name_parsed} (tg: {full_name}, id: {user.id})"
    else:
        client_line = f"👤 Mijoz: {full_name} (id: {user.id})"

    msg_text = (
        f"{header_line}\n"
        f"👥 Guruhdan: {chat_title}\n"
        f"{client_line}\n\n"
        f"📞 Telefon(lar): {phones_str}\n"
        f"{amount_line}\n"
        f"📍 Manzil: {loc_str}\n"
        f"💬 Izoh/comment:\n{comment_str}\n\n"
        f"☕️ Mahsulot/zakaz matni:\n{products_str}"
    )

    try:
        save_order_to_json(finalized)
    except Exception as e:
        logger.warning("Failed to save order JSON backup: %s", e)

    logger.info("Order saved to ai_bot.json for key=%s", key)

    try:
        append_dataset_line(
            "order.txt",
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "order",
                "order_id": order_id,
                "chat_id": base_message.chat.id,
                "chat_title": chat_title,
                "user_id": user.id,
                "user_name": full_name,
                "phones": client_phones,  # suffixsiz dataset
                "phones_out": phones_out,  # xohlasangiz ko'rish uchun
                "location": finalized.location,
                "raw_messages": finalized.raw_messages,
                "amount": amount,
                "client_name": client_name_parsed,
            },
        )
    except Exception as e:
        logger.warning("Failed to append orders_dataset.txt for order_id=%s: %s", order_id, e)

    reply_markup = None
    if order_id is not None:
        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Buyurtmani bekor qilish",
                        callback_data=f"cancel_order:{order_id}",
                    )
                ]
            ]
        )

    target_chat_ids = list(settings.send_group_ids) if settings.send_group_ids else [base_message.chat.id]
    logger.info("Sending order to target groups=%s", target_chat_ids)

    sent_msgs: list[Message] = []

    for target_chat_id in target_chat_ids:
        try:
            sent_msg = await base_message.bot.send_message(
                target_chat_id,
                msg_text,
                reply_markup=reply_markup,
            )
            sent_msgs.append(sent_msg)
        except TelegramBadRequest as e:
            logger.error(
                "Failed to send order to target_chat_id=%s: %s. Falling back to source chat_id=%s",
                target_chat_id, e, base_message.chat.id
            )
            try:
                fallback_msg = await base_message.answer(msg_text, reply_markup=reply_markup)
                sent_msgs.append(fallback_msg)
            except Exception as e2:
                logger.error("Fallback send also failed: %s", e2)

    if reply_markup is not None:
        for m in sent_msgs:
            asyncio.create_task(auto_remove_cancel_keyboard(m, delay=30))
