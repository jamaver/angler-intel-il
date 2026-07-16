from __future__ import annotations

import os
from typing import Any

import requests

from ..inventory import fallback_image_for
from .base import GearCatalogProvider


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _extract_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("displayValue", "value", "name", "title", "text", "label"):
            text = _extract_text(value.get(key))
            if text:
                return text
        return ""
    if isinstance(value, list):
        for item in value:
            text = _extract_text(item)
            if text:
                return text
        return ""
    return "" if value is None else str(value).strip()


def _extract_image(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("large", "medium", "small", "url", "src", "href"):
            text = _extract_image(value.get(key))
            if text:
                return text
        return ""
    if isinstance(value, list):
        for item in value:
            text = _extract_image(item)
            if text:
                return text
        return ""
    return "" if value is None else str(value).strip()


class WalmartCatalogProvider(GearCatalogProvider):
    name = "Walmart"
    provider_id = "walmart"
    enabled = True
    requires_credentials = True

    def configured(self) -> bool:
        return bool(_env("AI_WALMART_API_SEARCH_URL"))

    def health(self) -> dict[str, Any]:
        health = super().health()
        configured = self.configured()
        health["enabled"] = configured and self.enabled
        health["configured"] = configured
        health["status"] = "ready" if configured else "missing search URL"
        health["icon"] = f"/static/gear/providers/{self.provider_id}.svg"
        health["endpoint"] = _env("AI_WALMART_API_SEARCH_URL")
        return health

    def search(self, query: str, category: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        query = str(query or "").strip()
        search_url = _env("AI_WALMART_API_SEARCH_URL")
        if not query or not search_url:
            return []

        headers = {}
        bearer = _env("AI_WALMART_API_BEARER_TOKEN")
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        api_key = _env("AI_WALMART_API_KEY")
        if api_key:
            headers["WM_CONSUMER.ID"] = api_key

        params = {
            "query": query,
            "category": category or "",
            "limit": max(1, min(int(limit or 10), 10)),
        }

        try:
            response = requests.get(search_url, params=params, headers=headers, timeout=(5, 15))
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        items = []
        for key in ("items", "products", "data", "results"):
            value = data.get(key) if isinstance(data, dict) else None
            if isinstance(value, list):
                items = value
                break
        if not items and isinstance(data, dict) and isinstance(data.get("item"), dict):
            items = [data["item"]]

        results: list[dict[str, Any]] = []
        for item in items[: max(1, min(int(limit or 10), 10))]:
            if not isinstance(item, dict):
                continue
            title = _extract_text(item.get("name") or item.get("title") or item.get("productName"))
            brand = _extract_text(item.get("brand") or item.get("manufacturer"))
            image = _extract_image(item.get("image") or item.get("images") or item.get("primaryImage"))
            display_name = title or brand or "Walmart product"
            results.append({
                "provider": self.provider_id,
                "provider_product_id": _extract_text(item.get("itemId") or item.get("id") or item.get("sku") or item.get("upc")),
                "source_name": self.name,
                "source_url": _extract_text(item.get("url") or item.get("productUrl") or item.get("canonicalUrl")),
                "category": (category or "misc").lower() or "misc",
                "brand": brand,
                "model": title,
                "display_name": display_name,
                "image_url": image,
                "image_source": "walmart-api" if image else "",
                "identifiers": {
                    "sku": _extract_text(item.get("sku")),
                    "upc": _extract_text(item.get("upc")),
                },
                "specifications": {},
                "price": _extract_text(item.get("price") or item.get("salePrice") or item.get("currentPrice")),
                "availability": _extract_text(item.get("availability") or item.get("availabilityStatus") or item.get("stock")),
                "confidence": "medium" if image else "low",
                "raw_provider_data_cached": False,
            })
        return results
