#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

errors: list[str] = []


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def require(rel: str) -> None:
    path = ROOT / rel
    if not path.exists():
        errors.append(f"Missing {rel}")
    elif path.stat().st_size <= 0:
        errors.append(f"Empty {rel}")


for rel in (
    "app.py",
    "angler_reports_v38.py",
    "templates/snapshot.html",
    "data/version_v6_4_report_planning_polish.json",
):
    require(rel)

for rel in ("app.py", "angler_reports_v38.py"):
    try:
        ast.parse(read(rel))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

marker = json.loads(read("data/version_v6_4_report_planning_polish.json"))
if marker.get("version") != "v6.4-report-planning-polish":
    errors.append("Version marker mismatch")
for key in ("report_planning_polish", "grouped_saved_reports", "compact_report_cards", "smart_trip_reports_preserved", "admin_not_in_normal_nav"):
    if not marker.get(key):
        errors.append(f"Version marker missing {key}")

reports_text = read("angler_reports_v38.py")
for needle, message in (
    ("report-collection", "reports page should group saved reports"),
    ("report-group", "reports page should render grouped report sections"),
    ("report-list-card", "reports page should render compact report cards"),
    ("Create trip report", "reports page should use the new trip-report framing"),
    ("_default_report_title", "report titles should be auto-generated when blank"),
    ("_report_overview", "report overviews should be precomputed"),
):
    if needle not in reports_text:
        errors.append(message)

from app import app as flask_app
client = flask_app.test_client()

reports_res = client.get("/reports")
if reports_res.status_code != 200:
    errors.append(f"/reports failed with HTTP {reports_res.status_code}")
else:
    html = reports_res.get_data(as_text=True)
    for needle in ("report-collection", "report-group", "report-list-card", "Saved trip plans", "Create trip report"):
        if needle not in html:
            errors.append(f"/reports page missing {needle}")
    if "/admin" in html:
        errors.append("Admin must not return to normal navigation")

intel_res = client.get("/api/intel?zip=60543")
if intel_res.status_code != 200:
    errors.append(f"/api/intel failed with HTTP {intel_res.status_code}")
    intel = {}
else:
    intel = intel_res.get_json(silent=True) or {}

forecast = intel.get("forecast") if isinstance(intel, dict) else []
selected_date = forecast[1].get("date") if len(forecast) > 1 and isinstance(forecast[1], dict) else (forecast[0].get("date") if forecast and isinstance(forecast[0], dict) else "")
if not selected_date:
    errors.append("No selectable forecast date available for QC")

create_res = client.post(f"/api/reports/create?zip=60543&selected_forecast_date={selected_date}")
if create_res.status_code != 200:
    errors.append(f"/api/reports/create failed with HTTP {create_res.status_code}")
else:
    created = create_res.get_json(silent=True) or {}
    report = created.get("report") if isinstance(created, dict) else {}
    title = str(report.get("title") or "")
    if "Plan" not in title or "ZIP" not in title:
        errors.append(f"Auto-generated title is not trip-plan-like: {title!r}")
    if report.get("selected_forecast_date") != selected_date:
        errors.append("Selected forecast date did not persist in saved report")
    if report.get("view_url"):
        view_res = client.get(report["view_url"])
        if view_res.status_code != 200:
            errors.append(f"Saved report view failed with HTTP {view_res.status_code}")
        else:
            view_html = view_res.get_data(as_text=True)
            if "Trip date:" not in view_html:
                errors.append("Saved report view should show a trip date")
            if "forecast-day-selected" not in view_html:
                errors.append("Saved report view should highlight the selected forecast day")

reports_api = client.get("/api/reports")
if reports_api.status_code != 200:
    errors.append(f"/api/reports failed with HTTP {reports_api.status_code}")
else:
    payload = reports_api.get_json(silent=True) or {}
    items = payload.get("reports") if isinstance(payload, dict) else []
    if not items:
        errors.append("Expected at least one saved report in /api/reports")
    else:
        sample = items[0]
        if "overview" not in sample:
            errors.append("/api/reports should attach overview metadata")
        if "group" not in sample:
            errors.append("/api/reports should attach group metadata")

if errors:
    print("QC FAILED: v6.4 report planning polish")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: v6.4 report planning polish")
