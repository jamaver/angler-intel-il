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
    "intelligence/map_data.py",
    "intelligence/water_registry.py",
    "templates/map.html",
    "templates/water.html",
    "static/js/map_dashboard_v49.js",
    "static/css/style.css",
    "docs/ROADMAP.md",
    "data/version_v4_9_4_map_filters_water_list.json",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists() and path.suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v4_9_4_map_filters_water_list.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v4.9.4-map-filters-water-list":
        errors.append("v4.9.4 marker has unexpected version")
    if marker.get("map_filter_controls_enabled") is not True:
        errors.append("v4.9.4 marker should enable map filters")
    if marker.get("waters_in_view_list_enabled") is not True:
        errors.append("v4.9.4 marker should enable waters-in-view list")

app_version_path = APP_ROOT / "data" / "app_version.json"
if app_version_path.exists():
    app_version = json.loads(app_version_path.read_text(encoding="utf-8"))
    if app_version.get("version") not in {
        "v4.9.4-map-filters-water-list",
        "v5.0-sqlite-authority-migration",
        "v5.1-sqlite-waterbody-migration-prep",
        "v5.2-catch-learning",
        "v5.3-target-species-profile",
        "v5.4-map-ranking-prep",
        "v5.5-realistic-icon-system",
        "v5.6-waterbody-detail-panels",
        "v5.7-waterbody-dataset-import-export",
        "v5.8-structured-backup-restore",
    }:
        errors.append("app_version.json is not aligned to v4.9.4 or later")

app_text = read("app.py")
map_text = read("static/js/map_dashboard_v49.js")
map_html = read("templates/map.html")
css_text = read("static/css/style.css")

for needle, message in [
    ('@app.route("/api/water-intel")', "app.py missing water intel API"),
    ('@app.route("/water/<water_id>")', "app.py missing water detail route"),
]:
    if needle not in app_text:
        errors.append(message)

if 'APP_VERSION = "v4.9.4-map-filters-water-list"' not in app_text and 'APP_VERSION = "v5.0-sqlite-authority-migration"' not in app_text and 'APP_VERSION = "v5.1-sqlite-waterbody-migration-prep"' not in app_text and 'APP_VERSION = "v5.2-catch-learning"' not in app_text and 'APP_VERSION = "v5.3-target-species-profile"' not in app_text and 'APP_VERSION = "v5.4-map-ranking-prep"' not in app_text and 'APP_VERSION = "v5.5-realistic-icon-system"' not in app_text and 'APP_VERSION = "v5.6-waterbody-detail-panels"' not in app_text and 'APP_VERSION = "v5.7-waterbody-dataset-import-export"' not in app_text and 'APP_VERSION = "v5.8-structured-backup-restore"' not in app_text:
    errors.append("app.py version is not aligned to the map filters release line")

for needle, message in [
    ("mapFilterFavorite", "Map filters missing favorite toggle"),
    ("mapFilterManual", "Map filters missing manual toggle"),
    ("mapFilterStocked", "Map filters missing stocked trout toggle"),
    ("mapFilterHistory", "Map filters missing catch history toggle"),
    ("mapFilterConfidence", "Map filters missing confidence toggle"),
    ("mapList", "Map waters-in-view list missing"),
    ("renderWaterList", "Map waters-in-view list rendering missing"),
    ("confidenceTier", "Confidence tier helper missing"),
]:
    if needle not in map_text:
        errors.append(message)

for needle, message in [
    ("map-toggle", "Map toggle styles missing"),
    ("map-water-row", "Waters-in-view row styles missing"),
    ("map-water-tier", "Waters-in-view confidence tier styles missing"),
]:
    if needle not in css_text:
        errors.append(message)

for needle, message in [
    ("mapFilterFavorite", "Map template missing favorite toggle"),
    ("mapListStatus", "Map template missing waters-in-view status"),
    ("mapList", "Map template missing waters-in-view container"),
]:
    if needle not in map_html:
        errors.append(message)

from app import app as flask_app
from intelligence.water_registry import load_water_records

records = load_water_records()
if not records:
    errors.append("No water records available for QC")
else:
    client = flask_app.test_client()
    sample = records[0]
    response = client.get("/api/map-data")
    if response.status_code != 200:
        errors.append(f"/api/map-data failed with HTTP {response.status_code}")
    else:
        payload = response.get_json(force=True)
        if payload.get("ok") is not True:
            errors.append("/api/map-data did not return ok=true")
        if payload.get("record_count", 0) < 1:
            errors.append("/api/map-data returned no records")

    response = client.get(f"/api/water-intel?water_id={sample.get('id')}")
    if response.status_code != 200:
        errors.append(f"/api/water-intel failed with HTTP {response.status_code}")
    else:
        payload = response.get_json(force=True)
        if not payload.get("selected_species"):
            errors.append("Water intel did not return selected species")
        if not payload.get("smart_intelligence"):
            errors.append("Water intel did not return smart intelligence")

if errors:
    print("QC FAILED: v4.9.4 Map Filters + Water List")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.9.4 Map Filters + Water List")
print("Map filters and waters-in-view list are wired to live water records.")
