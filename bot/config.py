# bot/config.py
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    # Telegram
    tg_bot_token: str

    # AI
    openai_api_key: str | None
    openai_model: str
    gemini_api_key: str | None
    gemini_model: str

    # Boshqa sozlamalar
    max_diff_seconds: int
    geocoder_user_agent: str
    debug: bool

    # Guruhlar
    send_group_id: int | None
    error_group_id: int | None
    ai_check_group_id: int | None  # AI_CHECK guruh

    # Eski Postgres DSN (endilikda ishlatilmaydi, lekin xozircha qoldiramiz)
    db_dsn: str | None

    # --- DRF bilan ishlash uchun yangi maydonlar ---
    api_base_url: str  # masalan: http://localhost:8000 yoki https://backend.domain.com
    api_auth_token: str | None  # agar DRF token bilan himoyalangan bo'lsa (Token xxx / Bearer xxx)

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

    # Eski Postgres ulanishi (endi ishlatilmaydi)
    db_dsn = os.getenv("DB_DSN")

    # DRF uchun
    api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    # masalan: "Token 123..." yoki "Bearer 123..."
    api_auth_token = os.getenv("API_AUTH_TOKEN")

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
        api_base_url=api_base_url,
        api_auth_token=api_auth_token,
    )
