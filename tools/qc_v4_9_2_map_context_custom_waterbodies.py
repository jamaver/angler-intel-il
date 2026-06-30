#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

errors: list[str] = []


def read(rel: str) -> str:
    return (APP_ROOT / rel).read_text(encoding="utf-8")


def assert_exists(rel: str) -> None:
    if not (APP_ROOT / rel).exists():
        errors.append(f"Missing {rel}")


for rel in (
    "app.py",
    "angler_waters_v40.py",
    "intelligence/map_data.py",
    "intelligence/water_registry.py",
    "tools/qc_v4_9_2_map_context_custom_waterbodies.py",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists():
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

for rel in (
    "static/js/map_dashboard_v49.js",
    "templates/map.html",
    "data/app_version.json",
    "data/manual_waters.json",
    "data/version_v4_9_2_map_context_custom_waterbodies.json",
):
    assert_exists(rel)

version_path = APP_ROOT / "data" / "version_v4_9_2_map_context_custom_waterbodies.json"
if version_path.exists():
    marker = json.loads(version_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v4.9.2-map-context-custom-waterbodies":
        errors.append("v4.9.2 marker has unexpected version")
    if marker.get("json_source_of_truth") is not True:
        errors.append("v4.9.2 marker must keep JSON current")
    if marker.get("real_map_tiles_enabled") is not True:
        errors.append("v4.9.2 marker must enable real map tiles")
    if marker.get("manual_waterbody_entry_enabled") is not True:
        errors.append("v4.9.2 marker must enable manual waterbody entry")
    if marker.get("authority_switch_allowed_now") is not False:
        errors.append("v4.9.2 marker must not allow SQLite authority switch")

app_version_path = APP_ROOT / "data" / "app_version.json"
if app_version_path.exists():
    app_version = json.loads(app_version_path.read_text(encoding="utf-8"))
    if app_version.get("version") != "v4.9.2-map-context-custom-waterbodies":
        errors.append("app_version.json is not aligned to v4.9.2")

app_text = read("app.py")
map_text = read("static/js/map_dashboard_v49.js")
map_html = read("templates/map.html")
waters_text = read("angler_waters_v40.py")
registry_text = read("intelligence/water_registry.py")

for needle, message in [
    ('@app.route("/api/waters/custom", methods=["POST"])', "app.py missing manual waterbody route"),
    ('@app.route("/api/map-data")', "app.py missing map-data route"),
    ("append_custom_water_record", "app.py must save manual waters through the registry"),
    ("load_water_catalog", "app.py should use the merged water catalog"),
]:
    if needle not in app_text:
        errors.append(message)

for needle, message in [
    ("L.map", "Map dashboard should use Leaflet"),
    ("World_Imagery", "Map dashboard should include satellite tiles"),
    ("openstreetmap", "Map dashboard should include a street layer"),
    ("opentopomap", "Map dashboard should include a terrain layer"),
    ("/api/map-data", "Map dashboard should load merged map data"),
    ("/api/waters/custom", "Map dashboard should submit manual waters"),
    ("mapWaterName", "Map add form missing waterbody name field"),
    ("mapWaterLat", "Map add form missing latitude field"),
    ("mapBaseLayer", "Map basemap selector missing"),
]:
    if needle not in map_text:
        errors.append(message)

if "leaflet.css" not in map_html or "leaflet.js" not in map_html:
    errors.append("Map template must load Leaflet assets")
if "mapAddForm" not in map_html or "mapBaseLayer" not in map_html:
    errors.append("Map template must include basemap selector and add-water form")
if "Current release: {{ app_version }}" not in map_html:
    errors.append("Map template should surface the current release")

if "load_water_records" not in waters_text or "load_water_catalog" not in waters_text:
    errors.append("Local waters route should use the merged water catalog")
if "manual waterbody" not in registry_text.lower() or "append_custom_water_record" not in registry_text:
    errors.append("Water registry must support custom waterbody persistence")

from app import app as flask_app
from intelligence.map_data import get_map_data_readiness
from intelligence.water_registry import CUSTOM_WATERS_PATH

readiness = get_map_data_readiness()
if readiness.get("record_count", 0) < 1:
    errors.append("Map readiness did not return records")
if readiness.get("manual_waterbody_entry_enabled") is not True:
    errors.append("Map readiness must advertise manual waterbody entry")

manual_path = CUSTOM_WATERS_PATH
original_manual = manual_path.read_text(encoding="utf-8") if manual_path.exists() else "[]"
test_record = {
    "name": "QC Manual Waterbody",
    "type": "lake",
    "lat": 41.765432,
    "lon": -88.123456,
    "city": "QC City",
    "county": "QC County",
    "species": "largemouth bass, bluegill",
    "access": "shore, small craft",
    "notes": "QC-created waterbody for integration verification.",
    "favorite": True,
    "stocked_trout": False,
}

client = flask_app.test_client()
created_id = None
try:
    response = client.post("/api/waters/custom", json=test_record)
    if response.status_code != 201:
        errors.append(f"Manual waterbody POST failed with HTTP {response.status_code}")
    else:
        created = response.get_json(force=True)
        created_id = created.get("water", {}).get("id")
        if not created_id:
            errors.append("Manual waterbody POST did not return an id")
        else:
            data = client.get("/api/map-data").get_json(force=True)
            if not any(item.get("id") == created_id for item in data.get("waters", [])):
                errors.append("Manual waterbody did not appear in /api/map-data")
            if data.get("custom_count", 0) < 1:
                errors.append("Map data did not report any custom waters after POST")
finally:
    manual_path.write_text(original_manual, encoding="utf-8")

if errors:
    print("QC FAILED: v4.9.2 Map Context + Custom Waters")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.9.2 Map Context + Custom Waters")
print("Leaflet basemaps and manual waterbody persistence are wired end to end.")
