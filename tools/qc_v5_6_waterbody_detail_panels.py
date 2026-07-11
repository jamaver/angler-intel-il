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
    "templates/water.html",
    "static/css/style.css",
    "data/version_v5_6_waterbody_detail_panels.json",
    "docs/ROADMAP.md",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists() and path.suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v5_6_waterbody_detail_panels.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.6-waterbody-detail-panels":
        errors.append("v5.6 marker has unexpected version")
    for key in ("water_detail_panels_enabled", "water_map_preview_enabled", "target_fit_panel_enabled", "detail_actions_enabled"):
        if marker.get(key) is not True:
            errors.append(f"v5.6 marker must set {key}=true")

app_version = json.loads((APP_ROOT / "data" / "app_version.json").read_text(encoding="utf-8"))
if app_version.get("version") not in {
    "v5.6-waterbody-detail-panels",
    "v5.7-waterbody-dataset-import-export",
    "v5.8-structured-backup-restore",
        "v5.9-modern-ui-refresh",
}:
    errors.append("app_version.json is not aligned to v5.6 or later")

app_text = read("app.py")
if 'APP_VERSION = "v5.6-waterbody-detail-panels"' not in app_text and 'APP_VERSION = "v5.7-waterbody-dataset-import-export"' not in app_text and 'APP_VERSION = "v5.8-structured-backup-restore"' not in app_text and 'APP_VERSION = "v5.9-modern-ui-refresh"' not in app_text:
    errors.append("app.py version string is not aligned to v5.6 or later")
for needle, message in [
    ('@app.route("/water/<water_id>")', "app.py missing water detail route"),
    ("water_badges", "app.py should surface water badges"),
    ("water_profile", "app.py should surface water profile context"),
    ("detail_actions", "app.py should provide detail actions"),
]:
    if needle not in app_text:
        errors.append(message)

template_text = read("templates/water.html")
for needle, message in [
    ("Waterbody profile", "Water template should render a profile header"),
    ("water-badge-row", "Water template should show badge chips"),
    ("water-map", "Water template should render a map preview"),
    ("Water Intel", "Water template should render the intelligence panel"),
    ("Smart Intelligence", "Water template should surface smart intelligence"),
    ("Target fit", "Water template should surface target-fit context"),
]:
    if needle not in template_text:
        errors.append(message)

css_text = read("static/css/style.css")
for needle, message in [
    ("water-map", "Water CSS missing map preview styling"),
    ("water-detail-rail", "Water CSS missing target-fit rail styling"),
    ("water-badge-row", "Water CSS missing badge row styling"),
]:
    if needle not in css_text:
        errors.append(message)

from app import app as flask_app
from intelligence.water_registry import load_water_records

records = load_water_records()
if not records:
    errors.append("No water records available for v5.6 QC")
else:
    sample = records[0]
    client = flask_app.test_client()
    response = client.get(f"/water/{sample.get('id')}")
    if response.status_code != 200:
        errors.append(f"Water detail page failed with HTTP {response.status_code}")
    else:
        html = response.get_data(as_text=True)
        if "water-badge-row" not in html or "Water Intel" not in html or "Smart Intelligence" not in html:
            errors.append("Water detail page did not render the updated layout")

    api_response = client.get(f"/api/water-intel?water_id={sample.get('id')}&target_species=Largemouth Bass")
    if api_response.status_code != 200:
        errors.append(f"/api/water-intel failed with HTTP {api_response.status_code}")
    else:
        payload = api_response.get_json(force=True)
        if payload.get("target_species") != "Largemouth Bass":
            errors.append("Water intel API did not accept target_species")
        if not payload.get("water_profile"):
            errors.append("Water intel API did not return water profile context")
        if not payload.get("detail_actions"):
            errors.append("Water intel API did not return detail actions")

if errors:
    print("QC FAILED: v5.6 Waterbody Detail Panels")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v5.6 Waterbody Detail Panels")
print("Waterbody detail pages render richer profile, target-fit, and map context.")
