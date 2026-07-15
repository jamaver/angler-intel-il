from __future__ import annotations

from typing import Any

from ..inventory import find_duplicate_items, fallback_image_for, search_items
from .base import GearCatalogProvider


class LocalCatalogProvider(GearCatalogProvider):
    name = "Local locker"
    provider_id = "local"
    enabled = True
    requires_credentials = False

    def search(self, query: str, category: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        results = []
        owned = search_items(query=query, category=category or "", status="owned", limit=limit)
        cached = search_items(query=query, category=category or "", status="", limit=limit)
        seen: set[str] = set()

        for item in owned:
            item = dict(item)
            item["source_name"] = item.get("source_name") or "My Tackle Locker"
            item["source"] = item.get("source") or "manual"
            item["match_group"] = "owned"
            item["duplicate_matches"] = find_duplicate_items(item)
            item["fallback_image"] = item.get("fallback_image") or fallback_image_for(item.get("category"), item.get("subtype"))
            results.append(item)
            seen.add(str(item.get("id") or item.get("display_name") or ""))

        for item in cached:
            key = str(item.get("id") or item.get("query_key") or item.get("display_name") or "")
            if key in seen:
                continue
            item = dict(item)
            item["source_name"] = item.get("source_name") or "Catalog cache"
            item["source"] = item.get("source") or "cache"
            item["match_group"] = "cached"
            item["duplicate_matches"] = find_duplicate_items(item)
            item["fallback_image"] = item.get("fallback_image") or fallback_image_for(item.get("category"), item.get("subtype"))
            results.append(item)

        return results[:limit]

