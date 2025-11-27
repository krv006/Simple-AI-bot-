import json
from typing import Any, Dict, List

from ..config import Settings


def _simple_rule_based(text: str) -> Dict[str, Any]:
    tl = text.lower()

    address_keywords = [
        "dom", "kv", "kv.", "kvartira", "подъезд", "подьезд",
        "uy", "eshik", " подъезд", "kvartir", "подъез", "подьез",
        "дом", "улица", "улиц", "mavze", "orqa eshik", "oldi", "oldida"
    ]
    product_keywords = [
        "latte", "капучино", "cappuccino", "americano", "kofe", "coffee",
        "pizza", "burger", "lavash", "doner"
    ]

    has_addr = any(k in tl for k in address_keywords)
    has_prod = any(k in tl for k in product_keywords)

    if has_prod and not has_addr:
        role = "PRODUCT"
        is_order_related = True
    elif has_addr:
        role = "COMMENT"
        is_order_related = True
    else:
        greeting_keywords = ["salom", "assalomu", "qalesiz", "как дела", "привет"]
        if any(k in tl for k in greeting_keywords):
            role = "RANDOM"
            is_order_related = False
        else:
            role = "UNKNOWN"
            is_order_related = False

    return {
        "is_order_related": is_order_related,
        "role": role,
        "has_address_keywords": has_addr,
    }


async def classify_text_ai(
        settings: Settings,
        text: str,
        context_messages: List[str],
) -> Dict[str, Any]:
    if not text.strip():
        return {
            "is_order_related": False,
            "role": "UNKNOWN",
            "has_address_keywords": False,
        }

    if not settings.openai_enabled:
        return _simple_rule_based(text)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)

        system_prompt = (
            "Siz Telegram xabarlarini klassifikatsiya qilasiz. "
            "Maqsad: matn zakazga aloqador yoki yo'qligini aniqlash. "
            "Faqat quyidagi JSON formatda javob qaytaring:\n"
            "{\n"
            '  "is_order_related": bool,\n'
            '  "role": "PRODUCT" | "COMMENT" | "RANDOM" | "UNKNOWN",\n'
            '  "has_address_keywords": bool\n'
            "}\n"
        )

        user_prompt = (
                "Kontekst xabarlar (oxirgi 5 ta):\n"
                + "\n".join(f"- {m}" for m in context_messages[-5:])
                + "\n\nTahlil qilinadigan xabar:\n"
                + text
        )

        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        result_text = resp.choices[0].message.content
        data = json.loads(result_text)

        return {
            "is_order_related": bool(data.get("is_order_related", False)),
            "role": data.get("role", "UNKNOWN"),
            "has_address_keywords": bool(data.get("has_address_keywords", False)),
        }
    except Exception as e:
        print("OpenAI xato, rule-basedga qaytyapman:", repr(e))
        return _simple_rule_based(text)
