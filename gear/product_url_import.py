from __future__ import annotations

import ipaddress
import json
import socket
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from .inventory import fallback_image_for, _slug, _text

MAX_BYTES = 1_500_000
ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _blocked_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any([
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_reserved,
        ip.is_multicast,
        ip.is_unspecified,
    ])


def _resolve_host(hostname: str) -> list[str]:
    addresses: list[str] = []
    try:
        infos = socket.getaddrinfo(hostname, None)
    except Exception:
        return addresses
    for info in infos:
        sockaddr = info[4]
        if sockaddr and sockaddr[0]:
            addresses.append(sockaddr[0])
    return sorted(set(addresses))


class _ProductHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.meta_tags: list[dict[str, str]] = []
        self.jsonld_scripts: list[str] = []
        self._in_title = False
        self._in_script = False
        self._script_type = ""
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            self.meta_tags.append(attr_map)
        elif tag == "script":
            self._in_script = True
            self._script_type = attr_map.get("type", "").lower()
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_script:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            if self._script_type == "application/ld+json":
                self.jsonld_scripts.append("".join(self._script_parts))
            self._in_script = False
            self._script_type = ""
            self._script_parts = []

    @property
    def title_text(self) -> str:
        return unescape("".join(self.title_parts).strip())


def validate_product_url(url: str) -> tuple[bool, str]:
    url = _text(url, "")
    if not url:
        return False, "Paste a product URL first."
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, "Only http and https URLs are allowed."
    if not parsed.hostname:
        return False, "The URL must include a hostname."
    hostname = parsed.hostname.lower()
    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(".local"):
        return False, "Local and loopback addresses are blocked."

    if parsed.hostname.replace(".", "").isdigit():
        if _blocked_ip(parsed.hostname):
            return False, "Private or loopback IPs are blocked."

    for address in _resolve_host(parsed.hostname):
        if _blocked_ip(address):
            return False, "Private or loopback IPs are blocked."
    return True, ""


