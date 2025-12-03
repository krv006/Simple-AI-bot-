# bot/ai/stt_uzbekvoice.py
import asyncio
import logging
from typing import Optional

import requests

from ..utils.numbers_uz import normalize_uzbek_numbers_in_text

logger = logging.getLogger(__name__)

UZBEKVOICE_STT_URL = "https://uzbekvoice.ai/api/v1/stt"


def _stt_sync(
        file_bytes: bytes,
        api_key: str,
        language: str = "uz",
) -> Optional[str]:
    headers = {
        "Authorization": api_key,
    }

    files = {
        "file": ("voice.ogg", file_bytes, "audio/ogg"),
    }

    data = {
        "return_offsets": "false",
        "run_diarization": "false",
        "language": language,
        "blocking": "true",
    }

    resp = requests.post(
        UZBEKVOICE_STT_URL,
        headers=headers,
        files=files,
        data=data,
        timeout=60,
    )
    resp.raise_for_status()
    j = resp.json()
    logger.debug("Uzbekvoice response: %s", j)

    text: Optional[str] = None

    if isinstance(j, dict):
        if "text" in j:
            text = j["text"]
        elif "result" in j and isinstance(j["result"], dict):
            text = j["result"].get("text")

    if text:
        text = normalize_uzbek_numbers_in_text(text)

    return text


async def stt_uzbekvoice(
        file_bytes: bytes,
        api_key: str,
        language: str = "uz",
) -> Optional[str]:
    return await asyncio.to_thread(_stt_sync, file_bytes, api_key, language)
