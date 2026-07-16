from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests

from .base import GearCatalogProvider

AMAZON_RESOURCES = [
    "Images.Primary.Large",
    "Images.Primary.Medium",
    "ItemInfo.Title",
    "ItemInfo.ByLineInfo",
    "ItemInfo.Features",
    "ItemInfo.ProductInfo",
    "OffersV2.Listings.Price",
    "OffersV2.Listings.Availability.Message",
]

SEARCH_INDEX_BY_CATEGORY = {
    "rod": "All",
    "reel": "All",
    "line": "All",
    "lure": "All",
    "terminal": "All",
    "misc": "All",
}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _amz_now() -> tuple[str, str]:
    now = datetime.utcnow()
    return now.strftime("%Y%m%d"), now.strftime("%Y%m%dT%H%M%SZ")


def _hash_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _aws4_signature(secret: str, date_stamp: str, region: str, service: str, string_to_sign: str) -> str:
    k_date = _sign(("AWS4" + secret).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    return hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()


def _extract_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("DisplayValue", "Value", "Text"):
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


def _extract_price(item: dict[str, Any]) -> str:
    listings = item.get("OffersV2", {}).get("Listings", [])
    if not isinstance(listings, list) or not listings:
        return ""
    price = listings[0].get("Price", {}) if isinstance(listings[0], dict) else {}
    return _extract_text(price.get("DisplayAmount") or price.get("Amount") or price.get("AmountInUSD"))


def _extract_availability(item: dict[str, Any]) -> str:
    listings = item.get("OffersV2", {}).get("Listings", [])
    if not isinstance(listings, list) or not listings:
        return ""
    availability = listings[0].get("Availability", {}) if isinstance(listings[0], dict) else {}
    return _extract_text(availability.get("Message") or availability.get("Type") or availability)


def _extract_features(item: dict[str, Any]) -> list[str]:
    features = (
        item.get("ItemInfo", {})
        .get("Features", {})
        .get("DisplayValues", [])
    )
    if not isinstance(features, list):
        return []
    return [str(feature).strip() for feature in features if str(feature).strip()]


class AmazonCatalogProvider(GearCatalogProvider):
    name = "Amazon"
    provider_id = "amazon"
    enabled = True
    requires_credentials = True

    def configured(self) -> bool:
        return all([
            _env("AI_AMAZON_PAAPI_ACCESS_KEY"),
            _env("AI_AMAZON_PAAPI_SECRET_KEY"),
            _env("AI_AMAZON_PAAPI_PARTNER_TAG"),
        ])

    def health(self) -> dict[str, Any]:
        health = super().health()
        configured = self.configured()
        health["enabled"] = configured and self.enabled
        health["configured"] = configured
        health["status"] = "ready" if configured else "missing credentials"
        health["icon"] = f"/static/gear/providers/{self.provider_id}.svg"
        health["endpoint"] = _env("AI_AMAZON_PAAPI_HOST", "webservices.amazon.com")
        return health

    def _request(self, body: dict[str, Any]) -> dict[str, Any] | None:
        access_key = _env("AI_AMAZON_PAAPI_ACCESS_KEY")
        secret_key = _env("AI_AMAZON_PAAPI_SECRET_KEY")
        partner_tag = _env("AI_AMAZON_PAAPI_PARTNER_TAG")
        marketplace = _env("AI_AMAZON_PAAPI_MARKETPLACE", "www.amazon.com")
        host = _env("AI_AMAZON_PAAPI_HOST", "webservices.amazon.com")
        region = _env("AI_AMAZON_PAAPI_REGION", "us-east-1")
        if not (access_key and secret_key and partner_tag):
            return None

        date_stamp, amz_datetime = _amz_now()
        service = "ProductAdvertisingAPI"
        target = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
        endpoint = f"https://{host}/paapi5/searchitems"
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        canonical_uri = "/paapi5/searchitems"
        canonical_querystring = ""
        canonical_headers = (
            f"content-type:application/json; charset=utf-8\n"
            f"host:{host}\n"
            f"x-amz-date:{amz_datetime}\n"
            f"x-amz-target:{target}\n"
        )
        signed_headers = "content-type;host;x-amz-date;x-amz-target"
        payload_hash = _hash_hex(payload)
        canonical_request = "\n".join([
            "POST",
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash,
        ])
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
        string_to_sign = "\n".join([
            algorithm,
            amz_datetime,
            credential_scope,
            _hash_hex(canonical_request),
        ])
        signature = _aws4_signature(secret_key, date_stamp, region, service, string_to_sign)
        authorization = (
            f"{algorithm} Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-Amz-Date": amz_datetime,
            "X-Amz-Target": target,
            "Authorization": authorization,
        }

        response = requests.post(endpoint, headers=headers, data=payload, timeout=(5, 15))
        response.raise_for_status()
        data = response.json()
        return data

    def search(self, query: str, category: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        query = str(query or "").strip()
        if not query or not self.configured():
            return []

        search_index = SEARCH_INDEX_BY_CATEGORY.get(str(category or "").lower(), "All")
        body = {
            "Keywords": query,
            "SearchIndex": search_index,
            "ItemCount": max(1, min(int(limit or 10), 10)),
            "PartnerTag": _env("AI_AMAZON_PAAPI_PARTNER_TAG"),
            "PartnerType": "Associates",
            "Marketplace": _env("AI_AMAZON_PAAPI_MARKETPLACE", "www.amazon.com"),
            "Resources": AMAZON_RESOURCES,
        }

        try:
            data = self._request(body)
        except Exception:
            return []

        if not isinstance(data, dict):
            return []

        items = data.get("SearchResult", {}).get("Items", [])
        if not isinstance(items, list):
            return []

        results: list[dict[str, Any]] = []
        for item in items[: max(1, min(int(limit or 10), 10))]:
            if not isinstance(item, dict):
                continue
            title = _extract_text(item.get("ItemInfo", {}).get("Title", {})) or _extract_text(item.get("Title", {}))
            byline = item.get("ItemInfo", {}).get("ByLineInfo", {}) if isinstance(item.get("ItemInfo", {}), dict) else {}
            brand = _extract_text(byline.get("Brand") or byline.get("Manufacturer"))
            image = (
                item.get("Images", {})
                .get("Primary", {})
                .get("Large", {})
                .get("URL")
                or item.get("Images", {})
                .get("Primary", {})
                .get("Medium", {})
                .get("URL")
                or ""
            )
            features = _extract_features(item)
            display_name = title or brand or "Amazon product"
            result = {
                "provider": self.provider_id,
                "provider_product_id": _extract_text(item.get("ASIN")),
                "source_name": self.name,
                "source_url": _extract_text(item.get("DetailPageURL")),
                "category": str(category or "misc").strip().lower() or "misc",
                "brand": brand,
                "model": title,
                "display_name": display_name,
                "image_url": image,
                "image_source": "amazon-paapi",
                "identifiers": {
                    "asin": _extract_text(item.get("ASIN")),
                },
                "specifications": {
                    "features": features,
                } if features else {},
                "price": _extract_price(item),
                "availability": _extract_availability(item),
                "confidence": "high",
                "raw_provider_data_cached": False,
            }
            results.append(result)
        return results
