from __future__ import annotations

import hashlib
import json
from typing import Any


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): canonicalize(value[key]) for key in sorted(value.keys(), key=str)}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, tuple):
        return [canonicalize(item) for item in value]
    return value


def canonical_dumps(value: Any) -> str:
    return json.dumps(canonicalize(value), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def record_hash(value: Any) -> str:
    return hashlib.sha256(canonical_dumps(value).encode("utf-8")).hexdigest()


def stable_key_set(value: Any) -> tuple[str, ...]:
    if isinstance(value, dict):
        return tuple(sorted(str(key) for key in value.keys()))
    return tuple()

