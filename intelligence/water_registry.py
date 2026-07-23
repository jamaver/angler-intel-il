from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from persistence.manual_waters_mirror import mirror_manual_waters

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = APP_ROOT / "data"
BASE_WATERS_PATH = DATA_DIR / "illinois_waters.json"
CUSTOM_WATERS_PATH = DATA_DIR / "manual_waters.json"
SPECIES_PATH = DATA_DIR / "species_profiles_v43.json"


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


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        number = float(value)
        if number != number:
            return None
        return number
    except Exception:
        return None


def _slugify(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower())
    return text.strip("-")


def _as_text_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        items = value
    elif isinstance(value, str):
        items = re.split(r"[,\n;/|]+", value)
    else:
        items = [value]

    cleaned: list[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _species_lookup() -> dict[str, str]:
    payload = _read_json(SPECIES_PATH, [])
    lookup: dict[str, str] = {}

    if not isinstance(payload, list):
        return lookup

    for item in payload:
        if not isinstance(item, dict):
            continue

        species_id = str(item.get("id") or "").strip()
        species_name = str(item.get("name") or "").strip()

        if species_id:
            lookup[_slugify(species_id)] = species_id
        if species_name:
            lookup[_slugify(species_name)] = species_id or species_name

    return lookup


def _normalize_species_ids(values: Any) -> list[str]:
    lookup = _species_lookup()
    species_ids: list[str] = []
    seen: set[str] = set()

    for item in _as_text_list(values):
        species_id = lookup.get(_slugify(item), _slugify(item))
        if species_id and species_id not in seen:
            seen.add(species_id)
            species_ids.append(species_id)

    return species_ids


def _raw_water_list(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path, [])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("waters"), list):
        return [item for item in payload["waters"] if isinstance(item, dict)]
    return []


def _normalize_loaded_water(
    water: dict[str, Any],
    *,
    source: str,
    warnings: list[str],
) -> dict[str, Any] | None:
    name = str(water.get("name") or "").strip()
    water_type = str(water.get("type") or "water").strip() or "water"
    lat = _safe_float(water.get("lat"))
    lon = _safe_float(water.get("lon"))

    identifier = str(water.get("id") or "").strip()
    if not identifier:
        safe_name = _slugify(name or water_type or "waterbody") or "waterbody"
        identifier = f"{source}-{safe_name}-{uuid.uuid4().hex[:8]}"
        warnings.append(f"Generated an id for a {source} waterbody missing one: {name or water_type}.")

    if lat is None or lon is None:
        warnings.append(f"Skipped {name or identifier} because coordinates are missing or invalid.")
        return None

    species = _as_text_list(water.get("species"))
    raw_species_ids = _as_text_list(water.get("species_ids"))
    if raw_species_ids:
        species_ids = _normalize_species_ids(raw_species_ids)
    else:
        species_ids = _normalize_species_ids(species)
        if species:
            warnings.append(f"{name or identifier} is missing species_ids; derived them from species names.")

    loaded = dict(water)
    loaded.update(
        {
            "id": identifier,
            "name": name or f"Unnamed {water_type}",
            "type": water_type,
            "city": str(water.get("city") or "").strip(),
            "county": str(water.get("county") or "").strip(),
            "state": str(water.get("state") or "").strip(),
            "lat": lat,
            "lon": lon,
            "species": species,
            "species_ids": species_ids,
            "access": _as_text_list(water.get("access")),
            "habitat": _as_text_list(water.get("habitat")),
            "notes": str(water.get("notes") or "").strip(),
            "confidence": str(water.get("confidence") or ("manual" if source == "manual" else "unknown")).strip() or ("manual" if source == "manual" else "unknown"),
            "source": str(water.get("source") or source).strip() or source,
            "manual": _to_bool(water.get("manual")) or source == "manual",
            "favorite": _to_bool(water.get("favorite", False)),
            "stocked_trout": _to_bool(water.get("stocked_trout", False)),
        }
    )

    if water.get("catch_history_count") is not None:
        try:
            loaded["catch_history_count"] = max(0, _safe_int(water.get("catch_history_count", 0)))
        except Exception:
            loaded["catch_history_count"] = 0
    else:
        loaded.setdefault("catch_history_count", 0)

    if water.get("created_at"):
        loaded["created_at"] = str(water.get("created_at"))
    elif source == "manual":
        loaded["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")

    return loaded


