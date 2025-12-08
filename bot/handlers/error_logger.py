# bot/handlers/error_logger.py
import logging
from datetime import datetime, timezone

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

from bot.config import Settings
from bot.db import save_error_row
from .order_utils import append_dataset_line

logger = logging.getLogger(__name__)


async def send_non_order_error(
        settings: Settings,
        message: Message,
        text: str,
) -> None:
    """
    Orderga aloqador bo'lmagan xabarlarni:
      - error guruhiga yuborish (agar sozlangan bo'lsa),
      - errors.txt fayliga yozish,
      - ai_error_logs jadvaliga saqlash.
    """
    src_chat_title = message.chat.title or str(message.chat.id)
    user = message.from_user

    if user:
        full_name = user.full_name or f"id={user.id}"
        user_id = user.id
    else:
        full_name = "unknown"
        user_id = None

    error_text = (
        f"👥 Guruh: {src_chat_title}\n"
        f"👤 User: {full_name} (id: {user_id})\n\n"
        f"📩 Xabar:\n{text}"
    )

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "error",
        "chat_id": message.chat.id,
        "chat_title": src_chat_title,
        "user_id": user_id,
        "user_name": full_name,
        "text": text,
    }

    append_dataset_line("errors.txt", payload)

    try:
        save_error_row(
            settings=settings,
            message=message,
            text=text,
        )
    except Exception as e:
        logger.error("Failed to save error row to DB: %s", e)

    if settings.error_group_id:
        try:
            await message.bot.send_message(
                settings.error_group_id,
                error_text,
            )
        except TelegramBadRequest as e:
            logger.error(
                "Failed to send non-order message to error_group_id=%s: %s",
                settings.error_group_id,
                e,
            )
