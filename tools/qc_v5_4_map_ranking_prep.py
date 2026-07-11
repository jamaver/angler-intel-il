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
    "static/js/map_dashboard_v49.js",
    "templates/map.html",
    "intelligence/target_profile.py",
    "data/version_v5_4_map_ranking_prep.json",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists() and path.suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v5_4_map_ranking_prep.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.4-map-ranking-prep":
        errors.append("v5.4 marker has unexpected version")
    if marker.get("target_species_ranking_enabled") is not True:
        errors.append("v5.4 marker must enable target species ranking")
    if marker.get("ranked_waters_panel_enabled") is not True:
        errors.append("v5.4 marker must enable the ranked waters panel")

app_version_path = APP_ROOT / "data" / "app_version.json"
if app_version_path.exists():
    app_version = json.loads(app_version_path.read_text(encoding="utf-8"))
    if app_version.get("version") not in {
        "v5.4-map-ranking-prep",
        "v5.5-realistic-icon-system",
        "v5.6-waterbody-detail-panels",
        "v5.7-waterbody-dataset-import-export",
        "v5.8-structured-backup-restore",
    }:
        errors.append("app_version.json is not aligned to v5.4 or later")

app_text = read("app.py")
if 'APP_VERSION = "v5.4-map-ranking-prep"' not in app_text and 'APP_VERSION = "v5.5-realistic-icon-system"' not in app_text and 'APP_VERSION = "v5.6-waterbody-detail-panels"' not in app_text and 'APP_VERSION = "v5.7-waterbody-dataset-import-export"' not in app_text and 'APP_VERSION = "v5.8-structured-backup-restore"' not in app_text:
    errors.append("app.py version string is not aligned to v5.4 or later")
for needle, message in [
    ('@app.route("/api/map-data")', "app.py missing map-data route"),
    ("species_fit_bonus", "app.py should annotate waters with target fit"),
    ("top_waters", "app.py should return top waters"),
]:
    if needle not in app_text:
        errors.append(message)

map_text = read("templates/map.html")
map_js_text = read("static/js/map_dashboard_v49.js")
if "Top Waters Right Now" not in map_text or "mapRankedList" not in map_text:
    errors.append("Map template should expose the ranked waters panel")
for needle, message in [
    ("targetFitScore", "Map JS should compute target fit"),
    ("renderRankedWaters", "Map JS should render ranked waters"),
    ("target_species", "Map JS should request target-aware map data"),
]:
    if needle not in map_js_text:
        errors.append(message)

from app import app as flask_app

client = flask_app.test_client()
response = client.get("/api/map-data?target_species=Smallmouth Bass")
if response.status_code != 200:
    errors.append(f"/api/map-data failed with HTTP {response.status_code}")
else:
    payload = response.get_json(force=True)
    if payload.get("target_species") != "Smallmouth Bass":
        errors.append("Map data did not resolve the target species")
    if not payload.get("target_ranking_enabled"):
        errors.append("Map data should enable target ranking when a target exists")
    waters = payload.get("waters") or []
    if waters:
        first = waters[0]
        if not first.get("target_fit"):
            errors.append("Map waters did not include target fit annotations")
    if not payload.get("top_waters"):
        errors.append("Map data did not return top waters")

if errors:
    print("QC FAILED: v5.4 Map Ranking Prep")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v5.4 Map Ranking Prep")
print("Target-aware map ranking annotations are wired end to end.")
