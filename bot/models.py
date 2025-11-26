# bot/models.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Set


@dataclass
class OrderSession:
    user_id: int
    chat_id: int
    phones: Set[str] = field(default_factory=set)
    location: Optional[Dict[str, Any]] = None
    comments: List[str] = field(default_factory=list)
    product_texts: List[str] = field(default_factory=list)
    raw_messages: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_completed: bool = False
