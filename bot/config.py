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

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key)


def load_settings() -> Settings:
    load_dotenv()

    tg_bot_token = os.getenv("TG_BOT_TOKEN")
    if not tg_bot_token:
        raise RuntimeError("TG_BOT_TOKEN .env ichida ko'rsatilmagan!")

    return Settings(
        tg_bot_token=tg_bot_token,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        max_diff_seconds=int(os.getenv("MAX_DIFF_SECONDS", "120")),
        geocoder_user_agent=os.getenv("GEOCODER_USER_AGENT", "ai_taxi_bot"),
        debug=os.getenv("DEBUG", "False").lower() == "true",
    )
