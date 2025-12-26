# bot/utils/phones.py
import logging
import re
from typing import List, Optional, Set

from bot.utils.numbers_uz import spoken_phone_words_to_digits

logger = logging.getLogger(__name__)

PHONE_REGEX = re.compile(r"(\+?\d(?:[ \-\(\)]*\d){7,})")


# =========================
# PROMPT/LLM OUTPUT HELPERS
# =========================

PHONE_SUFFIX = "--"


def strip_phone_suffix(s: str, suffix: str = PHONE_SUFFIX) -> str:
    s = (s or "").strip()
    if s.endswith(suffix):
        return s[: -len(suffix)].strip()
    return s


def normalize_uz_phone_strict(raw: str) -> Optional[str]:
    """
    LLM yoki user matnidan kelgan phone ni qat'iy normalize qiladi.
    Qabul qilinadigan formatlar:
      - +998901234567
      - 998901234567
      - 901234567
      - +998901234567--   (suffix bo'lsa ham)
      - 998901234567--    (suffix bo'lsa ham)

    QAYTARADI: +998XXXXXXXXX yoki None
    """
    if not raw:
        return None

    raw = strip_phone_suffix(raw)
    digits = re.sub(r"\D", "", raw or "")

    # +998 + 9 digits = 12 digits
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"

    # local 9 digits
    if len(digits) == 9:
        return f"+998{digits}"

    return None


def ensure_phone_suffix(phones: List[str], suffix: str = PHONE_SUFFIX) -> List[str]:
    """
    Output uchun: har bir telefon oxiriga '--' qo'shib beradi.
    Input telefonlar suffixsiz bo'lishi mumkin.
    """
    out: List[str] = []
    for p in phones or []:
        p = (p or "").strip()
        if not p:
            continue
        if not p.endswith(suffix):
            p = p + suffix
        out.append(p)
    return out


def normalize_phone_list_strict(phones: List[str]) -> List[str]:
    """
    LLM qaytargan phones listni tozalaydi:
    - suffixni olib tashlaydi
    - +998 formatga keltiradi
    - invalid bo'lsa olib tashlaydi
    - unique qiladi (set)
    """
    normalized: Set[str] = set()
    for p in phones or []:
        np = normalize_uz_phone_strict(p)
        if np:
            normalized.add(np)
    return list(normalized)


# =========================
# OLD RULE-BASED (qolsin)
# =========================

def normalize_phone(raw: str) -> Optional[str]:
    """
    Rule-based normalize (eski).
    """
    digits = re.sub(r"\D", "", raw or "")

    if len(digits) < 9:
        return None

    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"

    if len(digits) == 9:
        return f"+998{digits}"

    return f"+{digits}"


def extract_phones(text: str) -> List[str]:
    """
    Rule-based raqamli telefonlarni topib, normalize qiladi.
    Eslatma: TEXT pipeline uchun siz endi buni ishlatmayapsiz (prompt-first).
    Voice/fallback uchun qoladi.
    """
    if not text:
        return []

    matches = PHONE_REGEX.findall(text)
    normalized: Set[str] = set()

    for m in matches:
        p = normalize_phone(m)
        if p:
            normalized.add(p)

    result = list(normalized)

    logger.info("[PHONES] text=%r -> matches=%s -> normalized=%s", text, matches, result)
    return result


# ========== Og'zaki telefon raqamlari (so'z bilan aytilgan) ==========

def _postprocess_phone_digits(seq: str) -> Optional[str]:
    if not seq:
        return None

    if len(seq) < 9:
        return None

    if len(seq) > 9:
        seq = seq[:9]

    return seq


def extract_spoken_phone_candidates(text: str) -> List[str]:
    if not text:
        return []

    digit_str = spoken_phone_words_to_digits(text)
    digit_str = re.sub(r"\D", "", digit_str or "")

    if not digit_str:
        logger.info("[SPOKEN_PHONES] text=%r -> no digit_str", text)
        return []

    processed = _postprocess_phone_digits(digit_str)
    if not processed:
        logger.info("[SPOKEN_PHONES] text=%r -> digit_str=%r is too short/invalid", text, digit_str)
        return []

    logger.info("[SPOKEN_PHONES] text=%r -> digit_str=%r -> %s", text, digit_str, processed)
    return [processed]


def format_phone_display(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")

    if digits.startswith("998") and len(digits) >= 12:
        digits = digits[-9:]

    if len(digits) != 9:
        return phone

    return f"{digits[0:2]} {digits[2:5]} {digits[5:7]} {digits[7:9]}"
