# bot/ai/order_extractor.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from bot.config import Settings
from bot.ai.voice_order_structured import extract_order_structured
from bot.utils.phones import normalize_phone, ensure_phone_suffix

@dataclass
class Extracted:
    phones: List[str]
    amount: Optional[int]
    address_type: str
    address_value: Optional[str]
    comment: Optional[str]
    confidence: float
    need_human_review: bool


def extract_via_prompt(settings: Settings, text: str) -> Extracted:
    """
    100% prompt-based extraction.
    Rule-based candidates yuborilmaydi.
    """
    ai = extract_order_structured(
        settings,
        text=text,
        raw_phone_candidates=[],     # <-- IMPORTANT: bo'sh
        raw_amount_candidates=[],    # <-- IMPORTANT: bo'sh
    )

    phones: List[str] = []
    for p in (ai.phone_numbers or []):
        n = normalize_phone(p)
        if n:
            phones.append(ensure_phone_suffix(n, "--"))

    # amount int bo‘lishi kerak bo‘lsa:
    amount = ai.amount if ai.amount is not None else None

    # address mapping (sizdagi schema'ga moslab)
    address_type = "none"
    address_value = None
    if getattr(ai, "address", None):
        # Agar ai.address dict bo‘lsa
        try:
            address_type = ai.address.get("type") or "none"
            address_value = ai.address.get("value")
        except Exception:
            pass

    return Extracted(
        phones=phones,
        amount=amount,
        address_type=address_type,
        address_value=address_value,
        comment=getattr(ai, "comment", None),
        confidence=float(getattr(ai, "confidence", 0.7) or 0.7),
        need_human_review=bool(getattr(ai, "need_human_review", False)),
    )
