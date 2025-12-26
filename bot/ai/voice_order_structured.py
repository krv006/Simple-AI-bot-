# bot/ai/voice_order_structured.py
import json
import time
import logging
from typing import List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from bot.config import Settings
from bot.prompt.prompt_manager import load_prompt_config

logger = logging.getLogger(__name__)

# =========================
# LLM circuit-breaker (module-level)
# =========================
_LLM_DISABLED_UNTIL_TS: float = 0.0


def _llm_disabled() -> bool:
    return time.time() < _LLM_DISABLED_UNTIL_TS


def _disable_llm_for(seconds: int, reason: str):
    global _LLM_DISABLED_UNTIL_TS
    _LLM_DISABLED_UNTIL_TS = time.time() + float(seconds)
    logger.warning("LLM disabled for %s seconds. reason=%s", seconds, reason)


class VoiceOrderExtraction(BaseModel):
    """
    STT'dan olingan voice xabar bo'yicha yakuniy strukturali natija.
    (Siz buni text uchun ham ishlatyapsiz.)
    """
    is_order: bool = Field(
        ...,
        description="Xabar zakazga aloqador bo'lsa True, aks holda False.",
    )
    phone_numbers: List[str] = Field(
        default_factory=list,
        description=(
            "Faqat mijoz telefon raqamlari. Har biri +998 bilan boshlovchi to'liq raqam, "
            "masalan: +998901234567. Agar aniq bo'lmasa bo'sh qoldir."
        ),
    )
    amount: Optional[int] = Field(
        default=None,
        description=(
            "Zakaz summasi so'mda. Masalan, 'besh yuz ming so'm' -> 500000. "
            "Agar aniq summa yo'q bo'lsa, None."
        ),
    )
    comment: str = Field(
        ...,
        description=(
            "Kuryer uchun qisqa izoh. Masalan, mijozning og'zaki izohi, "
            "yoki xabarni tartiblangan ko'rinishda."
        ),
    )


def _escape_braces(text: str) -> str:
    """
    ChatPromptTemplate ichida literal { } ishlatish uchun ularni {{ }} ga almashtiramiz.
    """
    if not text:
        return text
    return text.replace("{", "{{").replace("}", "}}")


def _build_prompt() -> ChatPromptTemplate:
    """
    AI-ga aniq instruksiya beradigan prompt.
    Qoidalar prompt_config.json (DB) dan olinadi.
    """
    config, config_hash = load_prompt_config()
    rules = config.get("rules", {})
    examples = config.get("examples", [])
    output_schema = config.get("output_schema", {})

    system_parts: list[str] = []

    meta = config.get("meta", {})
    desc = meta.get("description")
    if desc:
        system_parts.append(_escape_braces(desc))

    system_parts.append(
        _escape_braces(
            "Siz Telegram dostavka botining AI yordamchisiz. "
            "Sizga xabar matni va rule-based topilgan telefon/summa nomzodlari beriladi. "
            "Siz yakuniy strukturali natijani to'g'ri va ishonchli qilishingiz kerak."
        )
    )

    # RULES bo'limini qo'shamiz
    for section, items in rules.items():
        system_parts.append(_escape_braces(f"\n[{section.upper()} QOIDALARI]:"))
        for rule in items:
            system_parts.append(_escape_braces(f"- {rule}"))

    # output_schema ni JSON ko'rinishida qo'shamiz
    if output_schema:
        schema_json = json.dumps(output_schema, ensure_ascii=False, indent=2)
        system_parts.append(
            _escape_braces(
                "\nChiqarilishi kerak bo'lgan JSON struktura tavsifi (output_schema):"
            )
        )
        system_parts.append(_escape_braces(schema_json))

    # examples larni ham qo'shamiz
    if examples:
        system_parts.append(_escape_braces("\nMisollar (input -> expected_output):"))
        for ex in examples[:3]:
            inp = ex.get("input", "")
            expected = ex.get("expected_output", {})
            expected_json = json.dumps(expected, ensure_ascii=False)

            system_parts.append(_escape_braces(f"Input:\n{inp}"))
            system_parts.append(_escape_braces("Expected JSON:\n" + expected_json))

    system_msg = "\n".join(system_parts)

    human_msg = (
        "Asosiy ma'lumotlar:\n"
        "Xabar matni: \"{text}\"\n\n"
        "Raw telefon kandidatlari (rule-based): {raw_phone_candidates}\n"
        "Raw summa kandidatlari (rule-based): {raw_amount_candidates}\n\n"
        "Yuqoridagi ma'lumotlar asosida VoiceOrderExtraction strukturasiga mos "
        "aniq natija qaytaring."
    )

    return ChatPromptTemplate.from_messages(
        [
            ("system", system_msg),
            ("human", human_msg),
        ]
    )


def get_voice_order_extractor(settings: Settings) -> ChatOpenAI:
    """
    LangChain ChatOpenAI modelini qaytaradi.
    """
    # max_retries: kvota tugagan paytda 3 marta urinishning foydasi yo'q
    model = ChatOpenAI(
        model="gpt-4.1-mini",
        temperature=0,
        openai_api_key=settings.openai_api_key,
        max_retries=0,  # MUHIM: retry'ni o'chiramiz (o'zingiz boshqarasiz)
        timeout=30,
    )
    return model


def extract_order_structured(
    settings: Settings,
    *,
    text: str,
    raw_phone_candidates: list[str],
    raw_amount_candidates: list[int],
) -> Optional[VoiceOrderExtraction]:
    """
    Xabar matn + rule-based nomzodlardan foydalanib,
    LangChain structured output orqali yakuniy natijani oladi.

    QAYTARADI:
      - VoiceOrderExtraction (muvaffaqiyatli bo'lsa)
      - None (LLM vaqtincha o'chirilgan / quota / rate-limit / boshqa xato bo'lsa)
    """
    if _llm_disabled():
        logger.warning("extract_order_structured skipped: LLM cooldown active.")
        return None

    prompt = _build_prompt()
    llm = get_voice_order_extractor(settings)
    structured_llm = llm.with_structured_output(VoiceOrderExtraction)
    chain = prompt | structured_llm

    try:
        result: VoiceOrderExtraction = chain.invoke(
            {
                "text": text,
                "raw_phone_candidates": raw_phone_candidates,
                "raw_amount_candidates": raw_amount_candidates,
            }
        )
        return result

    except Exception as e:
        # LangChain ichida openai errorlar ham shu yerga tushadi
        msg = str(e)

        # 1) Balans/kvota tugagan holat (sizdagi log aynan shu)
        if "insufficient_quota" in msg:
            _disable_llm_for(30 * 60, "insufficient_quota")
            logger.exception("LLM error: insufficient_quota")
            return None

        # 2) Oddiy 429 / rate limit
        if "Error code: 429" in msg or "Too Many Requests" in msg:
            _disable_llm_for(60, "429_rate_limit")
            logger.exception("LLM error: 429 Too Many Requests")
            return None

        # 3) Boshqa xatolar
        logger.exception("LLM structured extraction error: %s", e)
        return None
