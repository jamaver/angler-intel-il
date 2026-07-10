#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import subprocess
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
    "data/app_version.json",
    "data/version_v5_5_realistic_icon_system.json",
    "docs/ROADMAP.md",
    "static/js/app.js",
    "static/js/map_dashboard_v49.js",
    "static/js/ui_polish_v442.js",
    "templates/map.html",
):
    assert_exists(rel)

for rel in ("app.py",):
    path = APP_ROOT / rel
    if path.exists():
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v5_5_realistic_icon_system.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.5-realistic-icon-system":
        errors.append("v5.5 marker has unexpected version")
    if marker.get("previous_version") != "v5.4-map-ranking-prep":
        errors.append("v5.5 marker has unexpected previous version")
    for key in ("icon_system_enabled", "water_icon_assets_enabled", "fish_icon_assets_enabled", "lure_icon_assets_enabled"):
        if marker.get(key) is not True:
            errors.append(f"v5.5 marker must set {key}=true")

app_version = json.loads((APP_ROOT / "data" / "app_version.json").read_text(encoding="utf-8"))
if app_version.get("version") not in {
    "v5.5-realistic-icon-system",
    "v5.6-waterbody-detail-panels",
}:
    errors.append("app_version.json is not aligned to v5.5 or later")
if app_version.get("modules", {}).get("realistic_icon_system") != "v5.5":
    errors.append("app_version.json missing realistic_icon_system module entry")

app_text = read("app.py")
if 'APP_VERSION = "v5.5-realistic-icon-system"' not in app_text and 'APP_VERSION = "v5.6-waterbody-detail-panels"' not in app_text:
    errors.append("app.py version string is not aligned to v5.5 or later")

map_js = read("static/js/map_dashboard_v49.js")
for needle in (
    "/static/icons/water/spillway.svg",
    "/static/icons/water/trout.svg",
):
    if needle not in map_js:
        errors.append(f"map JS missing icon mapping for {needle}")

map_template = read("templates/map.html")
for needle in (
    "/static/icons/water/spillway.svg",
    "/static/icons/water/trout.svg",
):
    if needle not in map_template:
        errors.append(f"map template missing legend icon {needle}")

icon_dir = APP_ROOT / "static" / "icons" / "water"
required_icons = {
    "lake.svg",
    "pond.svg",
    "river.svg",
    "reservoir.svg",
    "creek.svg",
    "manual.svg",
    "favorite.svg",
    "history.svg",
    "target.svg",
    "other.svg",
    "spillway.svg",
    "trout.svg",
}
present = {path.name for path in icon_dir.glob("*.svg")}
missing_icons = sorted(required_icons - present)
if missing_icons:
    errors.append(f"Missing water icons: {', '.join(missing_icons)}")

for rel in ("static/fish", "static/lures"):
    if not (APP_ROOT / rel).exists():
        errors.append(f"Missing {rel}")

if subprocess.run(["node", "--check", str(APP_ROOT / "static/js/app.js")], capture_output=True, text=True).returncode != 0:
    errors.append("static/js/app.js failed node --check")
if subprocess.run(["node", "--check", str(APP_ROOT / "static/js/map_dashboard_v49.js")], capture_output=True, text=True).returncode != 0:
    errors.append("static/js/map_dashboard_v49.js failed node --check")
if subprocess.run(["node", "--check", str(APP_ROOT / "static/js/ui_polish_v442.js")], capture_output=True, text=True).returncode != 0:
    errors.append("static/js/ui_polish_v442.js failed node --check")

from app import app as flask_app

client = flask_app.test_client()
response = client.get("/api/map-data?target_species=Largemouth Bass")
if response.status_code != 200:
    errors.append(f"/api/map-data failed with HTTP {response.status_code}")
else:
    payload = response.get_json(force=True)
    if payload.get("target_species") != "Largemouth Bass":
        errors.append("Map data did not resolve the target species")
    waters = payload.get("waters") or []
    if waters and not waters[0].get("target_fit"):
        errors.append("Map waters should include target fit annotations")

if errors:
    print("QC FAILED: v5.5 Realistic Icon System")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v5.5 Realistic Icon System")
print("Realistic icon assets and version markers are wired end to end.")
