from __future__ import annotations

from typing import Any

from intelligence.water_registry import load_water_catalog, load_water_records


def map_water_records(limit: int | None = None) -> list[dict[str, Any]]:
    records = load_water_records()
    if limit is not None:
        return records[:limit]
    return records


def get_map_data_readiness() -> dict[str, Any]:
    catalog = load_water_catalog()
    records = catalog["records"]

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

    warnings = list(catalog.get("warnings", []))

    return {
        "ok": bool(records) and not catalog.get("missing_coords"),
        "version": "v5.5-realistic-icon-system",
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "map_dashboard_planned": True,
        "map_dashboard_live": True,
        "manual_waterbody_entry_enabled": True,
        "record_count": len(records),
        "base_count": catalog.get("base_count", 0),
        "custom_count": catalog.get("custom_count", 0),
        "source_path": catalog.get("source_path"),
        "custom_source_path": catalog.get("custom_source_path"),
        "bounds": bounds,
        "missing_coords": catalog.get("missing_coords", [])[:10],
        "missing_species_ids": catalog.get("missing_species_ids", [])[:10],
        "unknown_species_ids": catalog.get("unknown_species_ids", [])[:10],
        "warnings": warnings,
        "records": records,
    }
