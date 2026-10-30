"""Flat-file JSON cache with TTLs, used to avoid re-hitting the Sleeper API."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable


class FileCache:
    """Caches JSON-serializable values to one file per key under `dir`.

    `clock` is injectable so tests can control expiry without sleeping.
    """

    def __init__(self, dir: Path | str, clock: Callable[[], float] = time.time) -> None:
        self.dir = Path(dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._clock = clock

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if self._clock() >= entry["expires_at"]:
            return None
        return entry["value"]

    def set(self, key: str, value: Any, ttl_seconds: float) -> None:
        entry = {"expires_at": self._clock() + ttl_seconds, "value": value}
        self._path(key).write_text(json.dumps(entry))
