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


for rel in ("app.py", "tools/qc_v4_9_map_dashboard.py"):
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
        continue
    try:
        ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

for rel in (
    "templates/map.html",
    "static/js/map_dashboard_v49.js",
    "data/version_v4_9_map_dashboard_prototype.json",
):
    if not (APP_ROOT / rel).exists():
        errors.append(f"Missing {rel}")

marker_path = APP_ROOT / "data" / "version_v4_9_map_dashboard_prototype.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v4.9-map-dashboard-prototype":
        errors.append("v4.9 marker has unexpected version")
    if marker.get("json_source_of_truth") is not True:
        errors.append("v4.9 marker must keep JSON current")
    if marker.get("external_map_tiles") is not False:
        errors.append("v4.9 prototype should not require external map tiles")
    if marker.get("authority_switch_allowed_now") is not False:
        errors.append("v4.9 marker must not allow SQLite authority switch")

app_text = read("app.py")
nav_text = read("static/js/global_nav_v433.js")
map_html = read("templates/map.html") if (APP_ROOT / "templates/map.html").exists() else ""
map_js = read("static/js/map_dashboard_v49.js") if (APP_ROOT / "static/js/map_dashboard_v49.js").exists() else ""

if '@app.route("/map")' not in app_text:
    errors.append("app.py missing /map route")
if "/api/map-data" not in map_js:
    errors.append("Map dashboard should use /api/map-data")
if "/map" not in nav_text:
    errors.append("Global nav missing Map link")
if 'href="/admin"' in map_html or 'href="/admin"' in nav_text:
    errors.append("Map normal navigation should not expose Admin")
if "leaflet" in map_html.lower() or "tile.openstreetmap" in map_js.lower():
    errors.append("v4.9 prototype should not add external tile dependency")

from intelligence.map_data import get_map_data_readiness

readiness = get_map_data_readiness()
if readiness.get("record_count", 0) < 1:
    errors.append("Map data helper did not return map records")

if errors:
    print("QC FAILED: v4.9 Map Dashboard Prototype")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v4.9 Map Dashboard Prototype")
print("Map prototype renders from local map data without external tile dependency.")
