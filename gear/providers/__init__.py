from .base import GearCatalogProvider
from .local_provider import LocalCatalogProvider
from .structured_data_provider import StructuredDataProvider
from .amazon_provider import AmazonCatalogProvider
from .walmart_provider import WalmartCatalogProvider

__all__ = [
    "GearCatalogProvider",
    "LocalCatalogProvider",
    "StructuredDataProvider",
    "AmazonCatalogProvider",
    "WalmartCatalogProvider",
]

