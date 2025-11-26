# bot/storage.py
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional

from aiogram.types import Message

from .config import Settings
from .models import OrderSession

SESSIONS: Dict[Tuple[int, int], OrderSession] = {}


def get_session_key(message: Message) -> Tuple[int, int]:
    return message.chat.id, message.from_user.id  # type: ignore[union-attr]


def get_or_create_session(settings: Settings, message: Message) -> OrderSession:
    key = get_session_key(message)
    now = datetime.now(timezone.utc)
    session = SESSIONS.get(key)

    if session:
        # Juda eski bo'lsa, yangidan boshlaymiz
        if (now - session.updated_at).total_seconds() > settings.max_diff_seconds:
            SESSIONS[key] = OrderSession(
                user_id=message.from_user.id,  # type: ignore[union-attr]
                chat_id=message.chat.id,
            )
    else:
        SESSIONS[key] = OrderSession(
            user_id=message.from_user.id,  # type: ignore[union-attr]
            chat_id=message.chat.id,
        )

    return SESSIONS[key]


def is_session_ready(session: OrderSession) -> bool:
    """Minimal shart: phone + location bor."""
    return bool(session.phones and session.location)


def finalize_session(key: Tuple[int, int]) -> Optional[OrderSession]:
    """
    Sessionni yakunlaydi va RETURN qiladi.
    E’TIBOR: bu yerda dict dan OCHIRMAYMIZ, chunki handler
    birinchi bo'lib xabarni yuborishi kerak, keyin clear_session() qiladi.
    """
    session = SESSIONS.get(key)
    if not session:
        return None
    session.is_completed = True
    return session


def clear_session(key: Tuple[int, int]) -> None:
    """
    Yakunlangan sessionni butunlay o'chirib yuboradi.
    Shunda keyingi xabarlar uchun YANGI OrderSession ochiladi.
    """
    if key in SESSIONS:
        del SESSIONS[key]
