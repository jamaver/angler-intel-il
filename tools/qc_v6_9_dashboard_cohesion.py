#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import subprocess
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
    "static/js/app.js",
    "static/js/ui_polish_v442.js",
    "templates/index.html",
    "data/version_v6_9_dashboard_cohesion.json",
):
    require(rel)

for rel in ("app.py",):
    try:
        ast.parse(read(rel))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

for rel in ("static/js/app.js", "static/js/ui_polish_v442.js"):
    try:
        result = subprocess.run(["node", "--check", str(ROOT / rel)], capture_output=True, text=True)
        if result.returncode != 0:
            errors.append(f"{rel} node --check failed: {result.stderr.strip() or result.stdout.strip()}")
    except FileNotFoundError:
        errors.append("node is not available for JavaScript syntax checking")
        break

marker = json.loads(read("data/version_v6_9_dashboard_cohesion.json"))
if marker.get("version") != "v6.9-dashboard-cohesion":
    errors.append("Version marker mismatch")
for key in ("dashboard_cohesion", "dashboard_learning_metric", "trip_plan_learning_signal", "map_first_command_center", "secondary_sections_collapsed", "admin_not_in_normal_nav"):
    if not marker.get(key):
        errors.append(f"Version marker missing {key}")

app_text = read("app.py")
for needle, message in (
    ("v6.9-dashboard-cohesion", "App release should be updated to v6.9"),
    ("APP_RELEASE", "App release constant should exist"),
):
    if needle not in app_text:
        errors.append(message)

js_text = read("static/js/app.js")
for needle, message in (
    ("dashboard-brief-learning", "Dashboard brief should include learning context"),
    ("trip-plan-learning", "Trip plan should include a learning signal"),
    ("Learning", "Dashboard summary should mention learning"),
):
    if needle not in js_text:
        errors.append(message)

from app import app as flask_app
client = flask_app.test_client()
js_text = read("static/js/app.js")

intel_res = client.get("/api/intel?zip=60543")
if intel_res.status_code != 200:
    errors.append(f"/api/intel failed with HTTP {intel_res.status_code}")
    intel = {}
else:
    intel = intel_res.get_json(silent=True) or {}

catch = intel.get("catch_insights") if isinstance(intel, dict) else {}
if not isinstance(catch, dict) or not catch.get("headline"):
    errors.append("Catch insight headline should be present for dashboard cohesion")

dash_res = client.get("/")
if dash_res.status_code != 200:
    errors.append(f"/ failed with HTTP {dash_res.status_code}")
else:
    html = dash_res.get_data(as_text=True)
    for needle in ("dashboardBrief", "tripPlan", "smartIntelligence"):
        if needle not in html:
            errors.append(f"Dashboard HTML missing {needle}")
    for needle in ("dashboard-brief-learning", "trip-plan-learning", "Learning signal", "What your catches suggest"):
        if needle not in js_text:
            errors.append(f"Dashboard JS missing {needle}")
    if "/admin" in html:
        errors.append("Admin must not return to normal navigation")

if errors:
    print("QC FAILED: v6.9 dashboard cohesion")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: v6.9 dashboard cohesion")
