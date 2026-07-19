from __future__ import annotations

import ipaddress
import json
import socket
import re
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
GENERIC_PAGE_MARKERS = (
    "site maintenance",
    "maintenance",
    "page not found",
    "not found",
    "temporarily unavailable",
    "access denied",
    "coming soon",
    "home page",
)


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
        self.text_parts: list[str] = []
        self._in_title = False
        self._in_script = False
        self._in_style = False
        self._script_type = ""
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            self.meta_tags.append(attr_map)
        elif tag == "style":
            self._in_style = True
        elif tag == "script":
            self._in_script = True
            self._script_type = attr_map.get("type", "").lower()
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if not self._in_script and not self._in_style:
            text = unescape(" ".join(data.split()))
            if text:
                self.text_parts.append(text)
        if self._in_script:
            self._script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        elif tag == "style":
            self._in_style = False
        elif tag == "script":
            if self._script_type == "application/ld+json":
                self.jsonld_scripts.append("".join(self._script_parts))
            self._in_script = False
            self._script_type = ""
            self._script_parts = []

    @property
    def title_text(self) -> str:
        return unescape("".join(self.title_parts).strip())

    @property
    def content_text(self) -> str:
        return " ".join(self.text_parts).strip()


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


def _all_text(*parts: Any) -> str:
    items: list[str] = []
    for part in parts:
        text = _text(part, "") if not isinstance(part, dict) else json.dumps(part, ensure_ascii=False)
        if text:
            items.append(text)
    return " ".join(items).strip()


def _first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1) if match.groups() else match.group(0)
    return ""


def _normalize_number(text: str) -> str:
    return text.replace(" ", "").replace(",", "").strip()


def _token_to_float(token: str) -> float | None:
    token = _normalize_number(token)
    if not token:
        return None
    if "/" in token and not token.replace("/", "").replace(".", "").isdigit():
        return None
    if "/" in token:
        parts = token.split("/")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit() and int(parts[1]) != 0:
            return float(int(parts[0]) / int(parts[1]))
    try:
        return float(token)
    except Exception:
        return None


def _parse_length_value(text: str) -> tuple[float | None, str]:
    compact = _normalize_number(text.lower().replace("feet", "ft").replace("foot", "ft").replace("inches", "in").replace("inch", "in"))
    match = re.search(r"(\d+(?:\.\d+)?)\s*ft(?:\s*(\d+(?:\.\d+)?)\s*in)?", compact)
    if match:
        feet = float(match.group(1))
        inches = float(match.group(2) or 0)
        total = round(feet + (inches / 12.0), 2)
        label = f"{int(feet) if feet.is_integer() else feet:g}'{int(inches) if inches.is_integer() else inches:g}\""
        return total, label
    match = re.search(r"(\d+)'(\d+)?\"?", text)
    if match:
        feet = float(match.group(1))
        inches = float(match.group(2) or 0)
        total = round(feet + (inches / 12.0), 2)
        label = f"{int(feet)}'{int(inches) if inches else 0}\""
        return total, label
    return None, ""


