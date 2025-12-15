# bot/utils/stt.py
import logging
from io import BytesIO

from aiogram.types import Message

from bot.config import Settings
from bot.services.stt_uzbekvoice import stt_uzbekvoice

logger = logging.getLogger(__name__)


async def transcribe_uzbekvoice_from_message(
    message: Message,
    settings: Settings,
    language: str = "uz",
) -> str:
    """
    Telegram voice -> download -> UzbekVoice STT -> text.
    message.voice bo'lishi shart.
    """
    if not message.voice:
        return ""

    api_key = getattr(settings, "uzbekvoice_api_key", None)
    if not api_key:
        raise RuntimeError("UZBEKVOICE_API_KEY sozlanmagan")

    file_info = await message.bot.get_file(message.voice.file_id)
    file_path = file_info.file_path

    bio = BytesIO()
    await message.bot.download_file(file_path, bio)
    bio.seek(0)
    file_bytes = bio.read()

    text = await stt_uzbekvoice(
        file_bytes=file_bytes,
        api_key=api_key,
        language=language,
    )

    if text:
        text = text.strip()

    logger.info("UzbekVoice STT text: %r", text)
    return text or ""
