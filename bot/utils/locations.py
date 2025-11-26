# bot/utils/locations.py
import re
from typing import Optional, Dict, Any

from aiogram.types import Message

LINK_REGEX = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)


def extract_location_from_message(message: Message) -> Optional[Dict[str, Any]]:
    """
    1) Telegram native location (message.location)
    2) Google/Yandex/2GIS link
    """
    # 1) Telegram location
    if message.location:
        return {
            "type": "telegram",
            "lat": message.location.latitude,
            "lon": message.location.longitude,
            "raw": None,
        }

    # 2) Matndan link qidiramiz
    text = message.text or message.caption or ""
    links = LINK_REGEX.findall(text)
    for link in links:
        lower = link.lower()
        loc_type = None

        if "google.com/maps" in lower or "maps.app.goo.gl" in lower or "goo.gl/maps" in lower:
            loc_type = "google"
        elif "yandex." in lower and "maps" in lower:
            loc_type = "yandex"
        elif "2gis" in lower:
            loc_type = "2gis"

        if loc_type:
            return {
                "type": loc_type,
                "lat": None,
                "lon": None,
                "raw": link,
            }

    return None
