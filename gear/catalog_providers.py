from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .inventory import catalog_cache_path, _slug, _text


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _default_cache() -> dict[str, Any]:
    return {
        "version": "v6.10-tackle-locker",
        "updated_at": _now(),
        "products": [],
    }


def load_cache() -> dict[str, Any]:
    data = _read_json(catalog_cache_path(), _default_cache())
    if not isinstance(data, dict):
        data = _default_cache()
    data.setdefault("version", "v6.10-tackle-locker")
    data.setdefault("updated_at", _now())
    data["products"] = data.get("products") if isinstance(data.get("products"), list) else []
    return data


def save_cache(data: dict[str, Any]) -> None:
    payload = dict(data or {})
    payload.setdefault("version", "v6.10-tackle-locker")
    payload["updated_at"] = _now()
    payload["products"] = payload.get("products") if isinstance(payload.get("products"), list) else []
    _write_json(catalog_cache_path(), payload)


def normalize_product(raw_product: dict[str, Any]) -> dict[str, Any]:
    product = dict(raw_product or {})
    product.setdefault("brand", "")
    product.setdefault("model", "")
    product.setdefault("category", "misc")
    product["display_name"] = _text(product.get("display_name"), " ".join(part for part in [product.get("brand"), product.get("model")] if _text(part)))
    product["specifications"] = product.get("specifications") if isinstance(product.get("specifications"), dict) else {}
    product["image_url"] = _text(product.get("image_url"), "")
    product["source_url"] = _text(product.get("source_url"), "")
    product["source_name"] = _text(product.get("source_name"), "Catalog cache")
    product["confidence"] = _text(product.get("confidence"), "low").lower()
    product["retrieved_at"] = _text(product.get("retrieved_at"), _now())
    product["query_key"] = _slug(" ".join(part for part in [product.get("brand"), product.get("model"), product.get("display_name")] if _text(part)))
    return product


def cache_product(product: dict[str, Any]) -> dict[str, Any]:
    data = load_cache()
    products = [item for item in data.get("products", []) if isinstance(item, dict)]
    normalized = normalize_product(product)
    key = normalized.get("query_key")
    if key and any(_text(item.get("query_key"), "") == key for item in products):
        return normalized
    products.insert(0, normalized)
    data["products"] = products
    save_cache(data)
    return normalized


def search_products(query: str, category: str = "") -> list[dict[str, Any]]:
    q = _text(query, "").lower()
    category = _text(category, "").lower()
    results: list[dict[str, Any]] = []

    for product in load_cache().get("products", []):
        if not isinstance(product, dict):
            continue
        blob = " ".join([
            _text(product.get("brand"), ""),
            _text(product.get("model"), ""),
            _text(product.get("display_name"), ""),
            _text(product.get("category"), ""),
            " ".join(map(str, product.get("specifications", {}).values())) if isinstance(product.get("specifications"), dict) else "",
        ]).lower()
        if q and q not in blob:
            continue
        if category and category != _text(product.get("category"), "").lower():
            continue
        results.append(normalize_product(product))

    return results[:20]


def fetch_product(url: str | None = None, provider: str | None = None) -> dict[str, Any] | None:
    _ = url, provider
    return None

