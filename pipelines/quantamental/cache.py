from __future__ import annotations

import copy
import time
from threading import RLock
from typing import Any


class TTLCache:
    def __init__(self) -> None:
        self._items: dict[str, tuple[float, Any]] = {}
        self._lock = RLock()

    def get(self, key: str) -> Any | None:
        now = time.time()
        with self._lock:
            item = self._items.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._items.pop(key, None)
                return None
            return copy.deepcopy(value)

    def set(self, key: str, value: Any, ttl_s: int | float) -> None:
        if ttl_s <= 0:
            return
        status = ""
        if isinstance(value, dict):
            status = str(value.get("status") or "").lower()
        if status in {"failed", "error"}:
            return
        with self._lock:
            self._items[key] = (time.time() + float(ttl_s), copy.deepcopy(value))

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


quantamental_cache = TTLCache()
