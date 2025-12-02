# bot/db.py
import logging
from typing import List, Optional

import requests
from aiogram.types import Message

from .config import Settings

logger = logging.getLogger(__name__)


def _build_headers(settings: Settings) -> dict:
    """
    DRF backend uchun headerlar (Content-Type va Authorization).
    """
    headers = {"Content-Type": "application/json"}
    if settings.api_auth_token:
        # masalan: "Token 123..." yoki "Bearer 123..."
        headers["Authorization"] = settings.api_auth_token
    return headers


def init_db(settings: Settings) -> None:
    """
    Oldin bu yerda Postgres jadvalini CREATE qilardik.
    Endi DB bilan Django shug'ullanadi, shu uchun bu yerda hech narsa qilmaymiz.
    Istasangiz, health-check uchun /api/orders/ ga GET so'rov yuborib ko'rishingiz mumkin.
    """
    logger.info("init_db(): endi DB bilan Django/DRF ishlaydi, bot faqat API bilan gaplashadi.")


def save_order_row(
        settings: Settings,
        *,
        message: Message,
        phones: Optional[List[str]],
        order_text: str,
        location: Optional[dict],
) -> int:
    """
    Eski psycopg2 INSERT o'rniga:
    DRF backend'ga POST /api/orders/ yuboradi va qaytgan id ni qaytaradi.

    Django tarafda Order modeli taxminan eski ai_orders jadvaliga o'xshash bo'lishi kerak:
    - user_message_id, user_id, username, full_name
    - group_id, group_title
    - order_text
    - phones (JSON yoki ArrayField)
    - location (JSONField)
    - is_active, cancelled_at, created_at va h.k. (backend default bilan to'ldiradi)
    """
    from_user = message.from_user
    username = from_user.username if from_user and from_user.username else None
    full_name = from_user.full_name if from_user and from_user.full_name else None

    base_url = settings.api_base_url.rstrip("/")
    url = f"{base_url}/api/orders/"
    headers = _build_headers(settings)

    payload = {
        "user_message_id": message.message_id,
        "user_id": from_user.id if from_user else None,
        "username": username,
        "full_name": full_name,
        "group_id": message.chat.id,
        "group_title": getattr(message.chat, "title", None),
        "order_text": order_text,
        "phones": phones if phones else None,
        "location": location,  # Django tomonida JSONField bo'lishi kerak
        # is_active / cancelled_at / created_at backendning o'zi belgilaydi
    }

    logger.info("save_order_row: POST %s payload=%s", url, payload)

    resp = requests.post(url, json=payload, headers=headers, timeout=10)
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        logger.error("Order create failed: %s, response=%s", exc, resp.text)
        raise

    data = resp.json()
    order_id = data.get("id")
    if order_id is None:
        logger.error("Order create response da 'id' yo'q: %s", data)
        raise RuntimeError("Order create response da id topilmadi")

    logger.info("Order DRF orqali yaratildi, id=%s", order_id)
    return int(order_id)


def cancel_order_row(settings: Settings, order_id: int) -> bool:
    """
    Eski psycopg2 UPDATE o'rniga:
    DRF backend orqali zakazni bekor qiladi.

    Backend tomonda quyidagilardan birini amalga oshirish kerak bo'ladi:

    1) Varianti (odatda eng sodda):
       maxsus endpoint: POST /api/orders/cancel/
       body: {"order_id": <id>}
       va u ichida Order ni topib, is_active=False, cancelled_at=now() qiladi.

    2) Varianti:
       OrderViewSet ga partial_update (PATCH) qo'shib,
       PATCH /api/orders/<id>/ bilan {"is_active": false} yuborish.

    Bu kod 1-variantni kutmoqda: /api/orders/cancel/
    Agar siz 2-variantni qilgan bo'lsangiz, shu yerda URL va methodni moslab o'zgartirasiz.
    """
    base_url = settings.api_base_url.rstrip("/")
    url = f"{base_url}/api/orders/cancel/"
    headers = _build_headers(settings)

    payload = {"order_id": order_id}

    logger.info("cancel_order_row: POST %s payload=%s", url, payload)

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
    except requests.RequestException as exc:
        logger.error("Order cancel request error: %s", exc)
        return False

    if resp.status_code >= 400:
        logger.error("Order cancel failed: status=%s, response=%s", resp.status_code, resp.text)
        return False

    logger.info("Order cancel API muvaffaqiyatli, id=%s", order_id)
    return True
