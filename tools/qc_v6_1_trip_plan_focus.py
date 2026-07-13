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


def require(rel: str) -> None:
    path = APP_ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
    elif path.stat().st_size <= 0:
        errors.append(f"Empty {rel}")


for rel in (
    "app.py",
    "angler_reports_v38.py",
    "templates/index.html",
    "static/js/app.js",
    "static/css/style.css",
    "docs/ROADMAP.md",
    "data/version_v6_1_trip_plan_focus.json",
):
    require(rel)

for rel in ("app.py", "angler_reports_v38.py"):
    path = APP_ROOT / rel
    if path.exists():
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            errors.append(f"{rel} syntax error: {exc}")

version_marker = json.loads((APP_ROOT / "data/version_v6_1_trip_plan_focus.json").read_text(encoding="utf-8"))
if version_marker.get("version") != "v6.1-trip-plan-focus":
    errors.append("v6.1 marker has unexpected version")
for key in ("selected_water_focus", "trip_plan_card", "water_id_intel", "focus_water_persistence"):
    if version_marker.get(key) is not True:
        errors.append(f"v6.1 marker must set {key}=true")

index_text = read("templates/index.html")
js_text = read("static/js/app.js")
css_text = read("static/css/style.css")
roadmap_text = read("docs/ROADMAP.md")

for needle, message in (
    ("focusWater", "Dashboard should include a focus water selector"),
    ("focusWaterSummary", "Dashboard should explain the focus water selection"),
    ("tripPlan", "Dashboard should include the trip plan card"),
    ("One-screen plan", "Trip plan card should be labeled clearly"),
):
    if needle not in index_text:
        errors.append(message)

for needle, message in (
    ("loadFocusWaters", "Dashboard JS should load map waters into the focus selector"),
    ("renderTripPlan", "Dashboard JS should render the trip plan"),
    ("water_id", "Dashboard JS should pass water_id through to /api/intel"),
    ("currentFocusWaterId", "Dashboard JS should keep selected-water state"),
):
    if needle not in js_text:
        errors.append(message)

for needle, message in (
    ("trip-plan-grid", "Trip plan CSS should exist"),
    ("focus-water-control", "Focus-water control CSS should exist"),
    ("dashboard-trip-plan-card", "Trip plan card CSS should exist"),
):
    if needle not in css_text:
        errors.append(message)

if "v6.1 Trip Plan Focus" not in roadmap_text:
    errors.append("Roadmap should mention v6.1 Trip Plan Focus")

from app import app as flask_app
client = flask_app.test_client()

dash = client.get("/")
if dash.status_code != 200:
    errors.append(f"Dashboard failed with HTTP {dash.status_code}")
else:
    html = dash.get_data(as_text=True)
    for needle in ("focusWater", "tripPlan", "dashboard-trip-plan-card"):
        if needle not in html:
            errors.append(f"Dashboard HTML missing {needle}")
    if "/admin" in html:
        errors.append("Admin must not return to normal navigation")

map_data = client.get("/api/map-data")
if map_data.status_code != 200:
    errors.append(f"/api/map-data failed with HTTP {map_data.status_code}")
else:
    map_payload = map_data.get_json(silent=True) or {}
    records = []
    if isinstance(map_payload, dict):
        records = map_payload.get("top_waters") or map_payload.get("waters") or []
    selected = next((item for item in records if isinstance(item, dict) and item.get("id")), None)
    if not selected:
        errors.append("Map data did not return a selectable water record")
    else:
        water_id = str(selected.get("id"))
        intel = client.get(f"/api/intel?zip=60543&water_id={water_id}")
        if intel.status_code != 200:
            errors.append(f"/api/intel with water_id failed with HTTP {intel.status_code}")
        else:
            payload = intel.get_json(silent=True) or {}
            if not isinstance(payload, dict):
                errors.append("/api/intel with water_id did not return JSON")
            else:
                if payload.get("water", {}).get("id") != water_id:
                    errors.append("Water-specific intel did not echo the selected water id")
                if "best_bet" not in payload:
                    errors.append("Water-specific intel should include best_bet")

        report_create = client.post(f"/api/reports/create?zip=60543&water_id={water_id}&title=QC%20Trip%20Plan")
        if report_create.status_code != 200:
            errors.append(f"/api/reports/create with water_id failed with HTTP {report_create.status_code}")
        else:
            created = report_create.get_json(silent=True) or {}
            report = created.get("report") if isinstance(created, dict) else {}
            view_url = report.get("view_url")
            if not view_url:
                errors.append("Report creation did not return a view URL")
            else:
                report_html = client.get(view_url)
                if report_html.status_code != 200:
                    errors.append(f"{view_url} failed with HTTP {report_html.status_code}")
                else:
                    html = report_html.get_data(as_text=True)
                    if str(selected.get("name") or "") not in html:
                        errors.append("Selected water name should appear in the saved report")

if errors:
    print("QC FAILED: v6.1 Trip Plan Focus")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: v6.1 Trip Plan Focus")
