# bot/utils/amounts.py
from __future__ import annotations

import re
from typing import List, Tuple, Optional


# Uzbek son so'zlari
UNITS = {
    "nol": 0,
    "bir": 1,
    "ikki": 2,
    "uch": 3,
    "tort": 4,
    "to'rt": 4,
    "turt": 4,
    "besh": 5,
    "olti": 6,
    "yetti": 7,
    "sakkiz": 8,
    "toqqiz": 9,
}

TENS = {
    "on": 10,
    "yigirma": 20,
    "ottiz": 30,
    "o'ttiz": 30,
    "qirq": 40,
    "ellik": 50,
    "oltmish": 60,
    "yetmish": 70,
    "sakson": 80,
    "to'qson": 90,
    "toqson": 90,
    "to'qsonlik": 90,
    "toqsonlik": 90,
}

SCALES = {
    "yuz": 100,
    "ming": 1000,
    "million": 1_000_000,
    "mln": 1_000_000,
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


def _parse_number_phrase(tokens: List[str]) -> int:
    """
    'ikki yuz ellik ming' -> 250000
    'uch yuz ming' -> 300000
    """
    total = 0
    current = 0

    for raw in tokens:
        w = _normalize_token(raw)

        if w in UNITS:
            current += UNITS[w]
        elif w in TENS:
            current += TENS[w]
        elif w in SCALES:
            scale = SCALES[w]
            if current == 0:
                current = 1
            current *= scale
            if scale >= 1000:
                total += current
                current = 0
        elif re.fullmatch(r"\d+([\.,]\d+)?", w):
            # raqamli token (300, 300.5 va hokazo)
            val = float(w.replace(",", "."))
            current += val
        # boshqa so'zlarni e'tiborsiz qoldiramiz

    return int(total + current)


def _extract_yuz_ming_candidates(text: str) -> List[Tuple[int, List[str]]]:
    """
    Matndan '... uch yuz ming ...', 'ikki yuz ellik ming ...' kabi
    yuz+ming strukturalarini topib, raqamga aylantirib qaytaradi.
    """
    cleaned = re.sub(r"[^\w\s'ʼ`’]", " ", text.lower())
    tokens = re.split(r"\s+", cleaned.strip())
    candidates: List[Tuple[int, List[str]]] = []

    for j, tok in enumerate(tokens):
        if _normalize_token(tok) == "ming":
            # oldindan eng yaqin 'yuz' ni topamiz
            yuz_idx = None
            for k in range(j - 1, -1, -1):
                if _normalize_token(tokens[k]) == "yuz":
                    yuz_idx = k
                    break
            if yuz_idx is None:
                continue

            # 'uch yuz ming' bo'lsin deb bitta tokenni oldindan ham olamiz
            start = max(0, yuz_idx - 1)
            phrase_tokens = tokens[start : j + 1]
            value = _parse_number_phrase(phrase_tokens)
            if value > 0:
                candidates.append((value, phrase_tokens))

    return candidates


def _extract_digit_candidates(text: str) -> List[int]:
    """
    Matndan raqamli (123, 300 000, 1.5 mln emas – oddiy integer) summalarini chiqarib oladi.
    """
    candidates: List[int] = []
    # 12 000, 300000, 1 000 000 ko'rinishidagi raqamlarni tozalab olamiz
    for m in re.findall(r"\d[\d\s]*", text):
        clean = re.sub(r"\s+", "", m)
        try:
            candidates.append(int(clean))
        except ValueError:
            continue
    return candidates


def extract_amount_from_text(text: str) -> Optional[int]:
    """
    Berilgan matndan ehtimoliy summa (so'm) ni integer ko'rinishida qaytaradi.
    Misollar:
      "uch yuz ming so'm" -> 300000
      "ikki yuz ellik ming" -> 250000
      "300 ming" -> 300000
    Hozircha eng yirik (max) kandidatni qaytaramiz.
    """
    candidates: List[int] = []

    # 1) '... yuz ... ming' strukturalari
    for value, phrase_tokens in _extract_yuz_ming_candidates(text):
        candidates.append(value)

    # 2) Raqamli ko'rinishlar (300000, 12 000 va hokazo)
    candidates.extend(_extract_digit_candidates(text))

    if not candidates:
        return None

    return max(candidates)
