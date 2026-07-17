from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .inventory import (
    catalog_cache_path,
    find_duplicate_items,
    fallback_image_for,
    list_items,
    search_items,
    _slug,
    _text,
)
from .product_url_import import import_product_from_url, normalize_structured_product
from .providers import AmazonCatalogProvider, GearCatalogProvider, LocalCatalogProvider, StructuredDataProvider, WalmartCatalogProvider
from .settings import load_settings

PROVIDER_REGISTRY: list[GearCatalogProvider] = [
    LocalCatalogProvider(),
    StructuredDataProvider(),
    WalmartCatalogProvider(),
    AmazonCatalogProvider(),
]


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
        "version": "v6.13-gear-intelligence-packing-catch-linking",
        "updated_at": _now(),
        "products": [],
    }


def provider_icon_for(provider_id: Any) -> str:
    key = _slug(_text(provider_id, "generic"))
    if key in {"manual", "cache", "local"}:
        return "/static/gear/providers/local.svg" if key == "local" else f"/static/gear/providers/{key}.svg"
    if key in {"structured", "amazon", "walmart"}:
        return f"/static/gear/providers/{key}.svg"
    return "/static/gear/providers/manual.svg"


def load_cache() -> dict[str, Any]:
    data = _read_json(catalog_cache_path(), _default_cache())
    if not isinstance(data, dict):
        data = _default_cache()
    data.setdefault("version", "v6.13-gear-intelligence-packing-catch-linking")
    data.setdefault("updated_at", _now())
    data["products"] = data.get("products") if isinstance(data.get("products"), list) else []
    return data


def save_cache(data: dict[str, Any]) -> None:
    payload = dict(data or {})
    payload.setdefault("version", "v6.13-gear-intelligence-packing-catch-linking")
    payload["updated_at"] = _now()
    payload["products"] = payload.get("products") if isinstance(payload.get("products"), list) else []
    _write_json(catalog_cache_path(), payload)


def normalize_product(raw_product: dict[str, Any]) -> dict[str, Any]:
    product = dict(raw_product or {})
    product.setdefault("provider", "cache")
    product.setdefault("provider_product_id", "")
    product.setdefault("brand", "")
    product.setdefault("model", "")
    product.setdefault("category", "misc")
    product["display_name"] = _text(product.get("display_name"), " ".join(part for part in [product.get("brand"), product.get("model")] if _text(part)))
    product["specifications"] = product.get("specifications") if isinstance(product.get("specifications"), dict) else {}
    product["identifiers"] = product.get("identifiers") if isinstance(product.get("identifiers"), dict) else {}
    product["image_url"] = _text(product.get("image_url"), "")
    product["image_source"] = _text(product.get("image_source"), "")
    product["source_url"] = _text(product.get("source_url"), "")
    product["source_name"] = _text(product.get("source_name"), "Catalog cache")
    product["confidence"] = _text(product.get("confidence"), "low").lower()
    product["retrieved_at"] = _text(product.get("retrieved_at"), _now())
    product["query_key"] = _slug(" ".join(part for part in [product.get("brand"), product.get("model"), product.get("display_name")] if _text(part)))
    product["image"] = _text(product.get("image"), product["image_url"] or fallback_image_for(product.get("category"), product.get("subtype")))
    product["provider_icon"] = _text(product.get("provider_icon"), provider_icon_for(product.get("provider")))
    for key in (
        "description",
        "import_summary",
        "product_summary",
        "imported_from_text",
        "field_sources",
        "length_ft",
        "length_label",
        "power",
        "action",
        "pieces",
        "lure_weight_min_oz",
        "lure_weight_max_oz",
        "line_rating_min_lb",
        "line_rating_max_lb",
        "reel_type",
        "gear_ratio",
        "max_drag_lb",
        "line_capacity",
        "weight_oz",
        "handedness",
        "line_type",
        "strength_lb",
        "diameter_equivalent",
        "color",
        "length_yd",
        "lure_type",
        "hook_size",
        "depth_min_ft",
        "depth_max_ft",
        "quantity",
        "subtype",
        "size",
        "technique_tags",
        "species_tags",
    ):
        if key in product and product.get(key) not in (None, "", [], {}):
            product[key] = product.get(key)
    if not product["image_url"] and product["image"].startswith("http"):
        product["image_url"] = product["image"]
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
            " ".join(map(str, product.get("identifiers", {}).values())) if isinstance(product.get("identifiers"), dict) else "",
        ]).lower()
        if q and q not in blob:
            continue
        if category and category != _text(product.get("category"), "").lower():
            continue
        results.append(normalize_product(product))

    return results[:20]


