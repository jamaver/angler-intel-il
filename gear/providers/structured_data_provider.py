from __future__ import annotations

from typing import Any

from ..product_url_import import import_product_from_url
from .base import GearCatalogProvider


class StructuredDataProvider(GearCatalogProvider):
    name = "Structured product page"
    provider_id = "structured"
    enabled = True
    requires_credentials = False

    def search(self, query: str, category: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        query = str(query or "").strip()
        if not query.startswith(("http://", "https://")):
            return []
        imported = import_product_from_url(query, category=category or "misc", allow_remote_images=True)
        if not imported.get("ok"):
            return []
        product = imported.get("product")
        return [product] if isinstance(product, dict) else []

    def fetch_product(self, product_id: str | None = None, url: str | None = None) -> dict[str, Any] | None:
        _ = product_id
        if not url:
            return None
        result = import_product_from_url(url, allow_remote_images=True)
        if not result.get("ok"):
            return None
        product = result.get("product")
        return product if isinstance(product, dict) else None

