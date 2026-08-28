from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from loguru import logger

from models.config import settings


class AuditLogger:
    def __init__(self) -> None:
        self._entries: List[Dict[str, Any]] = []
        self._secret = settings.SECRET_KEY.encode() if settings.SECRET_KEY else b"audit-secret"

    def _generate_hmac(self, entry: Dict[str, Any]) -> str:
        payload = json.dumps(
            {
                "action": entry.get("action", ""),
                "actor": entry.get("actor", ""),
                "resource": entry.get("resource", ""),
                "timestamp": entry.get("timestamp", ""),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()

    def log(
        self,
        action: str,
        actor: str = "system",
        resource: str = "",
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info",
    ) -> str:
        entry_id = f"audit_{uuid.uuid4().hex[:12]}"
        entry = {
            "entry_id": entry_id,
            "action": action,
            "actor": actor,
            "resource": resource,
            "details": details or {},
            "severity": severity,
            "timestamp": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        entry["hmac"] = self._generate_hmac(entry)

        self._entries.append(entry)
        logger.info(f"Audit: {action} by {actor} on {resource} [{severity}]")
        return entry_id

    def verify(self, entry_id: str) -> bool:
        entry = next((e for e in self._entries if e["entry_id"] == entry_id), None)
        if entry is None:
            return False

        expected_hmac = self._generate_hmac(entry)
        return hmac.compare_digest(expected_hmac, entry.get("hmac", ""))

    def query(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not filters:
            return self._entries[-100:]

        results = self._entries
        if "action" in filters:
            results = [e for e in results if e["action"] == filters["action"]]
        if "actor" in filters:
            results = [e for e in results if e["actor"] == filters["actor"]]
        if "resource" in filters:
            results = [e for e in results if e["resource"] == filters["resource"]]
        if "severity" in filters:
            results = [e for e in results if e["severity"] == filters["severity"]]
        if "start_time" in filters:
            results = [e for e in results if e["timestamp"] >= filters["start_time"]]
        if "end_time" in filters:
            results = [e for e in results if e["timestamp"] <= filters["end_time"]]

        return results[-100:]
