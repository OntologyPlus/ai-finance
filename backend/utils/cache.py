from __future__ import annotations

import time
from typing import Any, Dict, Optional


class TTLCache:
    def __init__(self, default_ttl: int = 3600):
        self.default_ttl = default_ttl
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry["timestamp"] > entry["ttl"]:
            del self._store[key]
            return None
        return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._store[key] = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl or self.default_ttl,
        }

    def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        self._store.clear()

    def keys(self) -> list[str]:
        expired = []
        result = []
        now = time.time()
        for key, entry in self._store.items():
            if now - entry["timestamp"] > entry["ttl"]:
                expired.append(key)
            else:
                result.append(key)
        for key in expired:
            del self._store[key]
        return result

    def size(self) -> int:
        return len(self.keys())
