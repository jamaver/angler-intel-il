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
    "data/version_v6_8_report_planning_polish.json",
):
    require(rel)

for rel in ("app.py", "angler_reports_v38.py"):
    try:
        ast.parse(read(rel))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

marker = json.loads(read("data/version_v6_8_report_planning_polish.json"))
if marker.get("version") != "v6.8-report-planning-polish":
    errors.append("Version marker mismatch")
for key in ("report_planning_polish", "report_learning_summary", "compact_report_cards", "forecast_context_preserved", "grouped_saved_reports", "admin_not_in_normal_nav"):
    if not marker.get(key):
        errors.append(f"Version marker missing {key}")

reports_text = read("angler_reports_v38.py")
for needle, message in (
    ("learning_summary", "Report overview should include a learning summary"),
    ("learning_takeaway", "Report overview should include a learning takeaway"),
    ("catch_quality", "Report overview should include catch quality"),
    ("report-learning-line", "Report list should render learning lines"),
):
    if needle not in reports_text:
        errors.append(message)

from app import app as flask_app
client = flask_app.test_client()

intel_res = client.get("/api/intel?zip=60543")
if intel_res.status_code != 200:
    errors.append(f"/api/intel failed with HTTP {intel_res.status_code}")
    intel = {}
else:
    intel = intel_res.get_json(silent=True) or {}

forecast = intel.get("forecast") if isinstance(intel, dict) else []
selected_date = ""
for item in forecast:
    if isinstance(item, dict) and item.get("date"):
        selected_date = str(item["date"])
        break
if not selected_date:
    errors.append("No forecast date available for report planning QC")

create_res = client.post(f"/api/reports/create?zip=60543&selected_forecast_date={selected_date}")
if create_res.status_code != 200:
    errors.append(f"/api/reports/create failed with HTTP {create_res.status_code}")
else:
    created = create_res.get_json(silent=True) or {}
    report = created.get("report") if isinstance(created, dict) else {}
    if not isinstance(report, dict) or not report.get("id"):
        errors.append("Report creation did not return a report payload")
    else:
        reports_api = client.get("/api/reports")
        if reports_api.status_code != 200:
            errors.append(f"/api/reports failed with HTTP {reports_api.status_code}")
        else:
            payload = reports_api.get_json(silent=True) or {}
            items = payload.get("reports") if isinstance(payload, dict) else []
            sample = next((item for item in items if isinstance(item, dict) and item.get("id") == report.get("id")), None)
            if not sample:
                errors.append("Saved report not returned by /api/reports")
            else:
                overview = sample.get("overview") if isinstance(sample.get("overview"), dict) else {}
                if not overview.get("learning_summary"):
                    errors.append("Report overview should include learning_summary")
                if not overview.get("catch_quality"):
                    errors.append("Report overview should include catch_quality")

        view_res = client.get(report.get("view_url") or "")
        if view_res.status_code != 200:
            errors.append(f"Saved report view failed with HTTP {view_res.status_code}")
        else:
            html = view_res.get_data(as_text=True)
            if "Raw saved JSON" not in html:
                errors.append("Saved report view should keep raw JSON collapsed")

        reports_res = client.get("/reports")
        if reports_res.status_code != 200:
            errors.append(f"/reports failed with HTTP {reports_res.status_code}")
        else:
            html = reports_res.get_data(as_text=True)
            for needle in ("report-learning-line", "report-list-card", "Saved trip plans"):
                if needle not in html:
                    errors.append(f"/reports HTML missing {needle}")
            if "/admin" in html:
                errors.append("Admin must not return to normal navigation")

if errors:
    print("QC FAILED: v6.8 report planning polish")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: v6.8 report planning polish")
