"""Tiny TTL cache for slow-moving fetch results (committed under cache/).

Fundamentals change quarterly, company profiles ~never, an earnings date is
fixed until it passes, and a plan-gated endpoint will 403 tomorrow too. Caching
these turns most Finnhub calls into disk reads, which matters because every
live call costs a ~1s rate-limit slot (free tier: 60/min).

Values must be JSON-serializable. With path=None the cache is memory-only
(handy for tests and one-off runs).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class FetchCache:
    def __init__(self, path: Path | None):
        self.path = path
        self._data: dict = {}
        if path is not None:
            try:
                self._data = json.loads(Path(path).read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                self._data = {}

    def get(self, key: str, ttl_days: float):
        """Return the cached value if younger than ttl_days, else None."""
        ent = self._data.get(key)
        if not isinstance(ent, dict) or "ts" not in ent:
            return None
        try:
            age = datetime.now(tz=timezone.utc) - datetime.fromisoformat(ent["ts"])
        except ValueError:
            return None
        return ent.get("v") if age.total_seconds() < ttl_days * 86400 else None

    def set(self, key: str, value) -> None:
        self._data[key] = {"ts": datetime.now(tz=timezone.utc).isoformat(), "v": value}

    def save(self) -> None:
        if self.path is None:
            return
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        Path(self.path).write_text(json.dumps(self._data, indent=2), encoding="utf-8")
