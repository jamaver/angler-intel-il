from __future__ import annotations

from .base import GearCatalogProvider


class WalmartCatalogProvider(GearCatalogProvider):
    name = "Walmart"
    provider_id = "walmart"
    enabled = False
    requires_credentials = True

