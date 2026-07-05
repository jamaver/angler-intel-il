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
    "intelligence/water_registry.py",
    "templates/map.html",
    "templates/water.html",
    "static/js/map_dashboard_v49.js",
    "static/css/style.css",
    "docs/ROADMAP.md",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists() and path.suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v4_9_3_map_water_intel.json"
if not marker_path.exists():
    errors.append("Missing data/version_v4_9_3_map_water_intel.json")
else:
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v4.9.3-map-water-intel":
        errors.append("v4.9.3 marker has unexpected version")
    if marker.get("selected_water_drives_intelligence") is not True:
        errors.append("v4.9.3 marker must enable selected-water intelligence")
    if marker.get("water_detail_route_enabled") is not True:
        errors.append("v4.9.3 marker must enable water detail routing")

app_version_path = APP_ROOT / "data" / "app_version.json"
if app_version_path.exists():
    app_version = json.loads(app_version_path.read_text(encoding="utf-8"))
    if app_version.get("version") not in {
        "v4.9.3-map-water-intel",
        "v4.9.4-map-filters-water-list",
        "v5.0-sqlite-authority-migration",
        "v5.1-sqlite-waterbody-migration-prep",
        "v5.2-catch-learning",
        "v5.3-target-species-profile",
        "v5.4-map-ranking-prep",
        "v5.5-realistic-icon-system",
    }:
        errors.append("app_version.json is not aligned to the map-water-intel line")

app_text = read("app.py")
map_text = read("static/js/map_dashboard_v49.js")
map_html = read("templates/map.html")
water_html = read("templates/water.html")

for needle, message in [
    ('@app.route("/api/water-intel")', "app.py missing water intel API"),
    ('@app.route("/water/<water_id>")', "app.py missing water detail route"),
    ("build_water_intel", "app.py missing water intel builder"),
    ("get_water_record_by_id", "app.py missing water lookup"),
]:
    if needle not in app_text:
        errors.append(message)

for needle, message in [
    ("/api/water-intel", "Map dashboard should load selected-water intelligence"),
    ("mapTargetSpecies", "Map dashboard should include target species selector"),
    ("mapIntelResults", "Map dashboard should render water intel results"),
    ("/water/", "Map dashboard should link to water detail"),
]:
    if needle not in map_text:
        errors.append(message)

if "mapTargetSpecies" not in map_html or "mapIntelResults" not in map_html:
    errors.append("Map template should include target species and intel panel slots")

if "Water Intel" not in water_html or "Smart Intelligence" not in water_html:
    errors.append("Water detail template should show intel content")

from app import app as flask_app
from intelligence.water_registry import load_water_records

records = load_water_records()
if not records:
    errors.append("No water records available for water intel QC")
else:
    sample = records[0]
    water_id = sample.get("id")
    client = flask_app.test_client()

    response = client.get(f"/api/water-intel?water_id={water_id}")
    if response.status_code != 200:
        errors.append(f"Water intel API failed with HTTP {response.status_code}")
    else:
        payload = response.get_json(force=True)
        if payload.get("ok") is not True:
            errors.append("Water intel API did not return ok=true")
        if not payload.get("smart_intelligence"):
            errors.append("Water intel API did not return smart intelligence")
        if not payload.get("best_bet"):
            errors.append("Water intel API did not return a best bet")

    response = client.get(f"/water/{water_id}")
    if response.status_code != 200:
        errors.append(f"Water detail route failed with HTTP {response.status_code}")
    elif sample.get("name") and sample.get("name") not in response.get_data(as_text=True):
        errors.append("Water detail page does not include the waterbody name")

    response = client.get("/api/water-intel?water_id=missing-water-id")
    if response.status_code != 404:
        errors.append("Missing waterbody should return HTTP 404")

if errors:
    print("QC FAILED: v4.9.3 Map Water Intel")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.9.3 Map Water Intel")
print("Selected waterbodies now drive dedicated water intelligence.")
