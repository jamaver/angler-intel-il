from __future__ import annotations

from typing import Any


class GearCatalogProvider:
    name = "Catalog provider"
    provider_id = "base"
    enabled = True
    requires_credentials = False

    def search(self, query: str, category: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        return []

    def fetch_product(self, product_id: str | None = None, url: str | None = None) -> dict[str, Any] | None:
        return None

    def health(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "icon": f"/static/gear/providers/{self.provider_id}.svg",
            "enabled": bool(self.enabled),
            "requires_credentials": bool(self.requires_credentials),
            "status": "enabled" if self.enabled else "disabled",
        }
