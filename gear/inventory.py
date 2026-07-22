from __future__ import annotations

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from persistence.gear_inventory_mirror import mirror_gear_inventory

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
CATCHES_PATH = DATA_DIR / "catches.json"

DEFAULT_VERSION = "v6.13-gear-intelligence-packing-catch-linking"
CATEGORY_ORDER = ["rod", "reel", "line", "lure", "terminal", "misc"]
CATEGORY_LABELS = {
    "rod": "Rods",
    "reel": "Reels",
    "line": "Line",
    "lure": "Lures",
    "terminal": "Terminal Tackle",
    "misc": "Miscellaneous",
}
CATEGORY_FALLBACKS = {
    "rod": "/static/gear/fallback/rod.svg",
    "reel": "/static/gear/fallback/reel.svg",
    "line": "/static/gear/fallback/line.svg",
    "lure": "/static/gear/fallback/lure.svg",
    "terminal": "/static/gear/fallback/terminal.svg",
    "misc": "/static/gear/fallback/generic.svg",
}
STATUS_VALUES = {"owned", "wishlist", "retired"}
TERMINAL_SUBTYPE_LABELS = {
    "hook": "Hook",
    "weight": "Weight",
    "swivel": "Swivel",
    "snap": "Snap",
    "jig_head": "Jig Head",
    "leader": "Leader",
}


def _path_from_env(name: str, default: Path) -> Path:
    value = os.environ.get(name, "").strip()
    return Path(value) if value else default


def inventory_path() -> Path:
    return _path_from_env("AI_GEAR_INVENTORY_PATH", DATA_DIR / "gear_inventory.json")


def catalog_cache_path() -> Path:
    return _path_from_env("AI_GEAR_CATALOG_CACHE_PATH", DATA_DIR / "gear_catalog_cache.json")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _slug(value: Any, fallback: str = "gear") -> str:
    text = " ".join(str(value or "").split()).strip().lower()
    text = "".join(ch if ch.isalnum() else "-" for ch in text)
    text = "-".join(part for part in text.split("-") if part)
    return text or fallback


def _text(value: Any, fallback: str = "") -> str:
    text = " ".join(str(value or "").split()).strip()
    return text or fallback


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "on"}


def _as_int(value: Any, fallback: int | None = None) -> int | None:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return fallback


def _as_float(value: Any, fallback: float | None = None) -> float | None:
    try:
        return float(str(value).strip())
    except Exception:
        return fallback


def _split_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    return [part.strip() for part in str(value or "").replace("\n", ",").split(",") if part.strip()]


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _compact_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _item_blob(item: dict[str, Any]) -> str:
    pieces = [
        item.get("category"),
        item.get("brand"),
        item.get("model"),
        item.get("display_name"),
        item.get("notes"),
        item.get("source_name"),
        item.get("source_url"),
        item.get("reel_type"),
        item.get("line_type"),
        item.get("lure_type"),
        item.get("subtype"),
        item.get("size"),
    ]
    specs = _as_dict(item.get("specifications"))
    identifiers = _as_dict(item.get("identifiers"))
    pieces.extend(specs.values())
    pieces.extend(identifiers.values())
    return " ".join(_text(piece) for piece in pieces if _text(piece)).lower()


def _identifier_values(item: dict[str, Any]) -> list[str]:
    identifiers = _as_dict(item.get("identifiers"))
    values = []
    for key in ("upc", "gtin", "gtin13", "gtin14", "sku", "asin", "mpn", "manufacturer_part_number", "product_id", "provider_product_id"):
        value = _text(identifiers.get(key), "")
        if value:
            values.append(value.lower())
    for key in ("provider_product_id", "provider", "source_url"):
        value = _text(item.get(key), "")
        if value:
            values.append(value.lower())
    return values


def ensure_inventory_file() -> None:
    path = inventory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        save_inventory(_default_inventory())


