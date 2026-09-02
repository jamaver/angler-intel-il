"""Small JSON cache for non-authoritative environmental observations."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def cache_root() -> Path:
    configured = os.environ.get("AI_INSTANCE_DIR")
    root = Path(configured) if configured else ROOT / "instance"
    return root / "cache" / "environment"


def cache_key(provider: str, latitude: object, longitude: object) -> Path:
    token = f"{provider}:{latitude}:{longitude}".encode()
    return cache_root() / (hashlib.sha256(token).hexdigest() + ".json")


def read_cached(provider: str, latitude: object, longitude: object, max_age_seconds: int = 1200) -> dict[str, Any] | None:
    path = cache_key(provider, latitude, longitude)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        age = max(0, time.time() - float(payload.get("cached_at", 0)))
        if isinstance(payload.get("data"), dict):
            payload["age_seconds"] = round(age)
            payload["stale"] = age > max_age_seconds
            return payload
    except (OSError, ValueError, TypeError):
        return None
    return None


def write_cached(provider: str, latitude: object, longitude: object, data: dict[str, Any]) -> Path:
    path = cache_key(provider, latitude, longitude)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"provider": provider, "cached_at": time.time(), "data": data}, separators=(",", ":")), encoding="utf-8")
    os.replace(temp, path)
    return path