def fetch_product_page(url: str) -> dict[str, Any]:
    ok, error = validate_product_url(url)
    if not ok:
        return {"ok": False, "error": error}

    try:
        response = requests.get(
            url,
            timeout=(5, 10),
            headers={"User-Agent": "AnglerIntelGearImport/1.0"},
            stream=True,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return {"ok": False, "error": f"Request failed: {exc}"}

    if response.history and len(response.history) > 3:
        return {"ok": False, "error": "Too many redirects."}

    final_url = response.url or url
    ok, error = validate_product_url(final_url)
    if not ok:
      # final target must remain safe as well
        return {"ok": False, "error": f"Blocked redirect target: {error}"}

    content_type = (response.headers.get("content-type") or "").lower()
    if content_type and not any(token in content_type for token in ("text/html", "application/xhtml+xml", "application/xml")):
        return {"ok": False, "error": f"Unsupported content type: {content_type.split(';')[0] or content_type}"}

    body = bytearray()
    try:
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            body.extend(chunk)
            if len(body) > MAX_BYTES:
                return {"ok": False, "error": "Product page is too large to import safely."}
    finally:
        response.close()

    encoding = response.encoding or "utf-8"
    html = body.decode(encoding, errors="replace")
    return {
        "ok": True,
        "url": final_url,
        "html": html,
        "content_type": content_type.split(";")[0] if content_type else "",
        "retrieved_at": _now(),
    }


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            text = _first_text(item)
            if text:
                return text
        return ""
    if isinstance(value, dict):
        for key in ("name", "title", "text", "@id", "url"):
            text = _first_text(value.get(key))
            if text:
                return text
        return ""
    return unescape(_text(value, ""))


def _find_product_nodes(blob: Any) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    if isinstance(blob, dict):
        if str(blob.get("@type", "")).lower() == "product":
            nodes.append(blob)
        graph = blob.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                if isinstance(item, dict):
                    nodes.extend(_find_product_nodes(item))
    elif isinstance(blob, list):
        for item in blob:
            if isinstance(item, dict):
                nodes.extend(_find_product_nodes(item))
    return nodes


def extract_jsonld_product(html: str) -> dict[str, Any]:
    parser = _ProductHTMLParser()
    parser.feed(html or "")
    nodes: list[dict[str, Any]] = []
    for text in parser.jsonld_scripts:
        if not text:
            continue
        try:
            blob = json.loads(text)
        except Exception:
            continue
        nodes.extend(_find_product_nodes(blob))

    if not nodes:
        return {}

    product = nodes[0]
    brand = _first_text(product.get("brand"))
    name = _first_text(product.get("name")) or _first_text(product.get("headline"))
    images = product.get("image")
    if isinstance(images, list):
        image = _first_text(images[0]) if images else ""
    else:
        image = _first_text(images)

    specs: dict[str, Any] = {}
    for prop in product.get("additionalProperty", []) if isinstance(product.get("additionalProperty"), list) else []:
        if not isinstance(prop, dict):
            continue
        key = _slug(prop.get("name") or prop.get("propertyID") or prop.get("valueReference") or "property")
        value = prop.get("value")
        if value is not None:
            specs[key] = _first_text(value) if not isinstance(value, (str, int, float, bool)) else value

    identifiers = {
        "sku": _first_text(product.get("sku")),
        "mpn": _first_text(product.get("mpn")),
        "gtin": _first_text(product.get("gtin")),
        "gtin13": _first_text(product.get("gtin13")),
        "gtin14": _first_text(product.get("gtin14")),
        "upc": _first_text(product.get("upc")),
    }
    identifiers = {key: value for key, value in identifiers.items() if value}

    offers = product.get("offers") if isinstance(product.get("offers"), dict) else {}
    price = offers.get("price") if isinstance(offers, dict) else None
    availability = _first_text(offers.get("availability")) if isinstance(offers, dict) else ""

    return {
        "provider": "structured",
        "provider_product_id": _first_text(product.get("@id") or product.get("url") or product.get("sku")),
        "source_name": "Structured product page",
        "source_url": _first_text(product.get("url")),
        "brand": brand,
        "model": _first_text(product.get("model")) or name,
        "display_name": name or "Imported product",
        "image_url": image,
        "identifiers": identifiers,
        "specifications": specs,
        "price": price,
        "availability": availability,
        "confidence": "high",
        "raw_provider_data_cached": False,
        "retrieved_at": _now(),
        "raw_product_type": _first_text(product.get("@type")),
        "raw_product_name": name,
        "raw_product_brand": brand,
    }


def normalize_structured_product(data: dict[str, Any], source_url: str = "", category: str = "misc", allow_remote_images: bool = True) -> dict[str, Any]:
    product = dict(data or {})
    image_url = _text(product.get("image_url"), "")
    if not allow_remote_images:
        image_url = ""

    brand = _text(product.get("brand"), "")
    model = _text(product.get("model"), "")
    display_name = _text(product.get("display_name"), "")
    if not display_name:
        display_name = " ".join(part for part in [brand, model] if _text(part)) or "Imported product"

    specs = product.get("specifications") if isinstance(product.get("specifications"), dict) else {}
    identifiers = product.get("identifiers") if isinstance(product.get("identifiers"), dict) else {}

    normalized = {
        "provider": _text(product.get("provider"), "structured"),
        "provider_product_id": _text(product.get("provider_product_id"), _slug(display_name)),
        "source_name": _text(product.get("source_name"), "Structured product page"),
        "source_url": _text(product.get("source_url"), source_url),
        "category": _text(category, "misc") or "misc",
        "brand": brand,
        "model": model,
        "display_name": display_name,
        "image_url": image_url,
        "identifiers": identifiers,
        "specifications": specs,
        "price": product.get("price"),
        "availability": _text(product.get("availability"), ""),
        "retrieved_at": _text(product.get("retrieved_at"), _now()),
        "confidence": _text(product.get("confidence"), "medium").lower(),
        "raw_provider_data_cached": bool(product.get("raw_provider_data_cached", False)),
        "image_source": "structured-product-page" if image_url else "fallback",
        "image": image_url or fallback_image_for(category),
    }
    return normalized


def import_product_from_url(url: str, category: str = "misc", allow_remote_images: bool = True) -> dict[str, Any]:
    result = fetch_product_page(url)
    if not result.get("ok"):
        return result

    html = result.get("html", "")
    parsed = extract_jsonld_product(html)
    if not parsed:
        parser = _ProductHTMLParser()
        parser.feed(html or "")
        title = _first_text(parser.title_text)
        og_title = ""
        og_image = ""
        for meta in parser.meta_tags:
            prop = _text(meta.get("property") or meta.get("name"), "").lower()
            if prop in {"og:title", "twitter:title"} and not og_title:
                og_title = _text(meta.get("content"), "")
            if prop in {"og:image", "twitter:image"} and not og_image:
                og_image = _text(meta.get("content"), "")
        parsed = {
            "provider": "structured",
            "provider_product_id": _slug(title or og_title or url),
            "source_name": "Structured product page",
            "source_url": url,
            "brand": "",
            "model": title or og_title or "Imported product",
            "display_name": title or og_title or "Imported product",
            "image_url": og_image,
            "identifiers": {},
            "specifications": {},
            "price": None,
            "availability": "",
            "confidence": "low",
            "raw_provider_data_cached": False,
            "retrieved_at": result.get("retrieved_at"),
        }

    normalized = normalize_structured_product(parsed, source_url=result.get("url", url), category=category, allow_remote_images=allow_remote_images)
    normalized["source_page_url"] = result.get("url", url)
    normalized["source_page_retrieved_at"] = result.get("retrieved_at")
    return {
        "ok": True,
        "product": normalized,
        "messages": [],
    }
