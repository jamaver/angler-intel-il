from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = APP_ROOT / "data"
WATERS_PATH = DATA_DIR / "illinois_waters.json"
SPECIES_PATH = DATA_DIR / "species_profiles_v43.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        n = float(value)
        if math.isnan(n):
            return None
        return n
    except Exception:
        return None


def _species_ids() -> set[str]:
    payload = _read_json(SPECIES_PATH, [])
    if not isinstance(payload, list):
        return set()
    return {
        str(item.get("id"))
        for item in payload
        if isinstance(item, dict) and item.get("id")
    }


def map_water_records(limit: int | None = None) -> list[dict[str, Any]]:
    payload = _read_json(WATERS_PATH, [])
    waters = payload if isinstance(payload, list) else []
    records: list[dict[str, Any]] = []

    for water in waters:
        if not isinstance(water, dict):
            continue
        lat = _safe_float(water.get("lat"))
        lon = _safe_float(water.get("lon"))
        if lat is None or lon is None:
            continue
        records.append(
            {
                "id": water.get("id"),
                "name": water.get("name"),
                "type": water.get("type"),
                "city": water.get("city"),
                "county": water.get("county"),
                "lat": lat,
                "lon": lon,
                "species": water.get("species") if isinstance(water.get("species"), list) else [],
                "species_ids": water.get("species_ids") if isinstance(water.get("species_ids"), list) else [],
                "habitat": water.get("habitat") if isinstance(water.get("habitat"), list) else [],
                "confidence": water.get("confidence", "unknown"),
            }
        )

    records.sort(key=lambda item: (str(item.get("county") or ""), str(item.get("name") or "")))
    if limit is not None:
        return records[:limit]
    return records


def get_map_data_readiness() -> dict[str, Any]:
    payload = _read_json(WATERS_PATH, [])
    waters = payload if isinstance(payload, list) else []
    species_ids = _species_ids()
    records = map_water_records()

    missing_coords = []
    missing_species_ids = []
    unknown_species_ids = []

    for water in waters:
        if not isinstance(water, dict):
            continue
        lat = _safe_float(water.get("lat"))
        lon = _safe_float(water.get("lon"))
        if lat is None or lon is None:
            missing_coords.append(water.get("id") or water.get("name") or "unknown")

        water_species_ids = water.get("species_ids")
        if not isinstance(water_species_ids, list) or not water_species_ids:
            missing_species_ids.append(water.get("id") or water.get("name") or "unknown")
        else:
            for sid in water_species_ids:
                if species_ids and str(sid) not in species_ids:
                    unknown_species_ids.append(str(sid))

    bounds = None
    if records:
        lats = [item["lat"] for item in records]
        lons = [item["lon"] for item in records]
        bounds = {
            "min_lat": min(lats),
            "max_lat": max(lats),
            "min_lon": min(lons),
            "max_lon": max(lons),
        }

    warnings = []
    if missing_coords:
        warnings.append(f"{len(missing_coords)} water record(s) missing coordinates.")
    if missing_species_ids:
        warnings.append(f"{len(missing_species_ids)} water record(s) missing species_ids.")
    if unknown_species_ids:
        warnings.append(f"{len(set(unknown_species_ids))} unknown species id(s) referenced.")

    return {
        "ok": bool(records) and not missing_coords,
        "version": "v4.8-map-data-readiness",
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "map_dashboard_planned": True,
        "record_count": len(records),
        "source_path": str(WATERS_PATH.relative_to(APP_ROOT)),
        "bounds": bounds,
        "missing_coords": missing_coords[:10],
        "missing_species_ids": missing_species_ids[:10],
        "unknown_species_ids": sorted(set(unknown_species_ids))[:10],
        "warnings": warnings,
        "records": records,
    }
