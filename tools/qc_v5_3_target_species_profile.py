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
    "intelligence/target_profile.py",
    "static/js/app.js",
    "static/js/map_dashboard_v49.js",
    "templates/index.html",
    "templates/map.html",
    "data/target_profile.json",
    "data/version_v5_3_target_species_profile.json",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists() and path.suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v5_3_target_species_profile.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.3-target-species-profile":
        errors.append("v5.3 marker has unexpected version")
    if marker.get("target_species_profile_enabled") is not True:
        errors.append("v5.3 marker must enable target species profiles")
    if marker.get("target_fit_ranking_prep") is not True:
        errors.append("v5.3 marker must enable target-fit ranking prep")

app_version_path = APP_ROOT / "data" / "app_version.json"
if app_version_path.exists():
    app_version = json.loads(app_version_path.read_text(encoding="utf-8"))
    if app_version.get("version") not in {
        "v5.3-target-species-profile",
        "v5.4-map-ranking-prep",
        "v5.5-realistic-icon-system",
        "v5.6-waterbody-detail-panels",
        "v5.7-waterbody-dataset-import-export",
        "v5.8-structured-backup-restore",
    }:
        errors.append("app_version.json is not aligned to v5.3")

app_text = read("app.py")
if 'APP_VERSION = "v5.3-target-species-profile"' not in app_text and 'APP_VERSION = "v5.4-map-ranking-prep"' not in app_text and 'APP_VERSION = "v5.5-realistic-icon-system"' not in app_text and 'APP_VERSION = "v5.6-waterbody-detail-panels"' not in app_text and 'APP_VERSION = "v5.7-waterbody-dataset-import-export"' not in app_text and 'APP_VERSION = "v5.8-structured-backup-restore"' not in app_text:
    errors.append("app.py version string is not aligned to v5.3")
for needle, message in [
    ('@app.route("/api/target-profile"', "app.py missing target profile API"),
    ("load_target_profile", "app.py should load the target profile"),
    ("resolve_target_species", "app.py should resolve target species"),
    ("species_fit_bonus", "app.py should compute target fit"),
]:
    if needle not in app_text:
        errors.append(message)

index_text = read("templates/index.html")
map_text = read("templates/map.html")
js_text = read("static/js/app.js")
map_js_text = read("static/js/map_dashboard_v49.js")
if "targetSpecies" not in index_text or "setTripTarget" not in index_text or "setDefaultTarget" not in index_text:
    errors.append("Dashboard target species controls are missing")
if "mapTargetSpecies" not in map_text:
    errors.append("Map target species selector is missing")
for needle, message in [
    ("loadTargetProfile", "Dashboard JS should load target profile"),
    ("saveTargetProfile", "Dashboard JS should save target profile"),
    ("syncTargetSpecies", "Dashboard JS should sync target species"),
    ("targetSpeciesNode", "Dashboard JS should track target selector"),
]:
    if needle not in js_text:
        errors.append(message)
for needle, message in [
    ("loadTargetProfile", "Map JS should load target profile"),
    ("saveTargetProfile", "Map JS should save target profile"),
    ("targetFitScore", "Map JS should compute target fit"),
    ("renderRankedWaters", "Map JS should render ranked waters"),
]:
    if needle not in map_js_text:
        errors.append(message)
if "Top Waters Right Now" not in map_text or "mapRankedList" not in map_text:
    errors.append("Map should expose a ranked waters panel")

from app import app as flask_app

client = flask_app.test_client()

original_profile = None
profile_path = APP_ROOT / "data" / "target_profile.json"
if profile_path.exists():
    original_profile = profile_path.read_text(encoding="utf-8")

try:
    response = client.get("/api/target-profile")
    if response.status_code != 200:
        errors.append(f"GET /api/target-profile failed with HTTP {response.status_code}")
    else:
        payload = response.get_json(force=True)
        profile = payload.get("profile", {})
        if "default_target_species" not in profile:
            errors.append("Target profile did not return default species")

    update = {
        "default_target_species": "Smallmouth Bass",
        "current_trip_target": "Smallmouth Bass",
        "favorite_species_add": "Smallmouth Bass",
    }
    response = client.post("/api/target-profile", json=update)
    if response.status_code != 200:
        errors.append(f"POST /api/target-profile failed with HTTP {response.status_code}")
    else:
        payload = response.get_json(force=True)
        profile = payload.get("profile", {})
        if profile.get("current_trip_target") != "Smallmouth Bass":
            errors.append("Target profile did not persist current trip target")

        intel = client.get("/api/intel?zip=60543")
        if intel.status_code != 200:
          errors.append(f"/api/intel failed with HTTP {intel.status_code}")
        else:
            data = intel.get_json(force=True)
            if data.get("target_species") != "Smallmouth Bass":
                errors.append("Intel did not resolve the target species profile")
            if data.get("target_species_source") not in {"current_trip_target", "default_target_species", "request"}:
                errors.append("Intel did not report a valid target species source")
            if not data.get("target_profile"):
                errors.append("Intel did not include target profile details")

            waters = data.get("waters") or []
            if waters:
                water_id = waters[0].get("id")
                water_intel = client.get(f"/api/water-intel?water_id={water_id}")
                if water_intel.status_code != 200:
                    errors.append(f"/api/water-intel failed with HTTP {water_intel.status_code}")
                else:
                    water_payload = water_intel.get_json(force=True)
                    if not water_payload.get("target_fit"):
                        errors.append("Water intel did not include target fit details")
finally:
    if original_profile is not None:
        profile_path.write_text(original_profile, encoding="utf-8")

if errors:
    print("QC FAILED: v5.3 Target Species Profile")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v5.3 Target Species Profile")
print("Target species profiles now persist and drive target-aware intel.")
