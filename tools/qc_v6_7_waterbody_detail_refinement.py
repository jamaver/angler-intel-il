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
    "templates/water.html",
    "static/css/style.css",
    "data/version_v6_7_waterbody_detail_refinement.json",
):
    require(rel)

for rel in ("app.py",):
    try:
        ast.parse(read(rel))
    except SyntaxError as exc:
        errors.append(f"{rel} syntax error: {exc}")

marker = json.loads(read("data/version_v6_7_waterbody_detail_refinement.json"))
if marker.get("version") != "v6.7-waterbody-detail-refinement":
    errors.append("Version marker mismatch")
for key in ("waterbody_detail_refinement", "water_plan_card", "trip_plan_summary", "learning_summary_in_water_detail", "selected_water_focus", "admin_not_in_normal_nav"):
    if not marker.get(key):
        errors.append(f"Version marker missing {key}")

water_text = read("templates/water.html")
for needle, message in (
    ("water-plan-card", "Water page should start with a trip plan card"),
    ("water-plan-actions", "Water page should include water plan actions"),
    ("water-learning-summary", "Water page should include a learning summary"),
    ("What your catches suggest", "Water page should explain catch learning"),
):
    if needle not in water_text:
        errors.append(message)

css_text = read("static/css/style.css")
for needle, message in (
    ("water-plan-card", "Water plan CSS should exist"),
    ("water-plan-focus", "Water plan focus CSS should exist"),
    ("water-learning-summary", "Water learning summary CSS should exist"),
):
    if needle not in css_text:
        errors.append(message)

from app import app as flask_app
client = flask_app.test_client()

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
        errors.append("No selectable water found for water detail QC")
    else:
        water_res = client.get(f"/water/{water['id']}")
        if water_res.status_code != 200:
            errors.append(f"/water/{water['id']} failed with HTTP {water_res.status_code}")
        else:
            html = water_res.get_data(as_text=True)
            for needle in ("water-plan-card", "water-plan-actions", "water-learning-summary", "Map Preview", "Water Intel"):
                if needle not in html:
                    errors.append(f"Water detail HTML missing {needle}")
            if "/admin" in html:
                errors.append("Admin must not return to normal navigation")

if errors:
    print("QC FAILED: v6.7 waterbody detail refinement")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("QC PASSED: v6.7 waterbody detail refinement")