def _parse_float_range(text: str, unit: str) -> tuple[float | None, float | None]:
    patterns = [
        rf"([\d./]+)\s*{re.escape(unit)}\s*(?:-|to|–|—)\s*([\d./]+)\s*{re.escape(unit)}",
        rf"([\d./]+)\s*(?:-|to|–|—)\s*([\d./]+)\s*{re.escape(unit)}",
        rf"([\d./]+)\s*{re.escape(unit)}\s*(?:-|to|–|—)\s*([\d./]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            left = _token_to_float(match.group(1))
            right = _token_to_float(match.group(2))
            return left, right
    single = re.search(rf"([\d./]+)\s*{re.escape(unit)}", text, re.IGNORECASE)
    if single:
        value = _token_to_float(single.group(1))
        return value, value
    return None, None


def _parse_int_range(text: str, unit: str) -> tuple[int | None, int | None]:
    patterns = [
        rf"(\d+)\s*{re.escape(unit)}\s*(?:-|to|–|—)\s*(\d+)\s*{re.escape(unit)}",
        rf"(\d+)\s*(?:-|to|–|—)\s*(\d+)\s*{re.escape(unit)}",
        rf"(\d+)\s*{re.escape(unit)}\s*(?:-|to|–|—)\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))
    single = re.search(rf"(\d+)\s*{re.escape(unit)}", text, re.IGNORECASE)
    if single:
        value = int(single.group(1))
        return value, value
    return None, None


def _infer_category(title: str, text: str, category: str) -> str:
    known = {"rod", "reel", "line", "lure", "terminal"}
    if category in known:
        return category
    blob = f"{title} {text}".lower()
    if any(token in blob for token in ("rod", "blank", "casting rod", "spinning rod")):
        return "rod"
    if any(token in blob for token in ("reel", "baitcaster", "spinning reel")):
        return "reel"
    if any(token in blob for token in ("line", "braid", "fluorocarbon", "monofilament", "mono")):
        return "line"
    if any(token in blob for token in ("hook", "jig head", "swivel", "weight", "snap", "terminal")):
        return "terminal"
    if any(token in blob for token in ("spinnerbait", "crankbait", "topwater", "swimbait", "frog", "jig", "worm", "plastic", "lure", "bait")):
        return "lure"
    return "misc"


def _infer_text_tags(text: str) -> tuple[list[str], list[str]]:
    lower = text.lower()
    technique_map = {
        "spinnerbait": "spinnerbait",
        "jig": "jig",
        "chatterbait": "chatterbait",
        "crankbait": "crankbait",
        "topwater": "topwater",
        "finesse": "finesse",
        "drop shot": "drop_shot",
        "dropshot": "drop_shot",
        "texas rig": "texas_rig",
        "carolina rig": "carolina_rig",
        "swimbait": "swimbait",
        "frog": "frog",
        "worm": "soft_plastic_worm",
        "live bait": "live_bait",
    }
    species_map = {
        "bass": "largemouth_bass",
        "largemouth": "largemouth_bass",
        "smallmouth": "smallmouth_bass",
        "crappie": "crappie",
        "bluegill": "bluegill",
        "panfish": "bluegill",
        "catfish": "channel_catfish",
        "trout": "rainbow_trout",
        "walleye": "walleye",
        "sauger": "sauger",
        "white bass": "white_bass",
        "pike": "northern_pike",
        "musky": "northern_pike",
        "muskie": "northern_pike",
    }
    techniques = [value for key, value in technique_map.items() if key in lower]
    species = [value for key, value in species_map.items() if key in lower]
    return sorted(set(techniques)), sorted(set(species))


def _infer_product_fields(product: dict[str, Any], text: str, category_hint: str) -> dict[str, Any]:
    title = _text(product.get("display_name") or product.get("model") or product.get("raw_product_name"), "")
    blob = _all_text(title, product.get("description"), text, product.get("specifications"), product.get("identifiers"))
    category = _infer_category(title, blob, category_hint)
    product["category"] = category
    field_sources = product.get("field_sources") if isinstance(product.get("field_sources"), dict) else {}

    if category == "rod":
        length_ft, length_label = _parse_length_value(blob)
        if length_ft is not None:
            product.setdefault("length_ft", length_ft)
            field_sources.setdefault("length_ft", "page_text")
        if length_label:
            product.setdefault("length_label", length_label)
            field_sources.setdefault("length_label", "page_text")
        power = _first_match(blob, [r"\b(extra light|ultra light|ultralight|light medium|medium light|medium heavy|extra heavy|heavy|medium)\b"])
        action = _first_match(blob, [r"\b(extra fast|fast|moderate fast|moderate|slow)\b"])
        if power:
            product.setdefault("power", power.lower().replace(" ", "_"))
            field_sources.setdefault("power", "page_text")
        if action:
            product.setdefault("action", action.lower().replace(" ", "_"))
            field_sources.setdefault("action", "page_text")
        lure_min, lure_max = _parse_float_range(blob, "oz")
        if lure_min is not None:
            product.setdefault("lure_weight_min_oz", lure_min)
            field_sources.setdefault("lure_weight_min_oz", "page_text")
        if lure_max is not None:
            product.setdefault("lure_weight_max_oz", lure_max)
            field_sources.setdefault("lure_weight_max_oz", "page_text")
        line_min, line_max = _parse_int_range(blob, "lb")
        if line_min is not None:
            product.setdefault("line_rating_min_lb", line_min)
            field_sources.setdefault("line_rating_min_lb", "page_text")
        if line_max is not None:
            product.setdefault("line_rating_max_lb", line_max)
            field_sources.setdefault("line_rating_max_lb", "page_text")
        pieces = _first_match(blob, [r"\b(\d+)\s*(?:piece|pc|pcs|pce|sections?)\b"])
        if pieces:
            product.setdefault("pieces", int(pieces))
            field_sources.setdefault("pieces", "page_text")
        techniques, species = _infer_text_tags(blob)
        if techniques:
            product.setdefault("technique_tags", techniques)
            field_sources.setdefault("technique_tags", "page_text")
        if species:
            product.setdefault("species_tags", species)
            field_sources.setdefault("species_tags", "page_text")

    elif category == "reel":
        reel_type = _first_match(blob, [r"\b(baitcasting|spinning|spincast|conventional|fly)\b"])
        gear_ratio = _first_match(blob, [r"\b(\d+(?:\.\d+)?)\s*:\s*1\b"])
        max_drag = _first_match(blob, [r"\b(?:max\s*)?drag\s*(\d+(?:\.\d+)?)\s*lb\b"])
        handedness = _first_match(blob, [r"\b(left|right)\s*hand(?:ed)?\b"])
        weight = _first_match(blob, [r"\b(\d+(?:\.\d+)?)\s*oz\b"])
        if reel_type:
            product.setdefault("reel_type", reel_type.replace(" ", "_"))
            field_sources.setdefault("reel_type", "page_text")
        if gear_ratio:
            product.setdefault("gear_ratio", float(gear_ratio))
            field_sources.setdefault("gear_ratio", "page_text")
        if max_drag:
            product.setdefault("max_drag_lb", float(max_drag))
            field_sources.setdefault("max_drag_lb", "page_text")
        if handedness:
            product.setdefault("handedness", handedness)
            field_sources.setdefault("handedness", "page_text")
        if weight:
            product.setdefault("weight_oz", float(weight))
            field_sources.setdefault("weight_oz", "page_text")
        line_capacity = _first_match(blob, [r"\b\d+\s*lb\s*/\s*\d+\s*yd\b", r"\b\d+\s*yd\s*/\s*\d+\s*lb\b"])
        if line_capacity:
            product.setdefault("line_capacity", line_capacity)
            field_sources.setdefault("line_capacity", "page_text")

    elif category == "line":
        line_type = _first_match(blob, [r"\b(braid|fluorocarbon|mono|monofilament|nylon|copolymer)\b"])
        strength = _first_match(blob, [r"\b(\d+)\s*lb\b"])
        diameter = _first_match(blob, [r"\b(\d+(?:\.\d+)?)\s*(?:in|inch|inches|mm)\b"])
        color = _first_match(blob, [r"\b(moss green|green|clear|blue|white|red|yellow|orange|black)\b"])
        length_yd = _first_match(blob, [r"\b(\d+)\s*yd\b"])
        if line_type:
            product.setdefault("line_type", line_type.replace(" ", "_"))
            field_sources.setdefault("line_type", "page_text")
        if strength:
            product.setdefault("strength_lb", int(strength))
            field_sources.setdefault("strength_lb", "page_text")
        if diameter:
            product.setdefault("diameter_equivalent", diameter)
            field_sources.setdefault("diameter_equivalent", "page_text")
        if color:
            product.setdefault("color", color.replace(" ", "_"))
            field_sources.setdefault("color", "page_text")
        if length_yd:
            product.setdefault("length_yd", int(length_yd))
            field_sources.setdefault("length_yd", "page_text")

    elif category == "lure":
        lure_type = _first_match(blob, [r"\b(spinnerbait|crankbait|swimbait|topwater popper|popper|frog|spoon|inline spinner|spinner|drop shot|dropshot|jig|worm|soft plastic|stick bait|senko|buzzbait|chatterbait)\b"])
        color = _first_match(blob, [r"\b(green pumpkin|black blue|black/blue|black and blue|watermelon red|junebug|shad|natural shad|chartreuse white|chartreuse black back|white pearl|pearl white|bluegill|firetiger|bone|chrome blue|gold|silver|green frog|frog green|leopard frog|brown frog|brown orange|craw|pbj|peanut butter jelly|morning dawn)\b"])
        weight_min, weight_max = _parse_float_range(blob, "oz")
        hook = _first_match(blob, [r"\b(\d+(?:/\d+)?(?:/\d+)?)\s*(?:hook|hooks?)\b"])
        depth_min, depth_max = _parse_int_range(blob, "ft")
        techniques, species = _infer_text_tags(blob)
        if lure_type:
            product.setdefault("lure_type", lure_type.replace(" ", "_"))
            field_sources.setdefault("lure_type", "page_text")
        if color:
            product.setdefault("color", color.replace(" ", "_"))
            field_sources.setdefault("color", "page_text")
        if weight_min is not None:
            product.setdefault("weight_oz", weight_min)
            field_sources.setdefault("weight_oz", "page_text")
        if hook:
            product.setdefault("hook_size", hook)
            field_sources.setdefault("hook_size", "page_text")
        if depth_min is not None:
            product.setdefault("depth_min_ft", depth_min)
            field_sources.setdefault("depth_min_ft", "page_text")
        if depth_max is not None:
            product.setdefault("depth_max_ft", depth_max)
            field_sources.setdefault("depth_max_ft", "page_text")
        if techniques:
            product.setdefault("technique_tags", techniques)
            field_sources.setdefault("technique_tags", "page_text")
        if species:
            product.setdefault("species_tags", species)
            field_sources.setdefault("species_tags", "page_text")

    elif category == "terminal":
        subtype = _first_match(blob, [r"\b(hook|weight|swivel|snap|jig head|jighead|leader)\b"])
        if subtype:
            product.setdefault("subtype", subtype.replace(" ", "_"))
            field_sources.setdefault("subtype", "page_text")
        size = _first_match(blob, [r"\b(\d+(?:/\d+)?(?:/\d+)?(?:/\d+)?)\b"])
        if size:
            product.setdefault("size", size)
            field_sources.setdefault("size", "page_text")
        weight_min, _ = _parse_float_range(blob, "oz")
        if weight_min is not None:
            product.setdefault("weight_oz", weight_min)
            field_sources.setdefault("weight_oz", "page_text")
        quantity = _first_match(blob, [r"\b(\d+)\s*(?:count|pack|pieces|pcs|qty)\b"])
        if quantity:
            product.setdefault("quantity", int(quantity))
            field_sources.setdefault("quantity", "page_text")

    product["import_summary"] = "Imported product details were inferred from page metadata and page text."
    product["imported_from_text"] = blob[:1200]
    if field_sources:
        product["field_sources"] = field_sources
    return product


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
        "description": _first_text(product.get("description")),
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
    generic_page = bool(product.get("page_is_generic"))
    image_url = _text(product.get("image_url"), "")
    if not allow_remote_images:
        image_url = ""

    brand = _text(product.get("brand"), "")
    model = _text(product.get("model"), "")
    display_name = _text(product.get("display_name"), "")
    if generic_page:
        brand = ""
        model = ""
        display_name = ""
    if not display_name:
        display_name = " ".join(part for part in [brand, model] if _text(part)) or "Imported product"

    specs = product.get("specifications") if isinstance(product.get("specifications"), dict) else {}
    identifiers = product.get("identifiers") if isinstance(product.get("identifiers"), dict) else {}

    normalized = {
        "provider": _text(product.get("provider"), "structured"),
        "provider_product_id": _text(product.get("provider_product_id"), _slug(display_name)),
        "source_name": _text(product.get("source_name"), "Structured product page"),
        "source_url": _text(product.get("source_url"), source_url),
        "category": _text(product.get("category"), _text(category, "misc")) or "misc",
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
        "description": _text(product.get("description"), ""),
        "import_summary": _text(product.get("import_summary"), ""),
        "product_summary": _text(product.get("product_summary"), ""),
        "field_sources": product.get("field_sources") if isinstance(product.get("field_sources"), dict) else {},
    }
    for key in (
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
        "imported_from_text",
        "product_summary",
        "field_sources",
    ):
        if key in product and product.get(key) not in (None, "", [], {}):
            normalized[key] = product.get(key)
    return normalized


def import_product_from_url(url: str, category: str = "misc", allow_remote_images: bool = True) -> dict[str, Any]:
    result = fetch_product_page(url)
    if not result.get("ok"):
        return result

    html = result.get("html", "")
    parsed = extract_jsonld_product(html)
    parser = _ProductHTMLParser()
    parser.feed(html or "")
    if not parsed:
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
            "field_sources": {},
        }
    parsed["description"] = _text(parsed.get("description"), parser.content_text)
    page_blob = " ".join(part for part in [
        _first_text(parsed.get("raw_product_name")),
        parser.title_text,
        parser.content_text,
        parsed.get("description"),
    ] if _text(part)).lower()
    if any(marker in page_blob for marker in GENERIC_PAGE_MARKERS):
        parsed["brand"] = ""
        parsed["model"] = ""
        parsed["display_name"] = ""
        parsed["product_summary"] = ""
        parsed["import_summary"] = ""
        parsed["confidence"] = "low"
        parsed["page_is_generic"] = True
        parsed.setdefault("field_sources", {})
        parsed["field_sources"].setdefault("brand", "generic_page_detected")
        parsed["field_sources"].setdefault("model", "generic_page_detected")
        parsed["field_sources"].setdefault("display_name", "generic_page_detected")
    if not isinstance(parsed.get("field_sources"), dict):
        parsed["field_sources"] = {}
    if parsed.get("brand"):
        parsed["field_sources"].setdefault("brand", "page_metadata")
    if parsed.get("model"):
        parsed["field_sources"].setdefault("model", "page_metadata")
    if parsed.get("display_name"):
        parsed["field_sources"].setdefault("display_name", "page_metadata")
    if parsed.get("image_url"):
        parsed["field_sources"].setdefault("image_url", "page_metadata")
    parsed = _infer_product_fields(parsed, parser.content_text, category)

    title_text = _text(parsed.get("display_name") or parsed.get("raw_product_name") or parser.title_text, "")
    brand_text = _text(parsed.get("brand"), "")
    if not brand_text and title_text and not parsed.get("page_is_generic"):
        title_tokens = [token.strip() for token in title_text.split() if token.strip()]
        if len(title_tokens) >= 2 and not title_tokens[0].isdigit() and not title_tokens[1].isdigit():
            parsed["brand"] = " ".join(title_tokens[:2])
        elif title_tokens:
            parsed["brand"] = title_tokens[0]
        parsed.setdefault("field_sources", {})
        parsed["field_sources"].setdefault("brand", "page_title")

    summary_parts: list[str] = []
    if parsed.get("brand"):
        summary_parts.append(_text(parsed.get("brand"), ""))
    if parsed.get("display_name"):
        summary_parts.append(_text(parsed.get("display_name"), ""))
    if parsed.get("length_label"):
        summary_parts.append(_text(parsed.get("length_label"), ""))
    if parsed.get("power"):
        summary_parts.append(_text(parsed.get("power"), "").replace("_", " "))
    if parsed.get("action"):
        summary_parts.append(_text(parsed.get("action"), "").replace("_", " "))
    if parsed.get("lure_weight_min_oz") is not None or parsed.get("lure_weight_max_oz") is not None:
        low = parsed.get("lure_weight_min_oz")
        high = parsed.get("lure_weight_max_oz")
        if low is not None and high is not None and low != high:
            summary_parts.append(f"{low:g} to {high:g} oz lure rating")
        elif low is not None:
            summary_parts.append(f"{low:g} oz lure rating")
    if parsed.get("line_rating_min_lb") is not None or parsed.get("line_rating_max_lb") is not None:
        low = parsed.get("line_rating_min_lb")
        high = parsed.get("line_rating_max_lb")
        if low is not None and high is not None and low != high:
            summary_parts.append(f"{low} to {high} lb line rating")
        elif low is not None:
            summary_parts.append(f"{low} lb line rating")
    if parsed.get("technique_tags"):
        summary_parts.append(", ".join(str(tag).replace("_", " ") for tag in parsed.get("technique_tags", [])[:3]))
    if parsed.get("species_tags"):
        summary_parts.append(", ".join(str(tag).replace("_", " ") for tag in parsed.get("species_tags", [])[:3]))
    if summary_parts and not _text(parsed.get("product_summary"), ""):
        parsed["product_summary"] = " • ".join(part for part in summary_parts if part)

    normalized = normalize_structured_product(parsed, source_url=result.get("url", url), category=category, allow_remote_images=allow_remote_images)
    normalized["source_page_url"] = result.get("url", url)
    normalized["source_page_retrieved_at"] = result.get("retrieved_at")
    return {
        "ok": True,
        "product": normalized,
        "messages": [],
    }
