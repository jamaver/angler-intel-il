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
    "templates/index.html",
    "static/js/app.js",
    "static/css/style.css",
    "angler_waters_v40.py",
    "data/version_v5_9_modern_ui_refresh.json",
    "docs/ROADMAP.md",
):
    assert_exists(rel)
    path = APP_ROOT / rel
    if path.exists() and path.suffix == ".py":
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

marker_path = APP_ROOT / "data" / "version_v5_9_modern_ui_refresh.json"
if marker_path.exists():
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("version") != "v5.9-modern-ui-refresh":
        errors.append("v5.9 marker has unexpected version")
    for key in ("modern_ui_refresh_enabled", "dashboard_map_first_shell", "hero_quick_actions_enabled", "nearby_water_preview_enabled"):
        if marker.get(key) is not True:
            errors.append(f"v5.9 marker must set {key}=true")

app_version = json.loads((APP_ROOT / "data" / "app_version.json").read_text(encoding="utf-8"))
if app_version.get("version") != "v5.9-modern-ui-refresh":
    errors.append("app_version.json is not aligned to v5.9")

app_text = read("app.py")
for needle, message in [
    ('APP_VERSION = "v5.9-modern-ui-refresh"', "app.py version string is not aligned to v5.9"),
    ("modern_ui_refresh", "app.py should record the modern UI refresh module"),
]:
    if needle not in app_text:
        errors.append(message)

index_text = read("templates/index.html")
for needle, message in [
    ('href="/map"', "Dashboard nav should expose Map"),
    ("dashboardSummary", "Dashboard should expose summary panel"),
    ("dashboardBrief", "Dashboard should expose nearby-water brief"),
    ("hero-actions", "Dashboard should expose quick action links"),
]:
    if needle not in index_text:
        errors.append(message)

js_text = read("static/js/app.js")
for needle, message in [
    ("renderDashboardSummary", "Dashboard JS should render summary metrics"),
    ("renderDashboardBrief", "Dashboard JS should render nearby-water brief"),
    ("waterIconForRecord", "Dashboard JS should use record-based water icons"),
]:
    if needle not in js_text:
        errors.append(message)

css_text = read("static/css/style.css")
for needle, message in [
    ("dashboard-v59", "Dashboard CSS should include the modern shell class"),
    ("dashboard-metric-grid", "Dashboard CSS should include summary metrics"),
    ("hero-action", "Dashboard CSS should style quick actions"),
    ("dashboard-brief-grid", "Dashboard CSS should style the brief section"),
]:
    if needle not in css_text:
        errors.append(message)

waters_text = read("angler_waters_v40.py")
if 'href="/map"' not in waters_text:
    errors.append("Local waters page should expose Map in the shell")

from app import app as flask_app
client = flask_app.test_client()
dashboard = client.get("/")
waters = client.get("/waters")
if dashboard.status_code != 200:
    errors.append(f"Dashboard failed with HTTP {dashboard.status_code}")
else:
    html = dashboard.get_data(as_text=True)
    for needle in ("Map Brief", "dashboardBrief", "dashboardSummary"):
        if needle not in html:
            errors.append(f"Dashboard HTML missing {needle}")
if waters.status_code != 200:
    errors.append(f"/waters failed with HTTP {waters.status_code}")

if errors:
    print("QC FAILED: v5.9 Modern UI Refresh")
    for error in errors:
        print(f" - {error}")
    raise SystemExit(1)

print("QC PASSED: v5.9 Modern UI Refresh")
print("Dashboard shell now surfaces map-first actions and nearby-water context.")