def _default_inventory() -> dict[str, Any]:
    return {
        "version": DEFAULT_VERSION,
        "updated_at": _now(),
        "items": [],
        "maintenance": [],
        "catalog_cache": [],
    }


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)
    except Exception:
        return default


def _load_catches() -> list[dict[str, Any]]:
    data = _read_json(CATCHES_PATH, [])
    return data if isinstance(data, list) else []


def load_inventory() -> dict[str, Any]:
    ensure_inventory_file()
    data = _read_json(inventory_path(), _default_inventory())
    if not isinstance(data, dict):
        data = _default_inventory()
    data.setdefault("version", DEFAULT_VERSION)
    data.setdefault("updated_at", _now())
    items = data.get("items")
    data["items"] = items if isinstance(items, list) else []
    data["maintenance"] = data.get("maintenance") if isinstance(data.get("maintenance"), list) else []
    data["catalog_cache"] = data.get("catalog_cache") if isinstance(data.get("catalog_cache"), list) else []
    return data


def save_inventory(data: dict[str, Any], *, usage_event: dict[str, Any] | None = None) -> None:
    payload = dict(data or {})
    payload.setdefault("version", DEFAULT_VERSION)
    payload["updated_at"] = _now()
    payload["items"] = payload.get("items") if isinstance(payload.get("items"), list) else []
    payload["maintenance"] = payload.get("maintenance") if isinstance(payload.get("maintenance"), list) else []
    payload["catalog_cache"] = payload.get("catalog_cache") if isinstance(payload.get("catalog_cache"), list) else []
    path = inventory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    # JSON remains authoritative. SQLite mirror failures are non-fatal and are
    # surfaced through V7 mirror diagnostics for later reconciliation.
    mirror_gear_inventory(payload, path, usage_event=usage_event)


def category_label(category: Any) -> str:
    key = _text(category, "misc").lower()
    return CATEGORY_LABELS.get(key, key.replace("_", " ").title() or "Miscellaneous")


def fallback_image_for(category: Any, subtype: Any = None) -> str:
    key = _text(category, "misc").lower()
    if key == "terminal":
        sub = _text(subtype, "").lower()
        if sub == "hook":
            return "/static/gear/fallback/terminal-hook.svg"
        if sub == "weight":
            return "/static/gear/fallback/terminal-weight.svg"
    return CATEGORY_FALLBACKS.get(key, CATEGORY_FALLBACKS["misc"])


def provider_icon_for(provider: Any, source: Any = None) -> str:
    key = _text(provider, "").lower()
    source_key = _text(source, "").lower()
    if key in {"amazon", "walmart", "structured", "local", "manual", "cache"}:
        if key in {"manual", "cache"}:
            return f"/static/gear/providers/{key}.svg"
        return f"/static/gear/providers/{key}.svg"
    if source_key in {"manual", "cache"}:
        return f"/static/gear/providers/{source_key}.svg"
    return "/static/gear/providers/manual.svg"


def _default_display_name(item: dict[str, Any]) -> str:
    category = _text(item.get("category"), "misc").lower()
    brand = _text(item.get("brand"), "")
    model = _text(item.get("model"), "")
    if category == "rod":
        parts = [brand, model, _text(item.get("length_label"), ""), _text(item.get("power"), "").replace("_", " ").title(), _text(item.get("action"), "").title()]
        return " ".join(part for part in parts if part)
    if category == "reel":
        parts = [brand, model, _text(item.get("reel_type"), "").title(), f'{item.get("gear_ratio")} :1' if item.get("gear_ratio") not in (None, "") else ""]
        return " ".join(part for part in parts if part)
    if category == "line":
        parts = [brand, model, _text(item.get("strength_lb"), ""), _text(item.get("line_type"), "").title()]
        return " ".join(part for part in parts if part)
    if category == "lure":
        parts = [brand, model, _text(item.get("lure_type"), "").replace("_", " ").title(), _text(item.get("color"), "").replace("_", " ").title()]
        return " ".join(part for part in parts if part)
    if category == "terminal":
        parts = [brand, model, TERMINAL_SUBTYPE_LABELS.get(_text(item.get("subtype"), "").lower(), _text(item.get("subtype"), "").title()), _text(item.get("size"), "")]
        return " ".join(part for part in parts if part)
    return " ".join(part for part in [brand, model, _text(item.get("display_name"), "")] if part)


