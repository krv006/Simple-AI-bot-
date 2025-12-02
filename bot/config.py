# bot/config.py
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    tg_bot_token: str
    openai_api_key: str | None
    openai_model: str
    gemini_api_key: str | None
    gemini_model: str
    max_diff_seconds: int
    geocoder_user_agent: str
    debug: bool
    send_group_id: int | None
    error_group_id: int | None
    ai_check_group_id: int | None  # AI_CHECK guruh
    db_dsn: str | None  # Postgres DSN

    uzbekvoice_api_key: str | None  # <<< YANGI MAYDON

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key)


def load_settings() -> Settings:
    load_dotenv()

    tg_bot_token = os.getenv("TG_BOT_TOKEN")
    if not tg_bot_token:
        raise RuntimeError("TG_BOT_TOKEN .env ichida ko'rsatilmagan!")

    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    gemini_api_key = os.getenv("GEMINI_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    max_diff_seconds = int(os.getenv("MAX_DIFF_SECONDS", "120"))
    geocoder_user_agent = os.getenv("GEOCODER_USER_AGENT", "ai_taxi_bot")
    debug = os.getenv("DEBUG", "False").lower() == "true"

    send_group_raw = os.getenv("SEND_GROUP_ID")
    error_group_raw = os.getenv("SEND_ERROR_MESSAGE")
    ai_check_raw = os.getenv("AI_CHECK")

    db_dsn = os.getenv("DB_DSN")

    uzbekvoice_api_key = os.getenv("UZBEKVOICE_API_KEY")  # <<< .env dan olamiz

    def _to_int(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    send_group_id = _to_int(send_group_raw)
    error_group_id = _to_int(error_group_raw)
    ai_check_group_id = _to_int(ai_check_raw)

    return Settings(
        tg_bot_token=tg_bot_token,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        max_diff_seconds=max_diff_seconds,
        geocoder_user_agent=geocoder_user_agent,
        debug=debug,
        send_group_id=send_group_id,
        error_group_id=error_group_id,
        ai_check_group_id=ai_check_group_id,
        db_dsn=db_dsn,
        uzbekvoice_api_key=uzbekvoice_api_key,  # <<< shu yerda
    )
