# bot/handlers/ai_check_logger.py
import logging
from datetime import datetime, timezone

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from bot.config import Settings
from bot.db import save_ai_check_row
from .order_utils import append_dataset_line

logger = logging.getLogger(__name__)


async def send_ai_check_log(
        settings: Settings,
        message: Message,
        text: str,
        ai_result: dict,
) -> None:
    """
    AI_CHECK guruhiga debug xabar yuborish,
    ai_check.txt faylga yozish va ai_check_logs jadvaliga saqlash.
    """
    ai_result = ai_result or {}

    role = ai_result.get("role", "UNKNOWN")
    has_addr_kw = ai_result.get("has_address_keywords", False)
    is_order_related = ai_result.get("is_order_related", False)
    reason = ai_result.get("reason") or ""
    order_prob = ai_result.get("order_probability", None)
    source = ai_result.get("source", "UNKNOWN")
    amount = ai_result.get("amount")

    src_chat_title = message.chat.title or str(message.chat.id)
    user = message.from_user

    if user:
        full_name = user.full_name or f"id={user.id}"
        user_id = user.id
    else:
        full_name = "unknown"
        user_id = None

    is_order_txt = "Ha" if is_order_related else "Yo'q"
    has_addr_txt = "Ha" if has_addr_kw else "Yo'q"

    debug_text = (
        "🤖 AI CHECK\n"
        f"👥 Guruh: {src_chat_title}\n"
        f"👤 User: {full_name} (id: {user_id})\n\n"
        f"📩 Xabar:\n{text}\n\n"
        "AI natijasi:\n"
        f"- orderga aloqador: {is_order_txt}\n"
        f"- role: {role}\n"
        f"- manzil kalit so'zlari: {has_addr_txt}\n"
        f"- manba: {source}\n"
    )

    if isinstance(order_prob, (int, float)):
        debug_text += f"- order ehtimoli: {order_prob:.2f}\n"

    if amount is not None:
        debug_text += f"- AI summa: {amount}\n"

    if reason:
        debug_text += f"\nSabab:\n{reason}"

    # 1) AI_CHECK guruhiga yuborish (agar sozlangan bo'lsa)
    if settings.ai_check_group_id:
        try:
            await message.bot.send_message(settings.ai_check_group_id, debug_text)
        except TelegramBadRequest as e:
            logger.error(
                "Failed to send AI_CHECK log to ai_check_group_id=%s: %s",
                settings.ai_check_group_id,
                e,
            )

    # 2) Faylga dataset yozish
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "chat_id": message.chat.id,
        "chat_title": src_chat_title,
        "user_id": user_id,
        "user_name": full_name,
        "text": text,
        "ai": {
            "is_order_related": is_order_related,
            "role": role,
            "has_address_keywords": has_addr_kw,
            "reason": reason,
            "order_probability": order_prob,
            "source": source,
            "amount": amount,
        },
    }
    append_dataset_line("ai_check.txt", payload)

    try:
        save_ai_check_row(
            settings=settings,
            message=message,
            text=text,
            ai_result=payload["ai"],
        )
    except Exception as e:
        logger.error("Failed to save AI_CHECK row to DB: %s", e)
