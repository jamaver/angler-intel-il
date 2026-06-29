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


for rel in (
    "app.py",
    "angler_health_v39.py",
    "intelligence/map_data.py",
    "intelligence/app_health_map_data.py",
    "tools/qc_v4_8_map_data_readiness.py",
):
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v4_8_map_data_readiness.json"
if not marker_path.exists():
    errors.append("Missing data/version_v4_8_map_data_readiness.json")
else:
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v4.8-map-data-readiness":
        errors.append("v4.8 marker has unexpected version")
    if marker.get("json_source_of_truth") is not True:
        errors.append("v4.8 marker must keep JSON current")
    if marker.get("authority_switch_allowed_now") is not False:
        errors.append("v4.8 marker must not allow SQLite authority switch")
    if marker.get("map_dashboard_planned") is not True:
        errors.append("v4.8 marker must declare map dashboard direction")

from intelligence.app_health_map_data import get_map_data_health_for_app
from intelligence.map_data import get_map_data_readiness, map_water_records

readiness = get_map_data_readiness()
records = map_water_records()
health = get_map_data_health_for_app()

if not isinstance(readiness, dict):
    errors.append("get_map_data_readiness did not return dict")
if not records:
    errors.append("map_water_records returned no records")
if readiness.get("json_source_of_truth") is not True:
    errors.append("Map readiness must preserve current JSON source-of-truth")
if "mirror/read-only" not in str(readiness.get("sqlite_role", "")).lower():
    errors.append("Map readiness must preserve SQLite mirror/read-only role")
if health.get("record_count", 0) < 1:
    errors.append("Map App Health should report records")

for item in records[:5]:
    for key in ("id", "name", "lat", "lon"):
        if item.get(key) in (None, ""):
            errors.append(f"Map record missing {key}")

health_text = read("angler_health_v39.py")
if "map_data_health" not in health_text:
    errors.append("App Health does not wire map_data_health")
if "_map_data_health_card.html" not in health_text:
    errors.append("App Health does not render map data card")

card_path = APP_ROOT / "templates" / "_map_data_health_card.html"
if not card_path.exists():
    errors.append("Missing templates/_map_data_health_card.html")
else:
    card = card_path.read_text(encoding="utf-8")
    if "Admin" in card:
        errors.append("Map data card should not mention Admin")

normal_nav = "\n".join(
    read(rel)
    for rel in (
        "templates/index.html",
        "angler_recommendations_v44.py",
        "angler_waters_v40.py",
        "angler_reports_v38.py",
        "angler_species_rigs_v43.py",
        "angler_health_v39.py",
        "static/js/global_nav_v433.js",
    )
)
if 'href="/admin"' in normal_nav:
    errors.append("Normal navigation should not expose Admin")

if errors:
    print("QC FAILED: v4.8 Map Data Readiness")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.8 Map Data Readiness")
print("Map data is readable and App Health visible.")
print("JSON remains current authority; SQLite transition remains planned.")
