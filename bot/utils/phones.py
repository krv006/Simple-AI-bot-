# bot/utils/phones.py
import re
from typing import List, Optional, Set


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
