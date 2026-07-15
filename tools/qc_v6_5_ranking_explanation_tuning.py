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
    "intelligence/smart_intelligence.py",
    "static/js/app.js",
    "templates/index.html",
    "templates/snapshot.html",
    "data/version_v6_5_ranking_explanation_tuning.json",
):
    require(rel)

for rel in ("app.py", "angler_reports_v38.py", "intelligence/smart_intelligence.py"):
    try:
        ast.parse(read(rel))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

marker = json.loads(read("data/version_v6_5_ranking_explanation_tuning.json"))
if marker.get("version") != "v6.5-ranking-explanation-tuning":
    errors.append("Version marker mismatch")
for key in (
    "ranking_explanation_tuning",
    "confidence_labels_refined",
    "ranking_factors_grouped",
    "explanation_sections_added",
    "dashboard_reasoning_cleaner",
    "report_reasoning_cleaner",
    "admin_not_in_normal_nav",
):
    if not marker.get(key):
        errors.append(f"Version marker missing {key}")

smart_text = read("intelligence/smart_intelligence.py")
for needle, message in (
    ("_explanation_sections", "Smart Intelligence should build grouped explanation sections"),
    ("ranking_factors", "Smart Intelligence should expose ranking factors"),
    ("decision_factors", "Smart Intelligence should expose decision factors"),
):
    if needle not in smart_text:
        errors.append(message)

app_text = read("app.py")
for needle, message in (
    ("ranking_factors", "Dashboard payload should carry ranking factors"),
    ("explanation_sections", "Dashboard payload should carry explanation sections"),
    ("decision_factors", "Dashboard payload should carry decision factors"),
    ("v6.5-ranking-explanation-tuning", "Release label should be updated to v6.5"),
):
    if needle not in app_text:
        errors.append(message)

reports_text = read("angler_reports_v38.py")
for needle, message in (
    ("ranking_factors", "Saved reports should carry ranking factors"),
    ("explanation_sections", "Saved reports should carry explanation sections"),
    ("decision_factors", "Saved reports should carry decision factors"),
):
    if needle not in reports_text:
        errors.append(message)

js_text = read("static/js/app.js")
for needle, message in (
    ("intel-rationale-grid", "Smart Intelligence card should render grouped rationale cards"),
    ("decision_factors", "Trip plan should use grouped decision factors"),
    ("ranking_factors", "Smart Intelligence should prefer grouped ranking factors"),
):
    if needle not in js_text:
        errors.append(message)

snapshot_text = read("templates/snapshot.html")
for needle, message in (
    ("report-factor-grid", "Snapshot should render ranking factor cards"),
    ("report-rationale-grid", "Snapshot should render explanation sections"),
    ("ranking_factors", "Snapshot should consume ranking factors"),
    ("explanation_sections", "Snapshot should consume explanation sections"),
):
    if needle not in snapshot_text:
        errors.append(message)

from app import app as flask_app
client = flask_app.test_client()

intel_res = client.get("/api/intel?zip=60543")
if intel_res.status_code != 200:
    errors.append(f"/api/intel failed with HTTP {intel_res.status_code}")
    intel = {}
else:
    intel = intel_res.get_json(silent=True) or {}

smart = intel.get("smart_intelligence") if isinstance(intel, dict) else {}
if not isinstance(smart, dict):
    errors.append("Smart Intelligence payload missing")
else:
    if not smart.get("ranking_factors"):
        errors.append("Smart Intelligence should expose ranking_factors")
    if not smart.get("explanation_sections"):
        errors.append("Smart Intelligence should expose explanation_sections")
    if not smart.get("decision_factors"):
        errors.append("Smart Intelligence should expose decision_factors")

dashboard_res = client.get("/")
if dashboard_res.status_code != 200:
    errors.append(f"/ failed with HTTP {dashboard_res.status_code}")
else:
    html = dashboard_res.get_data(as_text=True)
    if "Smart Intelligence" not in html:
        errors.append("Dashboard missing Smart Intelligence")
    if "/admin" in html:
        errors.append("Admin must not return to normal navigation")

report_create = client.post("/api/reports/create?zip=60543&selected_forecast_date=2026-07-14")
if report_create.status_code != 200:
    errors.append(f"/api/reports/create failed with HTTP {report_create.status_code}")
else:
    created = report_create.get_json(silent=True) or {}
    report = created.get("report") if isinstance(created, dict) else {}
    if not report:
        errors.append("Report creation failed to return a report payload")
    else:
        view_res = client.get(report.get("view_url") or "")
        if view_res.status_code != 200:
            errors.append(f"Report view failed with HTTP {view_res.status_code}")
        else:
            html = view_res.get_data(as_text=True)
            if "report-factor-grid" not in html or "report-rationale-grid" not in html:
                errors.append("Saved report should expose grouped rationale sections")

if errors:
    print("QC FAILED: v6.5 ranking and explanation tuning")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: v6.5 ranking and explanation tuning")