def _merge_water_records(
    waters: list[dict[str, Any]],
    *,
    source: str,
    warnings: list[str],
) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
    records: list[dict[str, Any]] = []
    missing_coords: list[str] = []
    missing_species_ids: list[str] = []
    unknown_species_ids: list[str] = []
    known_species_ids = set(_species_lookup().values())

    for water in waters:
        name = str(water.get("name") or "").strip()
        identifier = str(water.get("id") or name or "unknown").strip() or "unknown"
        lat = _safe_float(water.get("lat"))
        lon = _safe_float(water.get("lon"))

        if lat is None or lon is None:
            missing_coords.append(identifier)
            warnings.append(f"{identifier} is missing coordinates.")
            continue

        if not _as_text_list(water.get("species_ids")):
            if _as_text_list(water.get("species")):
                missing_species_ids.append(identifier)
                warnings.append(f"{identifier} is missing species_ids.")
        else:
            for species_id in _normalize_species_ids(water.get("species_ids")):
                if known_species_ids and species_id not in known_species_ids:
                    unknown_species_ids.append(species_id)

        normalized = _normalize_loaded_water(water, source=source, warnings=warnings)
        if normalized is not None:
            records.append(normalized)

    return records, missing_coords, missing_species_ids, unknown_species_ids


def load_water_catalog(include_custom: bool = True) -> dict[str, Any]:
    warnings: list[str] = []

    base_raw = _raw_water_list(BASE_WATERS_PATH)
    base_records, base_missing_coords, base_missing_species_ids, base_unknown_species_ids = _merge_water_records(
        base_raw,
        source="starter",
        warnings=warnings,
    )

    custom_raw = _raw_water_list(CUSTOM_WATERS_PATH) if include_custom else []
    custom_records, custom_missing_coords, custom_missing_species_ids, custom_unknown_species_ids = _merge_water_records(
        custom_raw,
        source="manual",
        warnings=warnings,
    )

    records_by_id: dict[str, dict[str, Any]] = {}
    for record in base_records + custom_records:
        records_by_id[record["id"]] = record

    records = sorted(
        records_by_id.values(),
        key=lambda item: (
            str(item.get("county") or ""),
            str(item.get("name") or ""),
        ),
    )

    missing_coords = base_missing_coords + custom_missing_coords
    missing_species_ids = base_missing_species_ids + custom_missing_species_ids
    unknown_species_ids = sorted(set(base_unknown_species_ids + custom_unknown_species_ids))

    if missing_coords:
        warnings.append(f"{len(missing_coords)} water record(s) were missing coordinates.")
    if missing_species_ids:
        warnings.append(f"{len(missing_species_ids)} water record(s) were missing species_ids.")
    if unknown_species_ids:
        warnings.append(f"{len(unknown_species_ids)} unknown species id(s) were referenced.")

    return {
        "records": records,
        "base_count": len(base_records),
        "custom_count": len(custom_records),
        "total_count": len(records),
        "source_path": str(BASE_WATERS_PATH.relative_to(APP_ROOT)),
        "custom_source_path": str(CUSTOM_WATERS_PATH.relative_to(APP_ROOT)),
        "missing_coords": missing_coords[:25],
        "missing_species_ids": missing_species_ids[:25],
        "unknown_species_ids": unknown_species_ids[:25],
        "warnings": warnings,
    }


def load_water_records(include_custom: bool = True) -> list[dict[str, Any]]:
    return load_water_catalog(include_custom=include_custom)["records"]


def load_custom_water_records() -> list[dict[str, Any]]:
    payload = _read_json(CUSTOM_WATERS_PATH, [])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("waters"), list):
        return [item for item in payload["waters"] if isinstance(item, dict)]
    return []


def get_water_record_by_id(water_id: str) -> dict[str, Any] | None:
    water_id = str(water_id or "").strip()
    if not water_id:
        return None

    for record in load_water_records(include_custom=True):
        if str(record.get("id") or "").strip() == water_id:
            return record

    return None


