#!/usr/bin/env python3
"""Focused QC for editable water metadata and observed-species updates."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import intelligence.water_registry as registry


def main() -> int:
    with tempfile.TemporaryDirectory(prefix=".angler-water-edit-qc-", dir=ROOT) as folder:
        root = Path(folder)
        base, custom, species = root / "base.json", root / "custom.json", root / "species.json"
        base.write_text(json.dumps([{"id": "starter-a", "name": "Starter Lake", "type": "lake", "lat": 41.0, "lon": -88.0, "species": ["Bluegill"]}]), encoding="utf-8")
        custom.write_text("[]", encoding="utf-8")
        species.write_text(json.dumps([{"id": "bluegill", "name": "Bluegill"}, {"id": "largemouth_bass", "name": "Largemouth Bass"}]), encoding="utf-8")
        old = registry.BASE_WATERS_PATH, registry.CUSTOM_WATERS_PATH, registry.SPECIES_PATH, registry.require_write_authority, registry.mirror_manual_waters, registry.load_water_records, registry.is_manual_waters_sqlite_authoritative
        try:
            registry.BASE_WATERS_PATH, registry.CUSTOM_WATERS_PATH, registry.SPECIES_PATH = base, custom, species
            registry.require_write_authority = lambda *_args: "json"  # type: ignore[assignment]
            registry.mirror_manual_waters = lambda *_args: {"ok": True}  # type: ignore[assignment]
            registry.is_manual_waters_sqlite_authoritative = lambda *_args: False  # type: ignore[assignment]
            registry.load_water_records = lambda include_custom=True: registry._load_water_catalog_json(include_custom=include_custom)["records"]  # type: ignore[assignment]
            edited = registry.update_water_record("starter-a", {"city": "Oswego", "species": "Bluegill, Largemouth Bass", "habitat": "weed edge"})
            assert edited["overrides_starter"] is True and edited["city"] == "Oswego"
            observation = registry.record_water_species_observation("Channel Catfish", water_id="starter-a")
            assert observation and observation["changed"] is True
            assert observation["water"]["species_observations"][0]["source"] == "catch"
            repeat = registry.record_water_species_observation("Channel Catfish", water_id="starter-a")
            assert repeat and repeat["changed"] is False
            merged = registry._load_water_catalog_json()["records"]
            lake = next(row for row in merged if row["id"] == "starter-a")
            assert "Channel Catfish" in lake["species"] and lake["overrides_starter"] is True
        finally:
            registry.BASE_WATERS_PATH, registry.CUSTOM_WATERS_PATH, registry.SPECIES_PATH, registry.require_write_authority, registry.mirror_manual_waters, registry.load_water_records, registry.is_manual_waters_sqlite_authoritative = old
    for path in (ROOT / "app.py", ROOT / "angler_reports_v38.py", ROOT / "static/js/app.js", ROOT / "static/js/map_dashboard_v49.js", ROOT / "templates/map.html"):
        assert path.exists() and path.stat().st_size > 0
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'methods=["PUT"]' in app_source and "record_water_species_observation" in app_source
    report_source = (ROOT / "angler_reports_v38.py").read_text(encoding="utf-8")
    assert "record_water_species_observation" not in report_source
    assert "water_species_update" not in report_source
    print("PASS: V7.7.7 water editing and observed-species QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