def gear_item_label(item: dict[str, Any] | None) -> str:
    if not isinstance(item, dict):
        return ""
    label = _text(item.get("display_name"), "")
    if label:
        return label
    brand = _text(item.get("brand"), "")
    model = _text(item.get("model"), "")
    if brand or model:
        return " ".join(part for part in [brand, model] if part)
    return category_label(item.get("category"))


def normalize_item(payload: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    category = _text(payload.get("category") or existing.get("category"), "misc").lower()
    if category not in CATEGORY_ORDER:
        category = "misc"

    item_id = _text(payload.get("id") or existing.get("id"), "")
    if not item_id:
        item_id = f"gear-{uuid.uuid4().hex[:12]}"

    item: dict[str, Any] = dict(existing)
    item.update({
        "id": item_id,
        "category": category,
        "brand": _text(payload.get("brand"), _text(existing.get("brand"), "")),
        "model": _text(payload.get("model"), _text(existing.get("model"), "")),
        "display_name": _text(payload.get("display_name"), _text(existing.get("display_name"), "")),
        "status": _text(payload.get("status"), _text(existing.get("status"), "owned")).lower(),
        "favorite": _as_bool(payload.get("favorite") if "favorite" in payload else existing.get("favorite")),
        "notes": _text(payload.get("notes"), _text(existing.get("notes"), "")),
        "image": _text(payload.get("image"), _text(existing.get("image"), "")),
        "image_url": _text(payload.get("image_url"), _text(existing.get("image_url"), "")),
        "image_source": _text(payload.get("image_source"), _text(existing.get("image_source"), "")),
        "source": _text(payload.get("source"), _text(existing.get("source"), "manual")).lower(),
        "source_name": _text(payload.get("source_name"), _text(existing.get("source_name"), "Manual entry")),
        "source_url": _text(payload.get("source_url"), _text(existing.get("source_url"), "")),
        "retrieved_at": _text(payload.get("retrieved_at"), _text(existing.get("retrieved_at"), "")),
        "confidence": _text(payload.get("confidence"), _text(existing.get("confidence"), "user-added")).lower(),
        "provider": _text(payload.get("provider"), _text(existing.get("provider"), "")),
        "provider_product_id": _text(payload.get("provider_product_id"), _text(existing.get("provider_product_id"), "")),
        "provider_icon": _text(payload.get("provider_icon"), _text(existing.get("provider_icon"), provider_icon_for(payload.get("provider"), payload.get("source") or existing.get("source")))),
        "price": payload.get("price", existing.get("price")),
        "availability": _text(payload.get("availability"), _text(existing.get("availability"), "")),
        "raw_provider_data_cached": _as_bool(payload.get("raw_provider_data_cached") if "raw_provider_data_cached" in payload else existing.get("raw_provider_data_cached")),
        "identifiers": _as_dict(payload.get("identifiers")) or _as_dict(existing.get("identifiers")),
        "specifications": _as_dict(payload.get("specifications")) or _as_dict(existing.get("specifications")),
        "field_sources": _as_dict(payload.get("field_sources")) or _as_dict(existing.get("field_sources")),
        "quantity": _as_int(payload.get("quantity"), _as_int(existing.get("quantity"), 1)) or 1,
        "purchase_date": _text(payload.get("purchase_date"), _text(existing.get("purchase_date"), "")),
        "purchase_price": _text(payload.get("purchase_price"), _text(existing.get("purchase_price"), "")),
        "last_used": _text(payload.get("last_used"), _text(existing.get("last_used"), "")),
        "trips_used": _as_int(payload.get("trips_used"), _as_int(existing.get("trips_used"), 0)) or 0,
        "catches_logged": _as_int(payload.get("catches_logged"), _as_int(existing.get("catches_logged"), 0)) or 0,
        "last_cleaned": _text(payload.get("last_cleaned"), _text(existing.get("last_cleaned"), "")),
        "maintenance_interval_days": _as_int(payload.get("maintenance_interval_days"), _as_int(existing.get("maintenance_interval_days"), 0)) or 0,
        "maintenance_notes": _text(payload.get("maintenance_notes"), _text(existing.get("maintenance_notes"), "")),
        "retired_at": _text(payload.get("retired_at"), _text(existing.get("retired_at"), "")),
        "retired_reason": _text(payload.get("retired_reason"), _text(existing.get("retired_reason"), "")),
        "created_at": _text(existing.get("created_at"), _now()),
        "updated_at": _now(),
    })

    if item["status"] not in STATUS_VALUES:
        item["status"] = "owned"

    if category == "rod":
        item.update({
            "length_ft": _as_float(payload.get("length_ft"), _as_float(existing.get("length_ft"))),
            "length_label": _text(payload.get("length_label"), _text(existing.get("length_label"), "")),
            "power": _text(payload.get("power"), _text(existing.get("power"), "")).lower().replace(" ", "_"),
            "action": _text(payload.get("action"), _text(existing.get("action"), "")).lower().replace(" ", "_"),
            "pieces": _as_int(payload.get("pieces"), _as_int(existing.get("pieces"), 1)) or 1,
            "lure_weight_min_oz": _as_float(payload.get("lure_weight_min_oz"), _as_float(existing.get("lure_weight_min_oz"))),
            "lure_weight_max_oz": _as_float(payload.get("lure_weight_max_oz"), _as_float(existing.get("lure_weight_max_oz"))),
            "line_rating_min_lb": _as_int(payload.get("line_rating_min_lb"), _as_int(existing.get("line_rating_min_lb"))),
            "line_rating_max_lb": _as_int(payload.get("line_rating_max_lb"), _as_int(existing.get("line_rating_max_lb"))),
            "technique_tags": _split_tags(payload.get("technique_tags", existing.get("technique_tags", []))),
            "species_tags": _split_tags(payload.get("species_tags", existing.get("species_tags", []))),
        })
        if not item["display_name"]:
            item["display_name"] = _default_display_name(item)
        if not item["length_label"] and item.get("length_ft"):
            item["length_label"] = f"{item['length_ft']:.1f} ft"
        if not item["power"]:
            item["power"] = "medium"
        if not item["action"]:
            item["action"] = "fast"

    elif category == "reel":
        item.update({
            "reel_type": _text(payload.get("reel_type"), _text(existing.get("reel_type"), "")).lower().replace(" ", "_"),
            "gear_ratio": _as_float(payload.get("gear_ratio"), _as_float(existing.get("gear_ratio"))),
            "max_drag_lb": _as_float(payload.get("max_drag_lb"), _as_float(existing.get("max_drag_lb"))),
            "line_capacity": _text(payload.get("line_capacity"), _text(existing.get("line_capacity"), "")),
            "weight_oz": _as_float(payload.get("weight_oz"), _as_float(existing.get("weight_oz"))),
            "handedness": _text(payload.get("handedness"), _text(existing.get("handedness"), "")).lower(),
        })
        if not item["display_name"]:
            item["display_name"] = _default_display_name(item)

    elif category == "line":
        item.update({
            "line_type": _text(payload.get("line_type"), _text(existing.get("line_type"), "")).lower().replace(" ", "_"),
            "strength_lb": _as_int(payload.get("strength_lb"), _as_int(existing.get("strength_lb"))),
            "diameter_equivalent": _text(payload.get("diameter_equivalent"), _text(existing.get("diameter_equivalent"), "")),
            "color": _text(payload.get("color"), _text(existing.get("color"), "")).lower().replace(" ", "_"),
            "length_yd": _as_int(payload.get("length_yd"), _as_int(existing.get("length_yd"))),
        })
        if not item["display_name"]:
            item["display_name"] = _default_display_name(item)

    elif category == "lure":
        item.update({
            "lure_type": _text(payload.get("lure_type"), _text(existing.get("lure_type"), "")).lower().replace(" ", "_"),
            "color": _text(payload.get("color"), _text(existing.get("color"), "")).lower().replace(" ", "_"),
            "weight_oz": _as_float(payload.get("weight_oz"), _as_float(existing.get("weight_oz"))),
            "hook_size": _text(payload.get("hook_size"), _text(existing.get("hook_size"), "")),
            "depth_min_ft": _as_float(payload.get("depth_min_ft"), _as_float(existing.get("depth_min_ft"))),
            "depth_max_ft": _as_float(payload.get("depth_max_ft"), _as_float(existing.get("depth_max_ft"))),
            "species_tags": _split_tags(payload.get("species_tags", existing.get("species_tags", []))),
            "technique_tags": _split_tags(payload.get("technique_tags", existing.get("technique_tags", []))),
        })
        if not item["display_name"]:
            item["display_name"] = _default_display_name(item)

    elif category == "terminal":
        item.update({
            "subtype": _text(payload.get("subtype"), _text(existing.get("subtype"), "")).lower().replace(" ", "_"),
            "size": _text(payload.get("size"), _text(existing.get("size"), "")),
            "weight_oz": _as_float(payload.get("weight_oz"), _as_float(existing.get("weight_oz"))),
            "hook_size": _text(payload.get("hook_size"), _text(existing.get("hook_size"), "")),
            "quantity": _as_int(payload.get("quantity"), _as_int(existing.get("quantity"), 1)) or 1,
        })
        if not item["display_name"]:
            item["display_name"] = _default_display_name(item)

    else:
        item["display_name"] = _text(payload.get("display_name"), _text(existing.get("display_name"), "")) or _default_display_name(item)

    if not item["display_name"]:
        item["display_name"] = _default_display_name(item)

    if not item["image"]:
        item["image"] = item["image_url"] or fallback_image_for(category, payload.get("subtype") or existing.get("subtype"))
    if not item["image_url"] and item["image"].startswith("http"):
        item["image_url"] = item["image"]

    return item


def list_items() -> list[dict[str, Any]]:
    data = load_inventory()
    items = data.get("items") if isinstance(data.get("items"), list) else []
    return sorted([item for item in items if isinstance(item, dict)], key=lambda x: (x.get("favorite", False), x.get("updated_at", ""), x.get("created_at", "")), reverse=True)


def search_items(query: str = "", category: str = "", status: str = "", limit: int = 20) -> list[dict[str, Any]]:
    q = _compact_text(query)
    category = _text(category, "").lower()
    status = _text(status, "").lower()
    results: list[tuple[int, dict[str, Any]]] = []

    for item in list_items():
        item_category = _text(item.get("category"), "misc").lower()
        item_status = _text(item.get("status"), "owned").lower()
        if category and item_category != category:
            continue
        if status and item_status != status:
            continue

        blob = _item_blob(item)
        if q and q not in blob:
            continue

        score = 0
        if q:
            if q in _compact_text(item.get("display_name")):
                score += 30
            if q in _compact_text(item.get("brand")):
                score += 10
            if q in _compact_text(item.get("model")):
                score += 10
            if q in _compact_text(item.get("notes")):
                score += 4
            if q in _compact_text(item.get("source_name")):
                score += 3
        if _as_bool(item.get("favorite")):
            score += 2
        if item_status == "owned":
            score += 1

        enriched = dict(item)
        enriched["fallback_image"] = fallback_image_for(item_category, item.get("subtype"))
        enriched["provider_icon"] = provider_icon_for(item.get("provider"), item.get("source"))
        results.append((score, enriched))

    results.sort(key=lambda pair: (pair[0], _text(pair[1].get("updated_at"), ""), _text(pair[1].get("display_name"), "")), reverse=True)
    return [item for _, item in results[:limit]]


def find_duplicate_items(candidate: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    candidate = candidate if isinstance(candidate, dict) else {}
    candidate_category = _text(candidate.get("category"), "misc").lower()
    candidate_brand = _compact_text(candidate.get("brand"))
    candidate_model = _compact_text(candidate.get("model"))
    candidate_display = _compact_text(candidate.get("display_name"))
    candidate_identifiers = [value for value in _identifier_values(candidate) if value]
    candidate_blob = _item_blob(candidate)
    candidate_id = _text(candidate.get("id"), "")

    matches: list[tuple[int, dict[str, Any]]] = []

    for item in list_items():
        if candidate_id and _text(item.get("id"), "") == candidate_id:
            continue
        score = 0
        reasons: list[str] = []
        item_category = _text(item.get("category"), "misc").lower()

        if candidate_category and item_category == candidate_category:
            score += 20
            reasons.append("same category")

        item_identifiers = _identifier_values(item)
        if candidate_identifiers and item_identifiers:
            overlap = sorted(set(candidate_identifiers).intersection(item_identifiers))
            if overlap:
                score += 120
                reasons.append("shared identifier")

        item_brand = _compact_text(item.get("brand"))
        item_model = _compact_text(item.get("model"))
        item_display = _compact_text(item.get("display_name"))
        if candidate_brand and item_brand and candidate_brand == item_brand:
            score += 30
            reasons.append("same brand")
        if candidate_model and item_model and candidate_model == item_model:
            score += 40
            reasons.append("same model")
        if candidate_display and item_display and candidate_display == item_display:
            score += 50
            reasons.append("same display name")
        if candidate_blob and candidate_blob == _item_blob(item):
            score += 25
            reasons.append("matching specs")
        if candidate_brand and candidate_brand in item_display and candidate_model:
            score += 10
            reasons.append("brand/model match")

        if score >= 40:
            match = dict(item)
            match["fallback_image"] = fallback_image_for(item_category, item.get("subtype"))
            match["match_score"] = score
            match["match_reasons"] = reasons
            matches.append((score, match))

    matches.sort(key=lambda pair: (pair[0], _text(pair[1].get("updated_at"), ""), _text(pair[1].get("display_name"), "")), reverse=True)
    return [item for _, item in matches[:limit]]


def get_item(item_id: str) -> dict[str, Any] | None:
    item_id = _text(item_id, "")
    if not item_id:
        return None
    for item in list_items():
        if _text(item.get("id"), "") == item_id:
            return item
    return None


def upsert_item(payload: dict[str, Any], *, usage_event: dict[str, Any] | None = None) -> dict[str, Any]:
    data = load_inventory()
    items = [item for item in data.get("items", []) if isinstance(item, dict)]
    existing = None
    item_id = _text(payload.get("id"), "")
    if item_id:
        for idx, item in enumerate(items):
            if _text(item.get("id"), "") == item_id:
                existing = item
                items[idx] = normalize_item(payload, existing=item)
                break
    if existing is None:
        items.append(normalize_item(payload))
    data["items"] = items
    save_inventory(data, usage_event=usage_event)
    return get_item(item_id) if item_id else items[-1]


def delete_item(item_id: str) -> bool:
    if gear_item_reference_summary(item_id).get("count", 0):
        return False
    data = load_inventory()
    items = [item for item in data.get("items", []) if isinstance(item, dict)]
    before = len(items)
    items = [item for item in items if _text(item.get("id"), "") != _text(item_id, "")]
    if len(items) == before:
        return False
    data["items"] = items
    save_inventory(data)
    return True


def restore_item(item_id: str) -> dict[str, Any] | None:
    item = get_item(item_id)
    if not item:
        return None
    payload = dict(item)
    payload["status"] = "owned"
    payload["retired_at"] = ""
    payload["retired_reason"] = ""
    return upsert_item(payload)


def set_status(item_id: str, status: str) -> dict[str, Any] | None:
    item = get_item(item_id)
    if not item:
        return None
    payload = dict(item)
    payload["status"] = _text(status, "owned").lower()
    if payload["status"] not in STATUS_VALUES:
        payload["status"] = "owned"
    return upsert_item(payload)


def toggle_favorite(item_id: str, favorite: bool | None = None) -> dict[str, Any] | None:
    item = get_item(item_id)
    if not item:
        return None
    payload = dict(item)
    payload["favorite"] = (not bool(item.get("favorite"))) if favorite is None else bool(favorite)
    return upsert_item(payload)


def gear_item_reference_summary(item_id: str, limit: int = 5) -> dict[str, Any]:
    item_id = _text(item_id, "")
    if not item_id:
        return {"count": 0, "examples": []}

    examples: list[dict[str, Any]] = []
    count = 0
    for record in _load_catches():
        if not isinstance(record, dict):
            continue
        gear_refs = record.get("gear_refs") if isinstance(record.get("gear_refs"), dict) else {}
        if item_id not in {str(ref).strip() for ref in gear_refs.values() if str(ref).strip()}:
            continue
        count += 1
        if len(examples) < limit:
            examples.append({
                "id": record.get("id"),
                "species": record.get("species"),
                "waterbody": record.get("waterbody"),
                "timestamp": record.get("timestamp"),
            })

    return {"count": count, "examples": examples}


def record_item_usage(
    item_id: str,
    *,
    used_at: str | None = None,
    trips: int = 1,
    catches: int = 0,
) -> dict[str, Any] | None:
    item = get_item(item_id)
    if not item:
        return None
    payload = dict(item)
    payload["last_used"] = _text(used_at, _now())
    payload["trips_used"] = max(0, _as_int(payload.get("trips_used"), 0) or 0) + max(0, int(trips or 0))
    payload["catches_logged"] = max(0, _as_int(payload.get("catches_logged"), 0) or 0) + max(0, int(catches or 0))
    return upsert_item(
        payload,
        usage_event={
            "gear_item_id": item_id,
            "used_at": payload["last_used"],
            "trips": max(0, int(trips or 0)),
            "catches": max(0, int(catches or 0)),
            "source": "record_item_usage",
        },
    )


def mark_item_cleaned(item_id: str, cleaned_at: str | None = None) -> dict[str, Any] | None:
    item = get_item(item_id)
    if not item:
        return None
    payload = dict(item)
    payload["last_cleaned"] = _text(cleaned_at, _now())
    return upsert_item(payload)


def category_sections(items: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    items = items if isinstance(items, list) else list_items()
    sections: list[dict[str, Any]] = []
    for category in CATEGORY_ORDER:
        category_items = [item for item in items if _text(item.get("category"), "misc").lower() == category]
        sections.append({
            "key": category,
            "label": category_label(category),
            "count": len(category_items),
            "items": category_items,
        })
    return sections


def inventory_summary(items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    items = items if isinstance(items, list) else list_items()
    owned = [item for item in items if _text(item.get("status"), "owned") == "owned"]
    favorites = [item for item in items if _as_bool(item.get("favorite"))]
    retired = [item for item in items if _text(item.get("status"), "") == "retired"]
    return {
        "total": len(items),
        "owned": len(owned),
        "favorites": len(favorites),
        "retired": len(retired),
        "wishlist": sum(1 for item in items if _text(item.get("status"), "") == "wishlist"),
        "recent": len([item for item in items if _text(item.get("updated_at"), "")][:4]),
        "by_category": {section["key"]: section["count"] for section in category_sections(items)},
    }


def recent_items(items: list[dict[str, Any]] | None = None, limit: int = 4) -> list[dict[str, Any]]:
    items = items if isinstance(items, list) else list_items()
    return sorted(items, key=lambda x: _text(x.get("updated_at"), _text(x.get("created_at"), "")), reverse=True)[:limit]


def reference_rig_items() -> list[dict[str, Any]]:
    path = DATA_DIR / "lure_rig_setups_v43.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except Exception:
        data = []
    return data if isinstance(data, list) else []
