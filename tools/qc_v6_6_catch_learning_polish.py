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
    "intelligence/catch_learning.py",
    "static/js/app.js",
    "templates/water.html",
    "data/version_v6_6_catch_learning_polish.json",
):
    require(rel)

for rel in ("app.py", "intelligence/catch_learning.py"):
    try:
        ast.parse(read(rel))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

marker = json.loads(read("data/version_v6_6_catch_learning_polish.json"))
if marker.get("version") != "v6.6-catch-learning-polish":
    errors.append("Version marker mismatch")
for key in ("catch_learning_polish", "headline_added", "takeaway_added", "dominant_signals_added", "dashboard_learning_summary", "water_learning_summary", "admin_not_in_normal_nav"):
    if not marker.get(key):
        errors.append(f"Version marker missing {key}")

catch_text = read("intelligence/catch_learning.py")
for needle, message in (
    ("headline", "Catch learning should expose a headline"),
    ("takeaway", "Catch learning should expose a takeaway"),
    ("dominant_species", "Catch learning should expose dominant species"),
    ("dominant_lure", "Catch learning should expose dominant lure"),
    ("dominant_waterbody", "Catch learning should expose dominant waterbody"),
):
    if needle not in catch_text:
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

catch_insights = intel.get("catch_insights") if isinstance(intel, dict) else {}
if not isinstance(catch_insights, dict):
    errors.append("Catch insights missing")
else:
    for key in ("headline", "takeaway", "dominant_species", "dominant_lure", "dominant_waterbody"):
        if key not in catch_insights:
            errors.append(f"Catch insights missing {key}")

dash_res = client.get("/")
if dash_res.status_code != 200:
    errors.append(f"/ failed with HTTP {dash_res.status_code}")
else:
    html = dash_res.get_data(as_text=True)
    if "dashboardBrief" not in html:
        errors.append("Dashboard should include the brief container")
    if "catchInsights" not in html:
        errors.append("Dashboard should include the catch insights container")
    if "dashboard-brief-learning" not in js_text:
        errors.append("Dashboard should surface catch learning in the brief")
    if "What your catches suggest" not in js_text:
        errors.append("Dashboard should render a catch learning headline")
    if "/admin" in html:
        errors.append("Admin must not return to normal navigation")

map_res = client.get("/api/map-data")
if map_res.status_code != 200:
    errors.append(f"/api/map-data failed with HTTP {map_res.status_code}")
else:
    payload = map_res.get_json(silent=True) or {}
    water = None
    if isinstance(payload, dict):
        waters = payload.get("top_waters") or payload.get("waters") or []
        water = next((item for item in waters if isinstance(item, dict) and item.get("id")), None)
    if not water:
        errors.append("No selectable water found for /water QC")
    else:
        water_res = client.get(f"/water/{water['id']}")
        if water_res.status_code != 200:
            errors.append(f"/water/{water['id']} failed with HTTP {water_res.status_code}")
        else:
            water_html = water_res.get_data(as_text=True)
            for needle in ("water-learning-summary", "What your catches suggest", "water-plan-card"):
                if needle not in water_html:
                    errors.append(f"Water page missing {needle}")

if errors:
    print("QC FAILED: v6.6 catch learning polish")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: v6.6 catch learning polish")
