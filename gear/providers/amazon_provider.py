from __future__ import annotations

from .base import GearCatalogProvider


class AmazonCatalogProvider(GearCatalogProvider):
    name = "Amazon"
    provider_id = "amazon"
    enabled = False
    requires_credentials = True