def normalize_custom_water_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a manual waterbody payload before persistence."""
    if not isinstance(payload, dict):
        raise ValueError("Waterbody payload must be an object")

    name = str(payload.get("name") or "").strip()
    water_type = str(payload.get("type") or "water").strip() or "water"
    lat = _safe_float(payload.get("lat"))
    lon = _safe_float(payload.get("lon"))

    if not name:
        raise ValueError("Waterbody name is required")
    if lat is None or lon is None:
        raise ValueError("Latitude and longitude are required")

    record_id = str(payload.get("id") or "").strip()
    if not record_id:
        record_id = f"manual-{_slugify(name) or 'waterbody'}-{uuid.uuid4().hex[:8]}"

    species = _as_text_list(payload.get("species"))
    access = _as_text_list(payload.get("access"))
    habitat = _as_text_list(payload.get("habitat"))
    species_ids = _normalize_species_ids(payload.get("species_ids") or species)
    confidence = str(payload.get("confidence") or "manual").strip() or "manual"
    created_at = str(payload.get("created_at") or "").strip() or datetime.now().astimezone().isoformat(timespec="seconds")

    return {
        "id": record_id,
        "name": name,
        "type": water_type,
        "city": str(payload.get("city") or "").strip(),
        "county": str(payload.get("county") or "").strip(),
        "state": str(payload.get("state") or "").strip() or "IL",
        "lat": lat,
        "lon": lon,
        "species": species,
        "species_ids": species_ids,
        "access": access,
        "habitat": habitat,
        "notes": str(payload.get("notes") or "").strip(),
        "confidence": confidence,
        "manual": True,
        "source": "manual",
        "favorite": _to_bool(payload.get("favorite", False)),
        "stocked_trout": _to_bool(payload.get("stocked_trout", False)),
        "catch_history_count": max(0, _safe_int(payload.get("catch_history_count", 0))),
        "created_at": created_at,
    }


def append_custom_water_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = normalize_custom_water_record(payload)

    records = load_custom_water_records()
    records = [item for item in records if str(item.get("id") or "").strip() != record["id"]]
    records.append(record)
    records.sort(key=lambda item: (str(item.get("county") or ""), str(item.get("name") or "")))
    _write_json(CUSTOM_WATERS_PATH, records)
    # JSON is authoritative. A SQLite failure is deliberately non-fatal here.
    mirror_manual_waters(CUSTOM_WATERS_PATH)

    return record


def export_waterbody_dataset(scope: str = "manual") -> dict[str, Any]:
    catalog = load_water_catalog()
    scope = str(scope or "manual").strip().lower()
    manual_records = load_custom_water_records()

    payload: dict[str, Any] = {
        "app_name": "Angler Intel",
        "dataset": "waterbodies",
        "export_scope": "merged" if scope == "merged" else "manual",
        "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_of_truth": "json",
        "starter_count": catalog.get("base_count", 0),
        "manual_count": catalog.get("custom_count", 0),
        "total_count": catalog.get("total_count", 0),
        "source_path": catalog.get("source_path"),
        "custom_source_path": catalog.get("custom_source_path"),
        "manual_waters": manual_records,
    }

    if scope == "merged":
        payload["waters"] = catalog.get("records", [])

    return payload


def import_waterbody_dataset(payload: dict[str, Any], mode: str = "replace") -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Import payload must be an object")

    mode = str(mode or "replace").strip().lower()
    if mode not in {"replace", "append", "merge"}:
        raise ValueError("Import mode must be replace, append, or merge")

    source_items = payload.get("manual_waters")
    if not isinstance(source_items, list):
        source_items = payload.get("waters")
    if not isinstance(source_items, list):
        source_items = payload.get("records")
    if not isinstance(source_items, list):
        raise ValueError("Import payload must include a manual_waters, waters, or records list")

    normalized: list[dict[str, Any]] = []
    skipped: list[str] = []

    for item in source_items:
        if not isinstance(item, dict):
            skipped.append("non-object item")
            continue

        source = str(item.get("source") or "manual").strip().lower()
        if source not in {"manual", "user", "user-added", "imported"} and not item.get("manual"):
            skipped.append(str(item.get("name") or item.get("id") or "unknown"))
            continue

        normalized.append(normalize_custom_water_record(item))

    existing = load_custom_water_records()

    if mode == "replace":
        merged = normalized
    else:
        merged_by_id: dict[str, dict[str, Any]] = {}
        for item in existing:
            merged_by_id[str(item.get("id") or "").strip()] = item
        for item in normalized:
            merged_by_id[str(item.get("id") or "").strip()] = item
        merged = list(merged_by_id.values())

    merged.sort(key=lambda item: (str(item.get("county") or ""), str(item.get("name") or "")))
    _write_json(CUSTOM_WATERS_PATH, merged)
    # Import writes the same authoritative source and mirrors the complete result.
    mirror_manual_waters(CUSTOM_WATERS_PATH)

    return {
        "ok": True,
        "mode": mode,
        "imported_count": len(normalized),
        "skipped_count": len(skipped),
        "skipped": skipped[:10],
        "manual_count": len(merged),
        "manual_waters_path": str(CUSTOM_WATERS_PATH.relative_to(APP_ROOT)),
    }