def search_local_catalog(query: str, category: str = "", limit: int = 20) -> dict[str, list[dict[str, Any]]]:
    owned = search_items(query=query, category=category, status="owned", limit=limit)
    cached = search_products(query=query, category=category)
    return {
        "owned": [dict(item, duplicate_matches=find_duplicate_items(item)) for item in owned],
        "cached": [dict(item, duplicate_matches=find_duplicate_items(item)) for item in cached if item],
    }


def _enabled_online_providers() -> list[GearCatalogProvider]:
    settings = load_settings()
    enabled = settings.get("enabled_providers") if isinstance(settings.get("enabled_providers"), dict) else {}
    online_enabled = bool(settings.get("online_lookup_enabled"))

    providers: list[GearCatalogProvider] = []
    for provider in PROVIDER_REGISTRY:
        if provider.provider_id == "local":
            continue
        if not online_enabled:
            continue
        if enabled.get(provider.provider_id):
            providers.append(provider)
    return providers


def available_providers() -> list[dict[str, Any]]:
    providers = [provider.health() for provider in PROVIDER_REGISTRY]
    settings = load_settings()
    for provider in providers:
        if provider.get("provider_id") in settings.get("enabled_providers", {}):
            provider["enabled"] = bool(settings["enabled_providers"].get(provider["provider_id"]))
        provider.setdefault("icon", provider_icon_for(provider.get("provider_id")))
    return providers


def search_gear_catalog(query: str, category: str = "", scope: str = "both", limit: int = 20) -> dict[str, Any]:
    scope = _text(scope, "both").lower()
    category = _text(category, "").lower()
    query = _text(query, "").strip()
    local = {"owned": [], "cached": []}
    online: list[dict[str, Any]] = []
    messages: list[str] = []

    if scope in {"both", "local"}:
        local = search_local_catalog(query, category=category, limit=limit)

    if scope in {"both", "online"}:
        if query and query.startswith(("http://", "https://")):
            imported = import_product_from_url(query, category=category or "misc", allow_remote_images=load_settings().get("allow_remote_images", False))
            if imported.get("ok") and isinstance(imported.get("product"), dict):
                product = normalize_product(imported["product"])
                cache_product(product)
                product["duplicate_matches"] = find_duplicate_items(product)
                product["match_group"] = "online"
                product["provider_icon"] = provider_icon_for(product.get("provider"))
                online.append(product)
            else:
                messages.append(imported.get("error", "Unable to import the product URL."))
        else:
            for provider in _enabled_online_providers():
                try:
                    provider_results = provider.search(query=query, category=category or None, limit=limit)
                except Exception as exc:
                    messages.append(f"{provider.name} search failed: {exc}")
                    continue
                for result in provider_results:
                    if not isinstance(result, dict):
                        continue
                    product = normalize_product(result)
                    product["duplicate_matches"] = find_duplicate_items(product)
                    product["match_group"] = "online"
                    product["provider_icon"] = provider_icon_for(product.get("provider"))
                    online.append(product)

            if not _enabled_online_providers() and query:
                messages.append("Online product sources are disabled or unavailable. You can still use local search, manual entry, or paste a product URL.")

    return {
        "ok": True,
        "version": "v6.13-gear-intelligence-packing-catch-linking",
        "query": query,
        "category": category,
        "scope": scope,
        "local": {
            "owned": local.get("owned", []),
            "cached": local.get("cached", []),
            "count": len(local.get("owned", [])) + len(local.get("cached", [])),
        },
        "online": {
            "matches": online[:limit],
            "count": len(online[:limit]),
        },
        "messages": messages,
        "providers": available_providers(),
    }


def fetch_product(url: str | None = None, provider: str | None = None, category: str = "misc", allow_remote_images: bool = True) -> dict[str, Any] | None:
    url = _text(url, "")
    if not url:
        return None

    if provider and provider != "structured":
        for item in PROVIDER_REGISTRY:
            if item.provider_id == provider:
                result = item.fetch_product(url=url)
                if result:
                    return normalize_product(result)
                return None

    imported = import_product_from_url(url, category=category, allow_remote_images=allow_remote_images)
    if not imported.get("ok"):
        return None
    product = imported.get("product")
    if not isinstance(product, dict):
        return None
    normalized = normalize_product(product)
    if normalized.get("source_url") or normalized.get("image_url"):
        cache_product(normalized)
    return normalized
