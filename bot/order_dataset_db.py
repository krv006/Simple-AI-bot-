# bot/order_dataset_db.py
from typing import List, Optional

from aiogram.types import Message
from psycopg2.extras import Json

from .config import Settings
from .db import _get_connection  # mavjud connection'dan foydalanamiz


def init_order_dataset_table(settings: Settings) -> None:
    conn = _get_connection(settings)
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_order_dataset (
                id              SERIAL PRIMARY KEY,
                order_id        INTEGER,          -- ai_orders.id
                user_message_id BIGINT,           -- asosiy base_message.id
                user_id         BIGINT,
                username        TEXT,
                full_name       TEXT,
                group_id        BIGINT,
                group_title     TEXT,
                messages        TEXT[],           -- sessiyadagi hamma xabarlar
                phones          TEXT[],
                location        JSONB,
                amount          BIGINT,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )


def save_order_dataset_row(
        settings: Settings,
        *,
        order_id: int,
        base_message: Message,
        messages: List[str],
        phones: Optional[List[str]],
        location: Optional[dict],
        amount: Optional[int],
) -> int:
    """
    Bitta yakuniy zakaz bo'yicha dataset qatori saqlaydi.
    messages – sessiyadagi hamma xabarlar (raw_messages).
    """
    conn = _get_connection(settings)
    user = base_message.from_user

    username = user.username if user and user.username else None
    full_name = user.full_name if user and user.full_name else None

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ai_order_dataset (
                order_id,
                user_message_id,
                user_id,
                username,
                full_name,
                group_id,
                group_title,
                messages,
                phones,
                location,
                amount
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
            """,
            (
                order_id,
                base_message.message_id,
                user.id if user else None,
                username,
                full_name,
                base_message.chat.id,
                base_message.chat.title,
                messages if messages else None,
                phones if phones else None,
                Json(location) if location else None,
                amount,
            ),
        )
        row = cur.fetchone()
        return row[0]
