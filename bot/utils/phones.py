# bot/utils/phones.py
import logging
import re
from typing import List
from typing import Optional, Set

logger = logging.getLogger(__name__)

PHONE_PATTERN = re.compile(r"\+?\d[\d\s\-]{6,}")

PHONE_REGEX = re.compile(r"(\+?\d(?:[ \-\(\)]*\d){7,})")


def normalize_phone(raw: str) -> Optional[str]:
    digits = re.sub(r"\D", "", raw)

    if len(digits) < 9:
        return None

    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"

    if len(digits) == 9:
        return f"+998{digits}"

    return f"+{digits}"


def extract_phones(text: str) -> List[str]:
    if not text:
        return []

    matches = PHONE_REGEX.findall(text)
    normalized: Set[str] = set()
    for m in matches:
        p = normalize_phone(m)
        if p:
            normalized.add(p)

    print(f"[PHONES] text={text!r} -> matches={matches} -> normalized={list(normalized)}")

    return list(normalized)


def _normalize_phone_digits(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None

    if digits.startswith("998") and len(digits) == 12:
        return "+" + digits

    if len(digits) == 9 and digits[0] == "9":
        return "+998" + digits

    if len(digits) > 12 and digits.endswith(("998",)):
        pass

    if len(digits) >= 9:
        return digits

    return None


def extract_phones(text: str) -> List[str]:
    matches = PHONE_PATTERN.findall(text or "")
    normalized: List[str] = []

    for m in matches:
        norm = _normalize_phone_digits(m)
        if norm and norm not in normalized:
            normalized.append(norm)

    logger.info(
        '[PHONES] text=%r -> matches=%s -> normalized=%s',
        text,
        matches,
        normalized,
    )
    return normalized


DIGIT_WORDS = {
    "nol": "0",
    "nolik": "0",
    "zero": "0",

    "bir": "1",
    "ikki": "2",
    "uch": "3",

    "tort": "4",
    "to'rt": "4",
    "turt": "4",

    "besh": "5",
    "olti": "6",
    "yetti": "7",
    "sakkiz": "8",

    "toqqiz": "9",
    "to'qqiz": "9",
    "toqiz": "9",
}


def _normalize_token(w: str) -> str:
    w = w.lower()
    w = (
        w.replace("’", "'")
        .replace("`", "'")
        .replace("‘", "'")
        .replace("ʼ", "'")
    )
    return w


def extract_spoken_phone_candidates(text: str) -> List[str]:
    cleaned = re.sub(r"[^\w\s'ʼ`’]", " ", text or "")
    tokens = [t for t in re.split(r"\s+", cleaned) if t]

    digit_sequences: List[str] = []
    current_digits: List[str] = []

    def flush():
        nonlocal current_digits, digit_sequences
        if len(current_digits) >= 7:  # minimal uzunlik
            seq = "".join(current_digits)
            digit_sequences.append(seq)
        current_digits = []

    for tok in tokens:
        w = _normalize_token(tok)

        if re.fullmatch(r"\d+", w):
            current_digits.append(w)
            continue

        if w in DIGIT_WORDS:
            current_digits.append(DIGIT_WORDS[w])
            continue

        flush()

    flush()

    unique = []
    for seq in digit_sequences:
        if seq not in unique:
            unique.append(seq)

    logger.info("[SPOKEN_PHONES] text=%r -> digit_seqs=%s", text, unique)
    return unique
