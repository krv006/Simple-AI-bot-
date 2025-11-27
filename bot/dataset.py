# bot/dataset.py
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ORDER_PATH = Path("order.txt")
ERRORS_PATH = Path("errors.txt")


def _ensure_parent(path: Path) -> None:
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)


def append_order_entry(entry: Dict[str, Any]) -> None:
    _ensure_parent(ORDER_PATH)

    if "timestamp" not in entry:
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()

    with ORDER_PATH.open("a", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)
        f.write("\n")


def append_error_entry(entry: Dict[str, Any]) -> None:
    _ensure_parent(ERRORS_PATH)

    if "timestamp" not in entry:
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()

    with ERRORS_PATH.open("a", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False)
        f.write("\n")
