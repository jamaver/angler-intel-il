from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

DEFAULT_VERSION = "v6.13-gear-intelligence-packing-catch-linking"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _path_from_env(name: str, default: Path) -> Path:
    value = os.environ.get(name, "").strip()
    return Path(value) if value else default


def settings_path() -> Path:
    return _path_from_env("AI_GEAR_SETTINGS_PATH", DATA_DIR / "gear_settings.json")


def _default_settings() -> dict[str, Any]:
    return {
        "version": DEFAULT_VERSION,
        "updated_at": _now(),
        "search_scope_default": "both",
        "online_lookup_enabled": False,
        "enabled_providers": {
            "structured": True,
            "manufacturer": False,
            "walmart": False,
            "amazon": False,
        },
        "allow_remote_images": False,
        "cache_lookup_results": True,
        "cache_duration_days": 30,
        "prefer_manufacturer_specs": True,
    }


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except Exception:
        return default


def load_settings() -> dict[str, Any]:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_json(path, _default_settings())
    if not isinstance(data, dict):
        data = _default_settings()
    defaults = _default_settings()
    for key, value in defaults.items():
        data.setdefault(key, value)
    data["enabled_providers"] = data.get("enabled_providers") if isinstance(data.get("enabled_providers"), dict) else defaults["enabled_providers"]
    data.setdefault("version", DEFAULT_VERSION)
    data.setdefault("updated_at", _now())
    return data


def save_settings(data: dict[str, Any]) -> dict[str, Any]:
    payload = load_settings()
    payload.update({k: v for k, v in dict(data or {}).items() if k in payload or k in _default_settings()})
    payload["updated_at"] = _now()
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload
